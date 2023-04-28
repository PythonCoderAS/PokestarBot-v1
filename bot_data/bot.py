import asyncio
import atexit
import collections
import datetime
import functools
import inspect
import logging
import os
import subprocess
import sys
import time
import traceback
import types
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Type, TypeVar, Union, overload

import aiohttp
import aiosqlite
import discord.ext.commands
import discord.ext.tasks
import psutil
import pytz
import sentry_sdk.integrations.logging

from bot_data import bot_version, command_logger
from bot_data.const import bad_argument_regex, invalid_spoiler, on_reaction_func_type, option_types, quote, url_regex, warning_on_failure, \
    warning_on_invalid_spoiler
from bot_data.creds import TOKEN, bot_support_join_leave_channel_id, bot_support_stats_total_commands_channel_id, \
    bot_support_stats_total_messages_sent_channel_id, owner_id, sentry_link
from bot_data.utils import BoundedList, Embed, HubContext, Mention, ReloadingClient, StopCommand, UserMention, get_context_variables, \
    get_context_variables_from_traceback, \
    send_embeds_fields
from bot_data.utils.data import BotBaseDataClass, DiscordDataException
from bot_data.utils.data.util import remove_prefix
from bot_data.utils.data.waifu import TooManyAnimeNames, TooManyBrackets, TooManyWaifuNames

logger = logging.getLogger(__name__)

NY = pytz.timezone("America/New_York")

_T = TypeVar("_T")
_ContextType = TypeVar("_ContextType", bound=discord.ext.commands.Context)
[sentry_sdk.integrations.logging.ignore_logger(logger_name) for logger_name in ("bot_command_log", "bot_data.bot")]

sentry_sdk.init(sentry_link, traces_sample_rate=1.0)


class PokestarBot(discord.ext.commands.Bot):
    INVALID_SPOILER = invalid_spoiler
    URL_REGEX = url_regex
    WARNING = warning_on_invalid_spoiler
    WARNING_FAIL = warning_on_failure
    QUOTE_MARKER = quote
    BAD_ARGUMENT = bad_argument_regex

    def __init__(self):
        self.started = datetime.datetime.utcnow()
        intents = discord.Intents.all()
        intents.typing = False
        intents.integrations = False
        intents.webhooks = False
        super().__init__("%", activity=discord.Game("%help • %support"), case_insensitive=True, intents=intents)
        self.stats_working_on_dict = {}
        self.stats_lock = asyncio.Lock()
        self.pings = BoundedList()
        self.spoiler_hashes = BoundedList()
        self.ping_timedelta = datetime.timedelta(seconds=0)
        self.owner_id = owner_id
        self.obj_ids = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self.conn: Optional[aiosqlite.Connection] = None
        self.channel_data = {}
        self.disabled_commands = {}
        self.channel_queue = asyncio.Queue()
        self.disabled_stat_channels = {}
        self.options = {}
        self.blacklisted_emojis = {}
        self.commands_processed = 0
        self.events = {}
        self.on_reaction_funcs: Dict[on_reaction_func_type] = {}
        self.running_stats_counter = 0
        self.running_stats_lock = asyncio.Lock()
        BotBaseDataClass.bot = self
        self.increment_commands_processed = self.after_invoke(self.increment_commands_processed)
        self.send_counter = 0
        self.send_lock = asyncio.Lock()
        self.command_counter = 0
        self.command_lock = asyncio.Lock()
        self.http.send_message = functools.partial(self.send_with_counter, self.http.send_message)
        self.http.send_files = functools.partial(self.send_with_counter, self.http.send_files)
        self.on_ready_wait = asyncio.Lock()
        self.setup_done = asyncio.Event()
        self.bracket_cache = None
        self.hubs = []

        for file in os.listdir(os.path.abspath(os.path.join(__file__, "..", "extensions"))):
            if not file.startswith("_"):
                name, sep, ext = file.rpartition(".")
                self.load_extension("bot_data.extensions.{}".format(name))

    async def send_with_counter(self, coro: Callable[..., Coroutine[None, None, _T]], *args, **kwargs) -> _T:
        async with self.send_lock:
            self.send_counter += 1
        return await coro(*args, **kwargs)

    def stats_working_on(self, guild_id: int):
        return self.stats_working_on_dict.setdefault(guild_id, asyncio.Event())

    @overload
    async def get_context(self, message: discord.Message) -> HubContext:
        pass

    @overload
    async def get_context(self, message: discord.Message, *, cls: Type[_ContextType]) -> _ContextType:
        pass

    async def get_context(self, message, *, cls=HubContext):
        return await super().get_context(message, cls=cls)

    def add_cog(self, cog: discord.ext.commands.Cog):
        """Every on_reaction method works very similarly, where they take the same arguments, just run a different batch of if statements. We can
        have the code for the actual on_raw_reaction event be on the bot, and just run each on_reaction event with the same arguments. This
        prevents having to fetch multiple copies of the same message, and should significantly speedup reaction events."""
        if hasattr(cog, "on_reaction"):
            self.on_reaction_funcs[cog.qualified_name] = cog.on_reaction
        return super().add_cog(cog)

    async def execute(self, function: Callable[..., _T], *args, **kwargs) -> _T:
        return await self.loop.run_in_executor(None, functools.partial(function, *args, **kwargs))

    @staticmethod
    def get_context_from_traceback(tb: types.TracebackType):
        cur_tb = tb
        tb_hashes = []
        while cur_tb is not None and hash(cur_tb) not in tb_hashes:
            frame = cur_tb.tb_frame
            for item in frame.f_locals.copy().values():
                if isinstance(item, HubContext):
                    return item
            tb_hashes.append(hash(cur_tb))
            cur_tb = tb.tb_next

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.user.id:  # ignore self reactions
            return
        channel: Optional[discord.TextChannel, discord.abc.PrivateChannel] = self.get_channel(payload.channel_id)
        if channel is None:  # in DM channel that hasn't been created yet, good luck! Exiting.
            return
        message: Optional[discord.Message] = discord.utils.find(lambda m: m.id == payload.message_id, self.cached_messages)
        if message is None:
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                logger.debug("Message not found: %s", payload.message_id)
                return
            else:
                self._connection._messages.append(message)
        if payload.guild_id:
            guild: Optional[discord.Guild] = self.get_guild(payload.guild_id)
        else:
            guild = None
        user = self.get_user(guild, payload.user_id)
        emoji = payload.emoji
        for func in self.on_reaction_funcs.values():
            try:
                await func(message, emoji, user)
            except discord.ext.commands.CommandError as exc:
                ctx = self.get_context_from_traceback(exc.__traceback__)
                if ctx is None:
                    raise
                else:
                    await self.on_command_error(ctx, exc)
            except Exception as exc:
                ctx = self.get_context_from_traceback(exc.__traceback__)
                if ctx is None:
                    raise
                else:
                    await self.on_command_error(ctx, discord.ext.commands.CommandInvokeError(exc))

    @staticmethod
    def permission_names(permissions: Union[discord.Permissions, discord.PermissionOverwrite]):
        return ", ".join(name.strip() for name, value in permissions if value)

    def context_from_user(self, author: Union[discord.Member, discord.User], channel: Optional[discord.abc.GuildChannel] = None, *,
                          name: str = "user") -> Dict[str, Dict[str, Any]]:
        if author:
            perm_name = name + "_permissions"
            derived = {name: {}}
            derived[name]["username"] = f"{author.name}#{author.discriminator}"
            derived[name]["display_name"] = author.display_name
            derived[name]["id"] = author.id
            if isinstance(author, discord.Member):
                top_role: discord.Role = author.top_role
                derived[perm_name] = {}
                derived[perm_name]["top_role"] = top_role.name
                derived[perm_name]["top_role_id"] = top_role.id
                derived[perm_name]["bot_owner"] = author.id == self.owner_id
                derived[perm_name]["is_administrator"] = author.guild_permissions.administrator
                derived[perm_name]["guild_permissions"] = self.permission_names(author.guild_permissions)
                if channel:
                    derived[perm_name]["channel_permissions"] = self.permission_names(author.permissions_in(channel))
            return derived
        return {}

    def context_from_channel(self, channel: Optional[Union[discord.TextChannel, discord.DMChannel]], *, name: str = "channel") -> Dict[
        str, Dict[str, Any]]:
        derived = {}
        if channel:
            guild: discord.Guild = channel.guild
            if guild:
                bot_user = guild.me
            else:
                bot_user = self.user
            derived[name] = {}
            derived[name]["name"] = str(channel)
            derived[name]["id"] = channel.id
            if isinstance(channel, discord.TextChannel):
                derived[name]["nsfw"] = channel.nsfw
                derived[name]["private"] = channel.overwrites_for(guild.default_role).read_messages is True
                derived[name]["category"] = channel.category
            derived[name]["bot_permissions"] = self.permission_names(channel.permissions_for(bot_user))
        return derived

    def context_from_voice_channel(self, channel: discord.VoiceChannel, *, name: str = "voice_channel") -> Dict[str, Dict[str, Any]]:
        guild: discord.Guild = channel.guild
        bot_user = guild.me
        derived = {name: {}}
        derived[name]["name"] = str(channel)
        derived[name]["id"] = channel.id
        derived[name]["bitrate"] = channel.bitrate
        derived[name]["limit"] = channel.user_limit
        derived[name]["users"] = channel.members
        derived[name]["private"] = channel.overwrites_for(guild.default_role).read_messages is True
        derived[name]["category"] = channel.category
        derived[name]["bot_permissions"] = self.permission_names(channel.permissions_for(bot_user))
        return derived

    def context_from_category_channel(self, channel: discord.CategoryChannel, *, name: str = "category_channel") -> Dict[str, Dict[str, Any]]:
        guild: discord.Guild = channel.guild
        bot_user = guild.me
        derived = {name: {}}
        derived[name]["name"] = str(channel)
        derived[name]["id"] = channel.id
        derived[name]["private"] = channel.overwrites_for(guild.default_role).read_messages is True
        derived[name]["bot_permissions"] = self.permission_names(channel.permissions_for(bot_user))
        return derived

    def context_from_guild(self, guild: Optional[discord.Guild], *, name: str = "guild") -> Dict[str, Dict[str, Any]]:
        derived = {}
        if guild:
            bot_user = guild.me
            derived[name] = {}
            derived[name]["name"] = guild.name
            derived[name]["id"] = guild.id
            derived[name]["is_large"] = guild.large
            derived[name]["nitro_boost_level"] = guild.premium_tier
            derived[name]["bot_permissions"] = self.permission_names(bot_user.guild_permissions)

        return derived

    @staticmethod
    def context_from_message(message: Optional[discord.Message], *, name: str = "message") -> Dict[str, Dict[str, Any]]:
        derived = {}
        if message:
            message_type: discord.MessageType = message.type
            derived[name] = {}
            derived[name]["id"] = message.id
            derived[name]["timestamp"] = message.created_at
            derived[name]["url"] = message.jump_url
            derived[name]["type"] = message_type.name
            derived[name]["content"] = message.content
            derived[name]["embed_count"] = len(message.embeds)
            derived[name]["file_count"] = len(message.attachments)
        return derived

    def context_from_role(self, role: discord.Role, channel: Optional[discord.abc.GuildChannel], *, name: str = "role") -> Dict[str, Dict[str, Any]]:
        derived = {name: {}}
        derived[name]["name"] = role.name
        derived[name]["id"] = role.id
        derived[name]["color"] = hex(role.color.value)[2:].upper()
        derived[name]["members"] = len(role.members)
        derived[name]["position"] = len(role.position)
        derived[name]["permissions"] = self.permission_names(role.permissions)
        if channel:
            derived[name]["permissions_in_channel_id"] = channel.id
            derived[name]["permissions_in_channel"] = self.permission_names(channel.overwrites_for(role))
        return derived

    def get_context_for_object(self, obj: Any, suffix: str = "", *, memo: Optional[List[int]] = None,
                               _channel_for_roles: Optional[discord.abc.GuildChannel] = None) -> Dict[str, Dict[str, Any]]:
        if memo is None:
            memo = []
        if id(obj) in memo:
            return {}
        if isinstance(obj, (discord.TextChannel, discord.DMChannel)):
            return self.context_from_channel(obj, name="channel" + suffix)
        elif isinstance(obj, discord.VoiceChannel):
            return self.context_from_voice_channel(obj, name="voice_channel" + suffix)
        elif isinstance(obj, discord.CategoryChannel):
            return self.context_from_category_channel(obj, name="category_channel" + suffix)
        elif isinstance(obj, discord.Guild):
            return self.context_from_guild(obj, name="guild" + suffix)
        elif isinstance(obj, (discord.Member, discord.User, discord.ClientUser, discord.abc.User)):
            return self.context_from_user(obj, name="user" + suffix)
        elif isinstance(obj, discord.Message):
            return self.context_from_message(obj, name="message" + suffix)
        elif isinstance(obj, discord.Role):
            return self.context_from_role(obj, _channel_for_roles, name="role" + suffix)
        elif isinstance(obj, list):
            data = {}
            for num, value in enumerate(obj, start=1):
                data.update(self.get_context_for_object(value, suffix=suffix + f"_item_{num}", memo=memo, _channel_for_roles=_channel_for_roles))
            return data
        elif isinstance(obj, dict):
            data = {}
            for key, value in obj.items():
                data.update(self.get_context_for_object(value, suffix=suffix + f"_{key}", memo=memo, _channel_for_roles=_channel_for_roles))
            return data
        else:
            return {}

    def extra_context_from_args(self, *args: Any, _channel_for_roles: Optional[discord.abc.GuildChannel] = None, **kwargs: Any) -> Dict[
        str, Dict[str, Any]]:
        data = {}
        memo = []
        for num, value in enumerate(args, start=1):
            data.update(self.get_context_for_object(value, suffix=f"_item_{num}", memo=memo, _channel_for_roles=_channel_for_roles))
        for key, value in kwargs.items():
            data.update(self.get_context_for_object(value, suffix=f"_{key}", memo=memo, _channel_for_roles=_channel_for_roles))
        return data

    def context_dict_from_context_object(self, context: HubContext) -> Dict[str, Dict[str, Any]]:
        derived = {"channel": {}}
        author: Union[discord.Member, discord.User] = context.author
        channel: Union[discord.TextChannel, discord.DMChannel] = context.channel
        guild: Optional[discord.Guild] = context.guild
        message: Optional[discord.Message] = context.message
        command: Optional[discord.ext.commands.Command] = context.command
        derived.update(self.context_from_user(author, channel))
        derived.update(self.context_from_channel(channel))
        derived.update(self.context_from_guild(guild))
        derived.update(self.context_from_message(message))
        if command:
            derived["command"] = {}
            derived["command"]["name"] = command.qualified_name
            derived["command"]["cog"] = command.cog
            derived["command"]["parent"] = command.parent
            derived["command"]["args"] = context.args
            derived["command"]["kwargs"] = context.kwargs
            if message:
                derived["command"]["args_unparsed"] = remove_prefix(message.content, context.prefix + context.invoked_with)
            derived["command"]["invoked"] = not context.command_failed
            derived.update(self.extra_context_from_args(context.args[2:], context.kwargs))
        return derived

    @staticmethod
    def tags_from_values(author: Optional[discord.User], guild: Optional[discord.Guild],
                         channel: Optional[Union[discord.TextChannel, discord.DMChannel]], command: Optional[discord.ext.commands.Command]) -> Dict[
        str, Union[int, str]]:
        derived = {}
        if author:
            derived["author_id"] = author.id
        if guild:
            derived["guild_id"] = guild.id
        if channel:
            derived["channel_id"] = channel.id
        if command:
            derived["command_name"] = command.qualified_name
        return derived

    @classmethod
    def tags_from_context(cls, context: HubContext) -> Dict[str, Union[int, str]]:
        return cls.tags_from_values(context.author, context.guild, context.channel, context.command)

    def scope_from_context(self, context: HubContext, *, extra_context: Optional[Dict[str, Dict[str, Any]]] = None,
                           tag_data: Optional[Dict[str, Any]] = None) -> sentry_sdk.Scope:
        if tag_data is None:
            tag_data = {}
        if extra_context is None:
            extra_context = {}
        scope_manager = context.hub.push_scope()
        scope = scope_manager.__enter__()
        if context:
            if isinstance(context, HubContext):
                original_context = context
                tag_data = {**self.tags_from_context(original_context), **tag_data}
                context = self.context_dict_from_context_object(original_context)
                user: Union[discord.Member, discord.User] = original_context.author
                scope.set_user({"id": user.id, "username": user.name + "#" + user.discriminator})
            context.update(extra_context)
            for key, value in context.items():
                scope.set_context(key, value)
        for key, value in tag_data.items():
            scope.set_tag(key, value)
        return scope_manager

    async def report_exception(self, exception: BaseException, context: Optional[Union[HubContext, Dict[str, Dict[str, Any]]]] = None, *,
                               extra_context: Optional[Dict[str, Dict[str, Any]]] = None, tag_data: Optional[Dict[str, Any]] = None):
        with self.scope_from_context(context, extra_context=extra_context, tag_data=tag_data) as scope:
            scope: sentry_sdk.Scope
            if isinstance(context, HubContext):
                prefix = context.hub
            else:
                prefix = sentry_sdk
            return await self.execute(prefix.capture_exception, exception, scope=scope)

    async def report_message(self, message: str, context: Optional[Union[HubContext, Dict[str, Dict[str, Any]]]] = None, *,
                             extra_context: Optional[Dict[str, Dict[str, Any]]] = None, tag_data: Optional[Dict[str, Any]] = None):
        with self.scope_from_context(context, extra_context=extra_context, tag_data=tag_data) as scope:
            scope: sentry_sdk.Scope
            if isinstance(context, HubContext):
                prefix = context.hub
            else:
                prefix = sentry_sdk
            return await self.execute(prefix.capture_message, message, scope=scope)

    @property
    def events_processed(self):
        return sum(self.events.values())

    def missing_argument(self, name: str):
        raise discord.ext.commands.MissingRequiredArgument(inspect.Parameter(name, kind=inspect.Parameter.POSITIONAL_ONLY))

    @property
    def session(self):
        while self._session is None:
            time.sleep(0.1)
        return self._session

    @session.setter
    def session(self, s: aiohttp.ClientSession):
        self._session = s

    def get_channel_data(self, guild_id: Optional[int], channel_name: str) -> Optional[Union[discord.abc.GuildChannel, discord.abc.PrivateChannel]]:
        if not isinstance(guild_id, int) and hasattr(guild_id, "id"):
            guild_id = guild_id.id
        guild_data = self.channel_data.get(guild_id, None)
        if guild_data is None:
            return None
        else:
            channel_id = guild_data.get(channel_name, None)
            if channel_id is None:
                return None
            if guild := self.get_guild(guild_id):
                return guild.get_channel(channel_id)
            else:
                return None

    @staticmethod
    def datetime_data(dt_obj: datetime.datetime) -> Dict[str, Union[int, datetime.datetime]]:
        return {
            "timestamp": dt_obj.timestamp(), "time_utc": dt_obj.astimezone(pytz.UTC), "year": dt_obj.year, "month": dt_obj.month, "day": dt_obj,
            "hour_24": dt_obj.hour, "hour_12": (dt_obj.hour % 12 or 12), "minute": dt_obj.minute, "second": dt_obj.second,
            "microsecond": dt_obj.microsecond
        }

    @staticmethod
    async def send_all(ctx: discord.abc.Messageable, embed_list: List[discord.Embed]) -> List[discord.Message]:
        return [await ctx.send(embed=item) for item in embed_list]

    def command_disabled(self, ctx: HubContext):
        if not hasattr(ctx.guild, "id"):
            return False
        guild_data = self.disabled_commands.get(getattr(ctx.guild, "id", None), [])
        cmd_name = getattr(ctx.command, 'qualified_name', '')
        for name in guild_data:
            if name.startswith(cmd_name):
                return True
        return False

    @overload
    def get_user(self, user_id: int, return_psuedo_object: bool = False) -> Optional[Union[discord.User, discord.Object]]:
        pass

    @overload
    def get_user(self, guild: Optional[discord.Guild], user_id: int) -> Union[discord.Member, discord.User, Mention]:
        pass

    def get_user(self, id1: Optional[Union[int, discord.Guild]], id2: Optional[int] = None, return_psuedo_object: bool = False) -> Optional[
        Union[discord.Member, discord.User, Mention, discord.Object]]:
        if id2 is None:  # Bot call
            val = super().get_user(id1)
            if val is None and return_psuedo_object:
                return discord.Object(id1)
            else:
                return val
        else:
            guild = id1
            user_id = id2
        # First, get the guild member normally
        if guild:
            member: Optional[discord.Member] = guild.get_member(user_id)
        else:
            member = None
        if not member:
            # Second, try to get the user
            user: Optional[discord.User] = super().get_user(user_id)
            if not user:
                # Finally, just return a plain AttrDict
                return UserMention(user_id)
            else:
                return user
        else:
            return member

    def get_guild(self, id: int, return_psuedo_object: bool = False) -> Optional[Union[discord.Guild, discord.Object]]:
        val = super().get_guild(id)
        if val is None and return_psuedo_object:
            return discord.Object(id)
        else:
            return val

    async def pre_create(self):
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS CHANNEL_DATA(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, CHANNEL_NAME TEXT NOT 
                NULL, CHANNEL_ID BIGINT NOT NULL, UNIQUE (GUILD_ID, CHANNEL_NAME))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS DISABLED_COMMANDS(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, COMMAND_NAME TEXT 
                NOT NULL, UNIQUE (GUILD_ID, COMMAND_NAME))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS STAT(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, CHANNEL_ID BIGINT NOT NULL, 
                AUTHOR_ID BIGINT NOT NULL, NUM INTEGER NOT NULL, UNIQUE(GUILD_ID, CHANNEL_ID, AUTHOR_ID))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS DISABLED_STATS(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, CHANNEL_ID BIGINT NOT 
                NULL, UNIQUE (GUILD_ID, CHANNEL_ID))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS OPTIONS(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, OPTION_NAME TEXT NOT NULL, 
                ENABLED BOOLEAN NOT NULL, UNIQUE (GUILD_ID, OPTION_NAME))"""):
            pass
        async with self.conn.execute("""CREATE TABLE IF NOT EXISTS INVITES(CODE VARCHAR(6) PRIMARY KEY, GUILD_ID BIGINT NOT NULL, USES SMALLINT)"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS BLACKLISTED_EMOJIS(ID INTEGER PRIMARY KEY AUTOINCREMENT, GUILD_ID BIGINT NOT NULL, EMOJI TEXT NOT 
                NULL, UNIQUE(GUILD_ID, EMOJI))"""):
            pass

    @staticmethod
    def check_recursive(func_name: str, command: discord.ext.commands.Command, *checks):
        for check in checks:
            if hasattr(check, "predicate"):
                check = check.predicate
            getattr(command, func_name)(check)
            if isinstance(command, discord.ext.commands.Group):
                for subcommand in command.walk_commands():
                    if subcommand != command:
                        subcommand.add_check(check)

    @classmethod
    def add_check_recursive(cls, command: discord.ext.commands.Command, *checks):
        cls.check_recursive("add_check", command, *checks)

    @classmethod
    def remove_check_recursive(cls, command: discord.ext.commands.Command, *checks):
        cls.check_recursive("remove_check", command, *checks)

    async def get_channel_mappings(self):
        async with self.conn.execute("""SELECT GUILD_ID, CHANNEL_NAME, CHANNEL_ID FROM CHANNEL_DATA""") as cursor:
            data = await cursor.fetchall()
        for guild_id, channel_name, channel_id in data:
            guild_data = self.channel_data.setdefault(guild_id, {})
            guild_data[channel_name] = channel_id

    def get_option(self, guild_id: Optional[int], option: str, *, allow_dm: bool = False):
        assert option in option_types, f"Option {option!r} does not exist currently."
        if not isinstance(guild_id, int) and hasattr(guild_id, "id"):
            guild_id = guild_id.id
        guild_data = self.options.get(guild_id, None)
        if guild_data is None:
            if allow_dm:
                return option_types[option][1]
            return None
        else:
            return guild_data.get(option, False)

    async def get_option_mappings(self):
        self.options = {}
        async with self.conn.execute("""SELECT GUILD_ID, OPTION_NAME, ENABLED FROM OPTIONS""") as cursor:
            data = await cursor.fetchall()
        for guild_id, option, enabled in data:
            guild_data = self.options.setdefault(guild_id, {})
            guild_data[option] = bool(enabled)
        for guild in self.guilds:
            guild_id = guild.id
            guild_data = self.options.setdefault(guild_id, {})
            for option_name, (long_name, default_value, description) in option_types.items():
                if option_name not in guild_data:
                    guild_data[option_name] = default_value
                    async with self.conn.execute("""INSERT INTO OPTIONS(GUILD_ID, OPTION_NAME, ENABLED) VALUES (?, ?, ?)""",
                                                 [guild_id, option_name, default_value]):
                        pass

    async def on_guild_join(self, guild: discord.Guild):
        await self.wait_until_ready()
        await self.get_option_mappings()
        await self.get_guild_stats(guild)
        await self.get_channel(bot_support_join_leave_channel_id).send("Joined Guild `" + guild.name + "`.")

    async def on_guild_remove(self, guild: discord.Guild):
        await self.get_channel(bot_support_join_leave_channel_id).send("Left Guild `" + guild.name + "`.")

    @staticmethod
    async def on_guild_available(guild: discord.Guild):
        logger.info("Guild avaliable: %s", guild)

    @staticmethod
    async def on_guild_unavailable(guild: discord.Guild):
        logger.warning("Guild unavaliable: %s", guild)

    async def blacklisted(self, guild_id: int, *emojis: str):
        data = self.blacklisted_emojis.get(guild_id, [])
        if not data:
            return False
        for emoji in emojis:
            if emoji in data:
                return True
        return False

    async def get_blacklist_mappings(self):
        self.blacklisted_emojis = {}
        async with self.conn.execute("""SELECT GUILD_ID, EMOJI FROM BLACKLISTED_EMOJIS""") as cursor:
            data = await cursor.fetchall()
        for guild_id, emoji in data:
            guild_data = self.blacklisted_emojis.setdefault(guild_id, [])
            guild_data.append(emoji.lower())

    async def get_disabled_commands(self):
        self.disabled_commands = {}
        async with self.conn.execute("""SELECT GUILD_ID, COMMAND_NAME FROM DISABLED_COMMANDS""") as cursor:
            data = await cursor.fetchall()
        for guild_id, command_name in data:
            l = self.disabled_commands.setdefault(guild_id, [])
            l.append(command_name)

    async def get_disabled_channels(self):
        async with self.conn.execute("""SELECT GUILD_ID, CHANNEL_ID FROM DISABLED_STATS""") as cursor:
            data = await cursor.fetchall()
        self.disabled_stat_channels = {}
        for guild_id, channel_id in data:
            l = self.disabled_stat_channels.setdefault(guild_id, [])
            l.append(channel_id)

    def has_channel(self, name: str):
        async def predicate(ctx: HubContext):
            if not ctx.guild:
                raise discord.ext.commands.CheckFailure(f"The guild does not have a `{name}` guild-channel mapping.")
            if bool(self.get_channel_data(getattr(ctx.guild, "id", None), name)):
                return True
            raise discord.ext.commands.CheckFailure(f"The guild does not have a `{name}` guild-channel mapping.")

        return predicate

    async def check_spoiler(self, msg: discord.Message):
        msg_hash = hash((msg.guild, msg.channel, msg.author, msg.content))
        if not self.get_option(getattr(getattr(msg, "guild", None), "id", None), "invalid_spoiler", allow_dm=True):
            return
        forbidden_to_delete = False
        if (self.INVALID_SPOILER.search(msg.content) or "/spoiler" in msg.content) and msg_hash not in self.spoiler_hashes:
            self.spoiler_hashes.append(msg_hash)
            try:
                await msg.delete()
            except discord.Forbidden:
                forbidden_to_delete = True
            author: Union[discord.User, discord.Member] = msg.author
            warning = self.WARNING if not forbidden_to_delete else self.WARNING_FAIL
            try:
                if len(msg.content) < 1012:
                    embed = Embed(msg, color=discord.Color.red(), title="Invalid Spoiler Sent", description=warning)
                    embed.add_field(name="Message", value=msg.content, inline=False)
                    await author.send(embed=embed)
                    await author.send("```markdown\n{}```".format(msg.content))
                else:
                    embed = Embed(msg, color=discord.Color.red(), title="Invalid Spoiler Sent", description=warning)
                    await author.send(embed=embed)
                    embed2 = Embed(msg, color=discord.Color.red(), title="Message Content", description=msg.content)
                    await author.send(embed=embed2)
                    # embed3 = Embed(msg, color=discord.Color.red(), title="Raw Markdown",description="```markdown\n{}```".format(msg.content))
                    # await author.send(embed=embed3)
                    await author.send("```markdown\n{}```".format(msg.content))
            except discord.Forbidden:
                chan: discord.TextChannel = self.get_channel_data(msg.guild.id, "bot-spam")
                if chan is None:
                    return
                if len(msg.content) < 1012:
                    embed = Embed(msg, color=discord.Color.red(), title="Invalid Spoiler Sent", description=warning)
                    embed.add_field(name="Unable to DM",
                                    value="The bot attempted to DM you this information, but was unable to do so due to a Forbidden error, "
                                          "which means that you have most likely disabled DMs from Guild members. If you want the bot to DM you "
                                          "next time instead of messaging you from the bot spam channel, enable DMs from Guild members.",
                                    inline=False)
                    embed.add_field(name="Message", value=msg.content, inline=False)
                    await author.send(embed=embed)
                    await author.send("```markdown\n{}```".format(msg.content))
                else:
                    embed = Embed(msg, color=discord.Color.red(), title="Invalid Spoiler Sent", description=warning)
                    embed.add_field(name="Unable to DM",
                                    value="The bot attempted to DM you this information, but was unable to do so due to a Forbidden error, "
                                          "which means that you have most likely disabled DMs from Guild members. If you want the bot to DM you "
                                          "next time instead of messaging you from the bot spam channel, enable DMs from Guild members.",
                                    inline=False)
                    await chan.send(embed=embed)
                    embed2 = Embed(msg, color=discord.Color.red(), title="Message Content", description=msg.content)
                    await chan.send(embed=embed2)
                    # embed3 = Embed(msg, color=discord.Color.red(), title="Raw Markdown", description="```markdown\n{}```".format(msg.content))
                    # embed3.set_author(name=str(msg.author), icon_url=msg.author.avatar_url_as(size=4096))
                    # await chan.send(embed=embed3)
                    await chan.send("```markdown\n{}```".format(msg.content))

    async def load_session(self):
        if self._session is None:
            self.session = ReloadingClient(bot=self, connector=aiohttp.TCPConnector(limit_per_host=5, limit=10))

    async def on_ready(self):
        logger.info("Bot ready.")
        print("Bot ready. All future output is going to the log file.")
        async with self.on_ready_wait:
            self.update_stats.start()
            await self.get_option_mappings()
            await self.get_all_stats()

    @staticmethod
    async def loop_stats(ctx: HubContext, loop: discord.ext.tasks.Loop, name: str):
        current_loop = loop.current_loop
        next_iteration = loop.next_iteration
        running = loop.is_running()
        canceling = loop.is_being_cancelled()
        failed = loop.failed()
        embed = Embed(ctx, title=f"{name} Loop", color=discord.Color.green() if running else discord.Color.red())
        fields = [("Current Loop", str(current_loop)),
                  ("Next Iteration",
                   (next_iteration.replace(tzinfo=pytz.UTC).astimezone(NY).strftime("%A, %B %d, %Y at %I:%M:%S %p") if next_iteration else "None")),
                  ("Running", str(running)), ("Cancelling", str(canceling)), ("Failed", str(failed))]
        await send_embeds_fields(ctx, embed, fields)

    async def can_run(self, ctx: HubContext, *, call_once=False):
        message = ctx.message
        if hasattr(message.channel, "guild"):
            perms: discord.Permissions = message.channel.permissions_for(message.channel.guild.get_member(self.user.id))
        else:
            perms: discord.Permissions = discord.Permissions(send_messages=True)
        if self.command_disabled(ctx):
            raise discord.ext.commands.DisabledCommand(f"The `{getattr(ctx.command, 'qualified_name', '')}` command is disabled on this Guild.")
        if self.get_option(getattr(getattr(ctx, "guild", None), "id", None), "bot_spam", allow_dm=True):
            if channel := self.get_channel_data(getattr(getattr(ctx, "guild", None), "id", None), "bot-spam"):
                if ctx.channel != channel and (
                        not getattr(ctx.command, "not_channel_locked", False) and ctx.command.qualified_name.lower() != "help"):
                    raise discord.ext.commands.CheckFailure(f"Commands can only be run in {channel.mention}.")
        if perms.send_messages:
            return await super().can_run(ctx, call_once=call_once)
        else:
            raise discord.ext.commands.BotMissingPermissions(["send_messages"])

    async def ping_time(self, message: discord.Message):
        cur_time = datetime.datetime.utcnow()
        difference = cur_time - message.created_at
        self.pings.append(difference)
        if "{}ping".format(self.command_prefix) in message.content.lower():
            self.ping_timedelta = difference

    async def process_commands(self, message, _hub: Optional[sentry_sdk.Hub] = None):
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        if _hub:
            ctx.hub = _hub
        await self.invoke(ctx)

    async def on_message(self, message: discord.Message, _replay=False, _hub: Optional[sentry_sdk.Hub] = None):
        if _replay:
            return await self.process_commands(message, _hub=_hub)
        coros = [self.ping_time(message)]
        if message.author.bot:
            if ("remove this message with -goaway" in message.content.lower() or "undefinedgoaway" in message.content.lower()) and self.get_option(
                    getattr(getattr(message, "guild", None), "id", None), "paisley_delete") and message.channel.permissions_for(
                message.guild.get_member(self.user.id)).manage_messages:
                logger.debug("Removed Paisley Park ad message.")
                coros.append(message.delete())
            else:
                if getattr(message, "guild", None):
                    coros.extend((self.add_stat_on_message(message), self.check_channel(message)))
        else:
            if getattr(message, "guild", None):
                coros.extend((self.add_stat_on_message(message), self.check_spoiler(message), self.check_channel(message)))
            coros.append(super().on_message(message))
        return await asyncio.gather(*coros)

    async def add_stat_on_message(self, message: discord.Message):
        await self.stats_working_on(message.guild.id).wait()
        await self.add_stat(message)

    @classmethod
    def get_message_content_formatted(cls, content: str):
        lines = []
        for line in content.splitlines(False):
            if match := cls.QUOTE_MARKER.match(line):
                find = match.group(0)
                line.replace(find, find.replace(">", "Quote:"))
            lines.append("> {}".format(line))
        return "\n".join(lines)

    async def increment_commands_processed(self, ctx: HubContext):
        self.commands_processed += 1

    def dispatch(self, event_name: str, *args, **kwargs):
        if not event_name.startswith("socket"):
            self.events[event_name] = self.events.get(event_name, 0) + 1
        super().dispatch(event_name, *args, **kwargs)

    async def on_command(self, ctx: HubContext):
        command_logger.info("", extra={"ctx": ctx})
        async with self.command_lock:
            self.command_counter += 1

    async def invoke(self, ctx: HubContext):
        ctx.hub.add_breadcrumb({"category": "Command Start", "message": "Command has been identified and will be invoked.", "level": "info"})
        return await super().invoke(ctx)

    @discord.ext.tasks.loop(seconds=30)
    async def update_stats(self):
        command_channel: discord.VoiceChannel = self.get_channel(bot_support_stats_total_commands_channel_id)
        old_command_count = int(command_channel.name.lstrip("Total Commands Run: "))
        message_channel: discord.VoiceChannel = self.get_channel(bot_support_stats_total_messages_sent_channel_id)
        old_message_count = int(message_channel.name.lstrip("Total Messages Sent: "))
        async with self.send_lock:
            new_message_count = old_message_count + self.send_counter
            self.send_counter = 0
        async with self.command_lock:
            new_command_count = old_command_count + self.command_counter
            self.command_counter = 0
        try:
            await command_channel.edit(name="Total Commands Run: " + str(new_command_count))
        except discord.errors.HTTPException as e:
            if e.status // 100 != 5:
                raise
            logger.warning("Discord is having server side issues, restoring counts.")
            self.command_counter = new_command_count - old_command_count
        try:
            await message_channel.edit(name="Total Messages Sent: " + str(new_message_count))
        except discord.errors.HTTPException as e:
            if e.status // 100 != 5:
                raise
            logger.warning("Discord is having server side issues, restoring counts.")
            self.send_counter = new_message_count - old_message_count

    @update_stats.error
    async def on_update_stats_error(self, exception: BaseException):
        return await self.on_error("update_stats")

    async def send_message(self, location: discord.TextChannel, static_number: int, message: discord.Message, channel: bool = False,
                           user: discord.Member = None):
        number = static_number
        chan: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel] = message.channel
        if user:
            if channel:
                description = ":tada::partying_face: {} has sent {} messages in {}!".format(user.mention, number, message.channel.mention)
            else:
                description = ":tada::partying_face: {} has sent a total of {} messages to the entire Guild!".format(user.mention, number)
        else:
            if channel:
                description = ":tada::partying_face: There has been a total of {} messages sent to the {} channel!".format(number,
                                                                                                                           message.channel.mention)
            else:
                description = ":tada::partying_face: There has been a total of {} messages sent to the entire guild!".format(number)
        embed = discord.Embed(timestamp=datetime.datetime.utcnow(), title="Message Goal Reached", color=discord.Color.green(),
                              description=description)
        embed.set_footer(text=f"PokestarBot Version {bot_version}")
        embed.set_thumbnail(url=message.author.avatar_url_as(size=4096))
        if user:
            if not channel:
                embed.add_field(name="Channel", value=message.channel.mention)
        else:
            if channel:
                embed.add_field(name="User", value=message.author.mention)
            else:
                embed.add_field(name="Channel", value=message.channel.mention)
                embed.add_field(name="User", value=message.author.mention)
        if len(message.content) < 1000:
            if len(message.content.strip('"').strip("'")):
                content = message.content
            else:
                content = "**No Content.**"
        else:
            content = "**Message too large.**"
        if chan.guild:
            if chan.id in self.disabled_stat_channels.get(chan.guild.id, []):
                content = "**No Content.**"
        embed.add_field(name="Message", value=content)
        embed.add_field(name="Message URL", value=message.jump_url)
        msg = await location.send(embed=embed)
        return msg

    async def check_channel(self, message: discord.Message):
        if message.guild is None:
            return
        guild_id = message.guild.id
        channel_id = message.channel.id
        user_id = message.author.id
        chan = self.get_channel_data(message.guild.id, "message-goals")
        if chan is None:
            return
        await self.stats_working_on(message.guild.id).wait()
        async with self.stats_lock:
            async with self.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==?""",
                                         [guild_id, channel_id]) as cursor:
                msg_sum, = await cursor.fetchone()
            async with self.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==?""",
                                         [guild_id]) as cursor:
                guild_sum, = await cursor.fetchone()
            async with self.conn.execute("""SELECT NUM FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==? AND AUTHOR_ID==?""",
                                         [guild_id, channel_id, user_id]) as cursor:
                user_num, = await cursor.fetchone()
            async with self.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==? AND AUTHOR_ID==?""",
                                         [guild_id, user_id]) as cursor:
                user_guild_sum, = await cursor.fetchone()
            msg_sum_id = f"{guild_id}:{channel_id}"
            guild_sum_id = f"{guild_id}"
            user_num_id = f"{guild_id}:{channel_id}:{user_id}"
            user_guild_sum_id = f"{guild_id}:{user_id}"
        if msg_sum in [100, 250, 500, 750] or (msg_sum % 1000 == 0 and msg_sum > 0):
            if hash(msg_sum_id) not in self.obj_ids or self.obj_ids.setdefault(hash(msg_sum_id), msg_sum) < msg_sum:
                self.obj_ids[hash(msg_sum_id)] = msg_sum
                await self.send_message(chan, msg_sum, message, channel=True)
        if guild_sum % 10000 == 0:
            if hash(guild_sum_id) not in self.obj_ids or self.obj_ids.setdefault(hash(guild_sum_id), guild_sum) < guild_sum:
                self.obj_ids[hash(guild_sum_id)] = guild_sum
                message = await self.send_message(chan, guild_sum, message)
        if user_num in [100, 250, 500, 750] or (user_num % 1000 == 0 and user_num > 0):
            if hash(user_num_id) not in self.obj_ids or self.obj_ids.setdefault(hash(user_num_id), user_num) < user_num:
                self.obj_ids[hash(user_num_id)] = user_num
                await self.send_message(chan, user_num, message, channel=True, user=message.author)
        if user_guild_sum in [100, 250, 500, 750] or (user_guild_sum % 1000 == 0 and user_guild_sum > 0):
            if hash(user_guild_sum_id) not in self.obj_ids or self.obj_ids.setdefault(hash(user_guild_sum_id), user_guild_sum) < user_guild_sum:
                self.obj_ids[hash(user_guild_sum_id)] = user_guild_sum
                await self.send_message(chan, user_guild_sum, message, user=message.author)

    async def on_command_error(self, ctx: HubContext,
                               exception: Union[DiscordDataException, discord.ext.commands.CommandError, BaseException],
                               custom_message: Optional[str] = None):
        if str(exception) in ["attempt to write a readonly database", "unable to open database file"]:
            await self.run_reload()
        if ctx.command:
            command_name = self.command_prefix + getattr(ctx.command, 'qualified_name', '')
        else:
            command_name = "*[No Command]*"
        if isinstance(exception, discord.ext.commands.MissingRequiredArgument):
            embed = Embed(ctx, title="Missing Argument", color=discord.Colour.red(),
                          description="Missing a required parameter. Please view the help command (provided below) to find usage instructions.")
            embed.add_field(name="Parameter", value=exception.param.name)
            embed.add_field(name="Command", value=command_name)
            await ctx.send(embed=embed)
            return await ctx.send_help(ctx.command)
        if isinstance(exception, discord.ext.commands.CommandNotFound):
            embed = Embed(ctx, title="Invalid Command", color=discord.Colour.red(),
                          description=f"An invalid command has been specified. Use `{self.command_prefix}help` to get a valid list of commands.")
            command = ctx.message.content.partition(" ")[0].lstrip(self.command_prefix)
            if ctx.command:
                command_obj: discord.ext.commands.Command = ctx.command
                command = command_obj.name
            embed.add_field(name="Command", value=command)
            if ctx.subcommand_passed:
                embed.add_field(name="Subcommand", value=ctx.subcommand_passed)
            await ctx.send(embed=embed)
            if ctx.subcommand_passed:
                return await ctx.send_help(command)
            return
        if isinstance(exception, discord.ext.commands.BotMissingPermissions):
            if "send_messages" in exception.missing_perms:
                logger.warning("Requested command on channel where bot cannot speak.")
                chan: discord.TextChannel = self.get_channel_data(getattr(ctx.guild, "id", None), "bot-spam")
                if chan is None:
                    return
                embed = Embed(ctx, title="Could Not Speak", color=discord.Colour.red(),
                              description="The bot cannot speak in the channel where the command was requested.")
                embed.add_field(name="Channel", value=ctx.channel.mention)
                embed.add_field(name="Command", value=command_name)
                return await chan.send(ctx.author.mention, embed=embed)
            else:
                msg = exception.args[0] if len(exception.args) > 0 else ""
                embed = Embed(ctx, title="Bot Missing Permissions", description=msg, color=discord.Color.red())
                embed.add_field(name="Command", value=command_name)
                return await ctx.send(embed=embed)
        if isinstance(exception, discord.ext.commands.CheckFailure):
            msg = exception.args[0] if len(exception.args) > 0 else ""
            embed = Embed(ctx, title="Unable To Run Command", description=msg, color=discord.Color.red())
            embed.add_field(name="Command", value=command_name)
            return await ctx.send(embed=embed)
        if isinstance(exception, discord.ext.commands.DisabledCommand):
            embed = Embed(ctx, title="Command is Disabled", description="The given command is disabled.", color=discord.Color.red())
            embed.add_field(name="Command", value=command_name)
            return await ctx.send(embed=embed)
        if isinstance(exception, discord.ext.commands.BadArgument):
            msg = exception.args[0] if len(exception.args) > 0 else ""
            embed = Embed(ctx, title="Invalid Argument Type", description="An invalid type was provided.")
            if match := self.BAD_ARGUMENT.match(msg):
                embed.add_field(name="Expected Type", value=match.group(1))
                embed.add_field(name="Parameter Name", value=match.group(2))
            else:
                embed.add_field(name="Message", value=msg or "None")
            embed.add_field(name="Command", value=command_name)
            await ctx.send(embed=embed)
            return await ctx.send_help(ctx.command)
        if isinstance(exception, discord.ext.commands.BadUnionArgument):
            msg = exception.args[0] if len(exception.args) > 0 else ""
            embed = Embed(ctx, title="Invalid Argument Type", description=msg or "An invalid type was provided.")
            embed.add_field(name="Parameter Name", value=exception.param.name)
            embed.add_field(name="Command", value=command_name)
            fields = []
            for converter, error in zip(exception.converters, exception.errors):
                converter: Type[discord.ext.commands.Converter]
                error: discord.ext.commands.CommandError
                if isinstance(error,
                              (discord.ext.commands.CommandInvokeError, discord.ext.commands.ExtensionFailed, discord.ext.commands.ConversionError)):
                    error = error.original
                fields.append((converter.__name__, str(error)))
            return await send_embeds_fields(ctx, embed, fields)
        if isinstance(exception, discord.ext.commands.CommandOnCooldown):
            msg = exception.args[0] if len(exception.args) > 0 else ""
            embed = Embed(ctx, title="Command On Cooldown", description=msg)
            embed.add_field(name="Command", value=command_name)
            return await ctx.send(embed=embed)
        if isinstance(exception, discord.ext.commands.MaxConcurrencyReached):
            msg = exception.args[0] if len(exception.args) > 0 else ""
            embed = Embed(ctx, title="Too Many Uses", description=msg)
            embed.add_field(name="Command", value=command_name)
            return await ctx.send(embed=embed)
        if isinstance(exception, DiscordDataException):
            embed = Embed(ctx, title=exception.exception_name, description=exception.args[0], color=discord.Color.red())
            if isinstance(exception, TooManyAnimeNames):
                return await send_embeds_fields(ctx, embed, [("Matches", "\n".join(""))])
            elif isinstance(exception, TooManyBrackets):
                pass
            elif isinstance(exception, TooManyWaifuNames):
                pass
            else:
                return await ctx.send(embed=embed)
        if not custom_message:
            meth = logger.exception
        else:
            meth = logger.warning
        if isinstance(exception,
                      (discord.ext.commands.CommandInvokeError, discord.ext.commands.ExtensionFailed, discord.ext.commands.ConversionError)):
            exception = exception.original
        if isinstance(exception, StopCommand):
            logger.debug("Stop Command issued.")
            return
        elif isinstance(exception, asyncio.TimeoutError):
            embed = Embed(ctx, title="Cancelled", description="You did not respond in the given time or requested a cancellation.",
                          color=discord.Color.red())
            return await ctx.send(embed=embed)
        elif isinstance(exception, aiohttp.ClientResponseError):
            embed = Embed(ctx, title="Error On Request", description="There was an error upon your request.", color=discord.Color.red())
            fields = [("URL", exception.request_info.url), ("Error Code", str(exception.status)),
                      ("Message", exception.message)]
            return await send_embeds_fields(ctx, embed, fields)
        meth("Exception in Bot Command:", exc_info=exception)
        await self.report_exception(exception, ctx)
        embed = Embed(ctx, title="Exception During Bot Command", color=discord.Color.red(),
                      description=custom_message or "While processing a bot command, an exception occurred. It has been logged.")
        return await ctx.send(embed=embed)

    async def on_error(self, event_method, *_args, **_kwargs):
        exctype, exc, tb = sys.exc_info()
        logger.debug("Hit on-error!", stack_info=True)
        if str(exc) == "attempt to write a readonly database":
            await self.run_reload()
        user, channel, command, message, ctx = get_context_variables_from_traceback(tb, break_on_message=False)
        if not ctx:
            _, _, _, _, ctx = get_context_variables(break_on_message=False)
        if not ctx:
            with sentry_sdk.push_scope() as scope:
                guild: Optional[discord.Guild] = getattr(channel, "guild", None)
                for key, value in {
                    **self.context_from_user(user, channel), **self.context_from_channel(channel),
                    **self.context_from_guild(guild), **self.context_from_message(message)
                }.items():
                    scope.set_context(key, value)
                for key, value in self.tags_from_values(user, guild, channel, None).items():
                    scope.set_tag(key, value)
                if user:
                    scope.set_user({"id": user.id, "username": user.name + "#" + user.discriminator})
                await self.execute(sentry_sdk.capture_exception, exc, scope=scope)
        else:
            await self.report_exception(exc, ctx)
        logger.exception("Error occurred in event handler %s", event_method)

    async def close(self, self_initiated=False):
        logger.info("Started bot shutdown.")
        if self.session is not None:
            await self.session.close()
        await self.conn.close()
        await super().close()
        try:
            await asyncio.wait_for(asyncio.gather(self.execute(sentry_sdk.Hub.current.client.close, timeout=2),
                                                  self.execute(sentry_sdk.Hub.main.client.close, timeout=2),
                                                  *(self.execute(hub.client.close, timeout=2) for hub in self.hubs)), 2)
        except Exception:
            pass
        logger.debug("Self_initiated: %s", self_initiated)
        logger.info("Bot shutdown has finished, running final cleanup and exit.")
        if self_initiated:
            return

    async def run_reload(self):
        logger.info("Reloading the bot. Calling function: %s", inspect.currentframe().f_back.f_code.co_name, exc_info=True)
        subprocess.Popen([os.path.abspath(os.path.join(__file__, "..", "terminate-process.sh")), str(os.getpid())], close_fds=True)
        os.kill(os.getpid(), 15)  # SIGTERM

    async def on_connect(self):
        logger.info("Bot has connected to Discord.")
        if self.conn is None or not self.conn.is_alive():
            self.conn = await aiosqlite.connect(os.path.abspath(os.path.join(__file__, "..", "database.db")), isolation_level=None)
        startup = [self.pre_create(), self.get_channel_mappings(), self.get_disabled_commands(), self.get_disabled_channels(),
                   self.get_blacklist_mappings()]
        for item in startup:
            await item

    async def on_disconnect(self):
        logger.info("Bot has disconnected from Discord.")

    async def on_resumed(self):
        logger.info("Bot has reconnected to Discord.")

    async def generic_help(self, ctx: HubContext):
        if isinstance(ctx, HubContext):
            ctx.hub.add_breadcrumb(category="Help", message="Did not specify a valid subcommand for the given command.",
                                   data={"command": ctx.command.qualified_name})
        embed = Embed(ctx, title="Subcommand Required", color=discord.Colour.red(), description="A valid subcommand is needed for the given command.")
        embed.add_field(name="Command", value=ctx.command.qualified_name)
        if ctx.subcommand_passed:
            raise discord.ext.commands.CommandNotFound()
        await ctx.send(embed=embed)
        return await ctx.send_help(ctx.command)

    @staticmethod
    def message_properties(message: discord.Message) -> Tuple[int, int, int]:
        author_id = message.author.id
        channel_id = message.channel.id
        guild_id = getattr(message.guild, "id", None) or 0
        return guild_id, channel_id, author_id

    async def add_stat(self, *messages: discord.Message):
        mapping = {}
        data = {}
        messages = list(messages)
        for message in messages:
            channel = message.channel
            if guild := getattr(channel, "guild", None):
                mapping[message] = guild.id
        for message, guild_id in mapping.items():
            props = self.message_properties(message)
            data[props] = data.setdefault(props, 0) + 1
        async with self.stats_lock:
            existing = collections.defaultdict(int)
            for guild_id, channel_id, author_id in data.keys():
                async with self.conn.execute("""SELECT NUM FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==? AND AUTHOR_ID==?""",
                                             [guild_id, channel_id, author_id]) as cursor:
                    num = await cursor.fetchone()
                if num is None:
                    async with self.conn.execute("""INSERT INTO STAT(GUILD_ID, CHANNEL_ID, AUTHOR_ID, NUM) VALUES (?, ?, ?, ?)""",
                                                 [guild_id, channel_id, author_id, 0]):
                        pass
                else:
                    num = num[0]
                    existing[(guild_id, channel_id, author_id)] = num or 0
            async with self.conn.executemany("""UPDATE STAT SET NUM=? WHERE GUILD_ID==? AND CHANNEL_ID==? AND AUTHOR_ID==?""",
                                             [(existing[(guild_id, channel_id, author_id)] + num, guild_id, channel_id, author_id) for
                                              (guild_id, channel_id, author_id), num in data.items()]):
                pass

    async def get_all_stats(self):
        logger.info("Bot is updating message stat cache. Some bot features may be unavailable while this happens.")
        await asyncio.gather(*[self.get_guild_stats(guild) for guild in self.guilds])
        logger.info("Update complete.")

    async def get_guild_stats(self, guild: discord.Guild):
        # channel: discord.TextChannel = self.get_channel_data(getattr(ctx.guild, "id", None), "bot-spam")
        # if channel is None:
        #     return
        # await chan.send("Bot is updating message stat cache. Some bot features may be unavailable while this happens.")
        # msg = await chan.send("[Will be updated] Showing current progress")
        channels = guild.text_channels
        # await msg.edit(
        #    content="(**{:.2f}**%) Gathering stats for channel: {}".format((num / len(channels)) * 100,
        #                                                                   channel.mention if hasattr(channel, "mention") else channel))
        self.stats_working_on(guild.id).clear()
        for num, channel in enumerate(channels):
            async with self.running_stats_lock:
                val = self.running_stats_counter
            while val > 20:
                logger.debug("Waiting for runs to clear up...")
                await asyncio.sleep(5)
                async with self.running_stats_lock:
                    val = self.running_stats_counter
            await self.get_channel_stats(channel)
        self.stats_working_on(guild.id).set()

    async def get_channel_stats(self, channel: discord.TextChannel):
        async with self.running_stats_lock:
            self.running_stats_counter += 1
        try:
            async with self.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==?""",
                                         [getattr(channel.guild, "id", 0), channel.id]) as cursor:
                num, = await cursor.fetchone()
                if num is None:
                    num = 0
                logger.debug("Channel %s: %s counted so far", channel, num)
                if num <= 5:
                    logger.debug("Working on channel %s (guild %s)", channel, channel.guild)
                else:
                    return
            msg_cache = []
            async for message in channel.history(limit=None, oldest_first=True):
                msg_cache.append(message)
                if len(msg_cache) == 100:
                    await self.add_stat(*msg_cache)
                    msg_cache = []
                del message
            if msg_cache:
                await self.add_stat(*msg_cache)
        except discord.DiscordException:
            return
        else:
            logger.debug("Finished collecting stats for %s", channel)
        finally:
            async with self.running_stats_lock:
                self.running_stats_counter -= 1

    async def remove_channel(self, channel: Union[
        discord.TextChannel, discord.VoiceChannel, discord.DMChannel, discord.GroupChannel, discord.CategoryChannel], _from_stat_reset: bool = False):
        if not isinstance(channel, discord.TextChannel) or not self.get_channel_data(getattr(channel.guild, "id", None), "message-goals"):
            return
        guild_id = getattr(channel.guild, "id", 0)
        async with self.conn.execute("""DELETE FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==?""", [guild_id, channel.id]):
            pass
        if _from_stat_reset:
            pass  # No purpose yet


def main():
    lock_path = os.path.abspath(os.path.join(__file__, "..", "bot.lock"))
    if False and os.path.exists(lock_path): # shut up I don't care
        logger.error(
            "Bot already running. Please either shutdown the other bot (with the %kill command) or delete the bot.lock file if the program crashed.")
        print(
            "Bot already running. Please either shutdown the other bot (with the %kill command) or delete the bot.lock file if the program crashed.")
        sys.exit(1)
    else:
        open(lock_path, "w").close()

        @atexit.register
        def delete_lock_file():
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                return
    try:
        pokestarbot_instance = PokestarBot()
    except Exception:
        logger.error("Critical error occured during bot initialization. Bot will be exiting.", exc_info=True)
        print("Critical error occured during bot initialization. Bot will be exiting. Check bot.log for details", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    else:
        pokestarbot_instance.run(TOKEN)
