import asyncio
import itertools
import logging
import os
import signal
import sqlite3
from typing import List, Optional, TYPE_CHECKING, Union

import aiosqlite
import discord.ext.commands

from . import PokestarBotCog
from .. import base
from ..const import CHANNEL_TYPE, channel_types, hideable_channel_types, log_line, option_types, writeable_channel_types
from ..utils import Embed, admin_or_bot_owner, break_into_groups, send_embeds, send_embeds_fields, HubContext

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Management(PokestarBotCog):
    log_line = log_line

    CHANNELS = channel_types

    @discord.ext.commands.command(brief="Kill the bot")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def kill(self, ctx: HubContext):
        embed = Embed(ctx, title="Killing Bot", color=discord.Color.green())
        await ctx.send(embed=embed)
        logger.info("Killing the bot with signal SIGINT.")
        os.kill(os.getpid(), signal.SIGINT)

    @discord.ext.commands.command(brief="Reload the bot with an UNIX exec command")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def reload(self, ctx: HubContext):
        embed = Embed(ctx, title="Reloading Bot", color=discord.Color.green())
        await ctx.send(embed=embed)
        await self.bot.run_reload()

    @discord.ext.commands.command(brief="Fetch bot logs.", usage="number")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def logs(self, ctx: HubContext, number: int = 20):
        ctx.hub.add_breadcrumb(category="Logs", message=f"Fetching {number} log entries.", level="debug")
        with open(os.path.join(base, "bot.log"), "r", encoding="utf-8") as logfile:
            lines = logfile.read().splitlines(False)
        lines.reverse()
        send_lines = []
        counter = 0
        for line in lines:
            send_lines.append(line)
            if self.log_line.search(line):
                counter += 1
            if counter == number:
                break
        send_lines.reverse()
        groups = await break_into_groups("\n".join(send_lines), template="```\n")
        embed = Embed(ctx, title="Log Lines")
        embed.add_field(name="Amount Requested", value=str(number), inline=False)
        await send_embeds(ctx, embed, groups)

    @discord.ext.commands.command(brief="Resets the bot's permission overrides", enabled=False)
    @admin_or_bot_owner()
    @discord.ext.commands.bot_has_guild_permissions(manage_channels=True)
    async def reset_perms(self, ctx: HubContext):
        channels = []
        for channel in ctx.guild.channels:
            channel: discord.abc.GuildChannel
            user_role_checks: List[Union[discord.Member, discord.Role]] = [ctx.me]
            if ctx.me.guild_permissions.manage_roles:
                for role in ctx.guild.roles:
                    if role.name == ctx.me.name and role in ctx.me.roles:
                        user_role_checks.append(user_role_checks)
            for item in user_role_checks:
                values = {value for name, value in channel.overwrites_for(item)}
                if values != {None}:
                    to_append = channel.mention if isinstance(channel, discord.TextChannel) else str(channel)
                    if to_append not in channels:
                        channels.append(to_append)
                    ctx.hub.add_breadcrumb(category="Permissions", message=f"Deleting overrides for {item} in {str(channel)}", data={"channel_id": channel.id, "is_member": bool(isinstance(item, discord.Member)), "item_id": item.id})
                    await channel.set_permissions(ctx.me, overwrite=None, reason="Resetting channel overrides")
        embed = Embed(ctx, title="Permission Reset Successful", color=discord.Color.green(), description="The permission reset was successful.")
        embed.add_field(name="Number of Channels Reset", value=str(len(channels)))
        await send_embeds_fields(ctx, embed, [("Channels Reset", "\n".join(channels))])

    @discord.ext.commands.group(brief="Work with the guild-channel database", usage="subcommand", invoke_without_command=True, significant=True)
    @admin_or_bot_owner()
    async def channel(self, ctx: HubContext):
        return await self.bot.generic_help(ctx)

    @channel.command(name="add", brief="Add channel to the guild-channel database", usage="name [channel]", significant=True)
    @discord.ext.commands.has_guild_permissions(manage_channels=True)
    async def channel_add(self, ctx: HubContext, name: str,
                          channel: Optional[Union[discord.TextChannel, discord.CategoryChannel, discord.VoiceChannel]] = None):
        if channel is None:
            channel = ctx.channel
        guild = ctx.guild
        ctx.hub.add_breadcrumb(category="Channel Mapping", message=f"Setting channel {str(channel)} for {name!r}", data={"channel_id": channel.id, "channel_type": type(channel), "guild_id": ctx.guild.id})
        options = list(itertools.chain(*self.CHANNELS.values()))
        if name not in options:
            embed = Embed(ctx, title="Channel Type not in Supported Guild-Channel Mappings",
                          description=f"The specified name is not in the list of valid Guild-Channel Mappings. Use `"
                                      f"{self.bot.command_prefix}channel list` to get a list of valid names.",
                          color=discord.Color.red())
            embed.add_field(name="Provided Name", value=name)
            return await ctx.send(embed=embed)
        try:
            async with self.bot.conn.execute("""INSERT INTO CHANNEL_DATA(GUILD_ID, CHANNEL_NAME, CHANNEL_ID) VALUES (?, ?, ?)""",
                                             [guild.id, name, channel.id]):
                pass
        except aiosqlite.IntegrityError:
            embed = Embed(ctx, title="Guild-Channel Mapping Already Exists", description="The channel name for this guild already exists.",
                          color=discord.Color.red())
            embed.add_field(name="Guild ID", value=str(guild.id))
            embed.add_field(name="Channel Name", value=name)
            embed.add_field(name="Channel", value=channel.mention)
            await ctx.send(embed=embed)
        else:
            ctx.hub.add_breadcrumb(category="Channel Mapping", message="Updating bot channel mappings.", level="debug")
            coros = [self.bot.get_channel_mappings()]
            embed = Embed(ctx, title="Guild-Channel Mapping Added", description="The channel name for this guild has been added.",
                          color=discord.Color.green())
            embed.add_field(name="Guild ID", value=str(guild.id))
            embed.add_field(name="Channel Name", value=name)
            embed.add_field(name="Channel", value=channel.mention)
            coros.append(ctx.send(embed=embed))
            await asyncio.gather(*coros)

    @channel.command(name="remove", brief="Delete the channel in the guild-channel database", usage="name", aliases=["delete"], significant=True)
    @discord.ext.commands.has_guild_permissions(manage_channels=True)
    async def channel_remove(self, ctx: HubContext, name: str):
        guild = ctx.guild
        ctx.hub.add_breadcrumb(category="Channel Mapping", message=f"Removing the {name!r} channel mapping.", data={"guild_id": ctx.guild.id})
        async with self.bot.conn.execute("""DELETE FROM CHANNEL_DATA WHERE GUILD_ID==? AND CHANNEL_NAME==?""", [guild.id, name]):
            pass
        ctx.hub.add_breadcrumb(category="Channel Mapping", message="Updating bot channel mappings.", level="debug")
        coros = [self.bot.get_channel_mappings()]
        embed = Embed(ctx, title="Guild-Channel Mapping Deleted", description="The channel name for this guild has been deleted.",
                      color=discord.Color.green())
        embed.add_field(name="Guild ID", value=str(guild.id))
        embed.add_field(name="Channel Name", value=name)
        coros.append(ctx.send(embed=embed))
        await asyncio.gather(*coros)

    @channel.command(name="list", brief="Get the list of possible channels that a guild can contain.")
    @discord.ext.commands.guild_only()
    async def channel_list(self, ctx: HubContext):
        embed = Embed(ctx, title="Channel List",
                      description="The possible Guild-Channel Mapping types, as well as the channel, if the mapping exists for the current Guild, "
                                  "is listed.")
        async with self.bot.conn.execute("""SELECT CHANNEL_NAME, CHANNEL_ID FROM CHANNEL_DATA WHERE GUILD_ID==?""",
                                         [getattr(ctx.guild, "id", None)]) as cursor:
            data = dict(await cursor.fetchall())
        fields = []
        for group_name, item_list in self.CHANNELS.items():
            items = []
            for name in item_list:
                chan = ctx.guild.get_channel(data.pop(name, 1))
                str_chan = chan.mention if chan else "None"
                items.append(f"**{name}**: {str_chan}")
            fields.append((group_name, "\n".join(items) or "None"))
        if data:
            items = []
            for name, channel_id in data.items():
                chan = ctx.guild.get_channel(channel_id)
                str_chan = chan.mention if chan else "None"
                items.append(f"**{name}**: {str_chan}")
            fields.append(("Extra Items For Guild (Should Be Deleted)", "\n".join(items) or "None"))
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.group(brief="Disable a command (or subcommand) for the Guild", usage="command", invoke_without_command=True,
                                significant=True)
    @admin_or_bot_owner()
    async def disable(self, ctx: HubContext, *, command: str):
        if command.startswith(self.bot.command_prefix):
            command = command[len(self.bot.command_prefix):]
        if command.startswith("enable"):
            return await ctx.send(embed=Embed(ctx, title="Cannot Disable the Enable command",
                                              description=f"The `{self.bot.command_prefix}enable` command cannot be disabled.",
                                              color=discord.Color.red()))
        command_obj = self.bot.get_command(command)
        if command_obj is None:
            embed = Embed(ctx, title="Command Does Not Exist", description="The provided command does not exist.", color=discord.Color.red())
            embed.add_field(name="Command", value=command)
            await ctx.send(embed=embed)
            return await ctx.send_help()
        try:
            ctx.hub.add_breadcrumb(category="Commands", message=f"Disabling command {command_obj.qualified_name!r}", data={"guild_id": ctx.guild.id})
            async with self.bot.conn.execute("""INSERT INTO DISABLED_COMMANDS(GUILD_ID, COMMAND_NAME) VALUES (?, ?)""",
                                             [getattr(ctx.guild, "id", None), command_obj.qualified_name]):
                pass
        except sqlite3.IntegrityError:
            embed = Embed(ctx, title="Command Already Disabled", description="The given command is already disabled for the Guild.",
                          color=discord.Color.red())
            embed.add_field(name="Command", value=command_obj.qualified_name)
            await ctx.send(embed=embed)
        else:
            embed = Embed(ctx, title="Command Disabled", description="The given command is disabled for the Guild.",
                          color=discord.Color.green())
            embed.add_field(name="Command", value=command_obj.qualified_name)
            await ctx.send(embed=embed)
            ctx.hub.add_breadcrumb(category="Commands", message=f"Getting the disabled command list.", level="debug")
            await self.bot.get_disabled_commands()

    @disable.command(name="list", brief="Get the list of disabled commands")
    @discord.ext.commands.guild_only()
    async def disable_commands(self, ctx: HubContext):
        async with self.bot.conn.execute("""SELECT COMMAND_NAME FROM DISABLED_COMMANDS WHERE GUILD_ID==?""",
                                         [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        names = [f"{self.bot.command_prefix}{name}" for name, in data]
        embed = Embed(ctx, title="Disabled Commands", color=discord.Color.green() if len(names) == 0 else discord.Color.red())
        await send_embeds_fields(ctx, embed, [("\u200B", "\n".join(names) or "None")])

    @discord.ext.commands.command(brief="Enable a command (or subcommand) for the Guild", usage="command", significant=True)
    @admin_or_bot_owner()
    async def enable(self, ctx: HubContext, *, command: str):
        command = self.bot.get_command(command)
        command_obj = self.bot.get_command(command)
        if command_obj is None:
            embed = Embed(ctx, title="Command Does Not Exist", description="The provided command does not exist.", color=discord.Color.red())
            embed.add_field(name="Command", value=command)
            await ctx.send(embed=embed)
            return await ctx.send_help()
        ctx.hub.add_breadcrumb(category="Commands", message=f"Enabling command {command_obj.qualified_name!r}", data={"guild_id": ctx.guild.id})
        async with self.bot.conn.execute("""DELETE FROM DISABLED_COMMANDS WHERE GUILD_ID==? AND COMMAND_NAME==?""",
                                         [getattr(ctx.guild, "id", None), command_obj.qualified_name]):
            pass
        embed = Embed(ctx, title="Command Enabled", description="The given command is enabled for the Guild.", color=discord.Color.green())
        embed.add_field(name="Command", value=command_obj.qualified_name)
        await ctx.send(embed=embed)
        ctx.hub.add_breadcrumb(category="Commands", message=f"Getting the disabled command list.", level="debug")
        await self.bot.get_disabled_commands()

    @discord.ext.commands.command(brief="Setup the bot channels", significant=True)
    @admin_or_bot_owner()
    async def setup(self, ctx: HubContext):
        embed = Embed(ctx, title="Instructions",
                      description="You will be prompted with the various channel types for the bot, and you should reply with the text channel for "
                                  "it. For example, if you get prompted for the 'example' channel type, type `#example` to link that type to the "
                                  "example channel. There are certain words you can type. The fields include the special words you can type. If a "
                                  "word is in `<>`, that means you substitute a value. The **Existing Channel** is *not* a special word. Now, "
                                  "type `y` to start.")
        await ctx.send(embed=embed)
        await self.bot.wait_for("message",
                                check=lambda message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                                    "y", "yes", "1", "continue", "cont"], timeout=60)
        async with self.bot.conn.execute("""SELECT CHANNEL_NAME, CHANNEL_ID FROM CHANNEL_DATA WHERE GUILD_ID==?""",
                                         [getattr(ctx.guild, "id", None)]) as cursor:
            data = dict(await cursor.fetchall())
        for item in self.CHANNELS.values():
            for channel_type, (description, channel_type_to_create) in item.items():
                type_embed = Embed(ctx, title=channel_type, description=description)
                chan = ctx.guild.get_channel(data.pop(channel_type, 1))
                str_chan = chan.mention if chan else "None"
                type_embed.add_field(name="Existing Channel", value=str_chan)
                type_embed.add_field(name="<Channel Name>", value="The name of the channel. Can be in `#channel`, `channel` or `channel_id` formats.")
                type_embed.add_field(name="Skip", value="Skips this channel.")
                type_embed.add_field(name="Stop", value="Stops the setup.")
                type_embed.add_field(name="Create",
                                     value="Create a new channel with the provided name (Requires bot to have Manage Channels permission).")
                type_embed.add_field(name="Delete", value="If there is an existing channel, delete the channel association.")
                type_embed.add_field(name="Repeat", value="Repeat this message.")
                await ctx.send(embed=type_embed)
                while True:
                    message: discord.Message = await self.bot.wait_for("message", check=lambda
                        message: message.author == ctx.author and message.channel == ctx.channel, timeout=120)
                    content = message.content.lower()
                    if content == "skip":
                        break
                    elif content == "stop":
                        raise asyncio.TimeoutError
                    elif content == "create":
                        if not ctx.me.guild_permissions.manage_channels:
                            raise discord.ext.commands.BotMissingPermissions(["manage_channels"])
                        if channel_type_to_create == CHANNEL_TYPE.TEXT_CHANNEL:
                            channel: discord.TextChannel = await ctx.guild.create_text_channel(channel_type, reason=f"Bot Setup by {ctx.author}")
                        elif channel_type_to_create == CHANNEL_TYPE.CATEGORY_CHANNEL:
                            channel: discord.CategoryChannel = await ctx.guild.create_category_channel(channel_type,
                                                                                                       reason=f"Bot Setup by {ctx.author}")
                        elif channel_type_to_create == CHANNEL_TYPE.VOICE_CHANNEL:
                            channel: discord.VoiceChannel = await ctx.guild.create_voice_channel(channel_type, reason=f"Bot Setup by {ctx.author}")
                        else:
                            raise ValueError("Not in the Channel Types.")
                        if channel in hideable_channel_types:
                            await channel.set_permissions(ctx.guild.default_role, reason="Denying @everyone read perms", read_messages=False)
                        elif channel_type not in writeable_channel_types:
                            await channel.set_permissions(ctx.guild.default_role, reason="Denying @everyone speak perms", send_messages=False)
                        await self.channel_add(ctx, channel_type, channel)
                        break
                    elif content == "delete":
                        if not ctx.me.guild_permissions.manage_channels:
                            raise discord.ext.commands.BotMissingPermissions(["manage_channels"])
                        await self.channel_remove(ctx, channel_type)
                        break
                    elif content == "repeat":
                        await ctx.send(embed=type_embed)
                    else:
                        try:
                            if channel_type_to_create == CHANNEL_TYPE.TEXT_CHANNEL:
                                channel: discord.TextChannel = await discord.ext.commands.TextChannelConverter().convert(ctx, message.content)
                            elif channel_type_to_create == CHANNEL_TYPE.CATEGORY_CHANNEL:
                                channel: discord.TextChannel = await discord.ext.commands.CategoryChannelConverter().convert(ctx, message.content)
                            elif channel_type_to_create == CHANNEL_TYPE.VOICE_CHANNEL:
                                channel: discord.TextChannel = await discord.ext.commands.VoiceChannelConverter().convert(ctx, message.content)
                            else:
                                raise ValueError("Not in the Channel Types.")
                        except discord.ext.commands.BadArgument:
                            embed = Embed(ctx, title="Invalid Channel Name",
                                          description="The provided channel name is invalid. Pass a valid channel name or one of the special "
                                                      "words from above. Pass `repeat` to get the list of special words.",
                                          color=discord.Color.red())
                            return await ctx.send(embed=embed)
                        await self.channel_add.fully_run_command(ctx, channel_type, channel)
                        break
        type_embed_2 = Embed(ctx, title="Instructions Part 2",
                             description="You will be prompted with server options. Type one of the special words below to perform the listed "
                                         "action. Now, type `y` to start.")
        type_embed_2.add_field(name="Enable", value="Enable this server option.")
        type_embed_2.add_field(name="Disable", value="Disable this server option.")
        type_embed_2.add_field(name="Skip", value="Skips this option.")
        type_embed_2.add_field(name="Stop", value="Stops the setup.")
        type_embed_2.add_field(name="Repeat", value="Repeat this message.")
        await ctx.send(embed=type_embed_2)
        await self.bot.wait_for("message",
                                check=lambda message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                                    "y", "yes", "1", "continue", "cont"], timeout=60)
        for item in option_types.keys():
            await self.option_info.fully_run_command(ctx, option_name=item, _fields=type_embed_2._fields)
            while True:
                message: discord.Message = await self.bot.wait_for("message",
                                                                   check=lambda
                                                                       message: message.author == ctx.author and message.channel == ctx.channel,
                                                                   timeout=120)
                content = message.content.lower()
                if content == "skip":
                    break
                elif content == "stop":
                    raise asyncio.TimeoutError
                elif content == "repeat":
                    await self.option_info.fully_run_command(ctx, option_name=item, _fields=type_embed_2._fields)
                elif content == "enable":
                    await self.option_enable(ctx, option_name=item)
                    break
                elif content == "disable":
                    await self.option_disable(ctx, option_name=item)
                    break
                else:
                    embed = Embed(ctx, title="Invalid Operation", description="The operation is not invalid. Please state a valid operation.")
                    await ctx.send(embed=embed)
                    await self.option_info.fully_run_command(ctx, option_name=item, _fields=type_embed_2._fields)
        embed = Embed(ctx, title="Complete", description="Setup is complete.", color=discord.Color.green())
        await ctx.send(embed=embed)

    @discord.ext.commands.group(brief="Manage Server Options", aliases=["options"], invoke_without_command=True)
    @admin_or_bot_owner()
    async def option(self, ctx: HubContext):
        await self.bot.generic_help(ctx)

    @option.command(name="enable", brief="Enable an option.", usage="option_name")
    @admin_or_bot_owner()
    async def option_enable(self, ctx: HubContext, *, option_name: str):
        if option_name not in option_types:
            embed = Embed(ctx, title="Invalid Option",
                          description=f"The option is invalid. Use `{self.bot.command_prefix}option list` to get a list of valid option names.",
                          color=discord.Color.red())
            embed.add_field(name="Option Name", value=option_name)
            await ctx.send(embed=embed)
        else:
            ctx.hub.add_breadcrumb(category="Options", message=f"Enabling option {option_name!r}", data={"guild_id": ctx.guild.id})
            async with self.bot.conn.execute("""UPDATE OPTIONS SET ENABLED=? WHERE GUILD_ID==? AND OPTION_NAME==?""",
                                             [True, getattr(ctx.guild, "id", None), option_name]):
                pass
            embed = Embed(ctx, title="Option Enabled", description="The option was enabled.", color=discord.Color.green())
            embed.add_field(name="Option Name", value=option_name)
            await ctx.send(embed=embed)
            ctx.hub.add_breadcrumb(category="Options", message=f"Getting the option list.", level="debug")
            await self.bot.get_option_mappings()

    @option.command(name="disable", brief="Disable an option.", usage="option_name")
    @admin_or_bot_owner()
    async def option_disable(self, ctx: HubContext, *, option_name: str):
        if option_name not in option_types:
            embed = Embed(ctx, title="Invalid Option",
                          description=f"The option is invalid. Use `{self.bot.command_prefix}option list` to get a list of valid option names.",
                          color=discord.Color.red())
            embed.add_field(name="Option Name", value=option_name)
            await ctx.send(embed=embed)
        else:
            ctx.hub.add_breadcrumb(category="Options", message=f"Disabling option {option_name!r}", data={"guild_id": ctx.guild.id})
            async with self.bot.conn.execute("""UPDATE OPTIONS SET ENABLED=? WHERE GUILD_ID==? AND OPTION_NAME==?""",
                                             [False, getattr(ctx.guild, "id", None), option_name]):
                pass
            embed = Embed(ctx, title="Option Disabled", description="The option was disabled.", color=discord.Color.green())
            embed.add_field(name="Option Name", value=option_name)
            await ctx.send(embed=embed)
            ctx.hub.add_breadcrumb(category="Options", message=f"Getting the option list.", level="debug")
            await self.bot.get_option_mappings()

    @option.command(name="list", brief="List all options.")
    @discord.ext.commands.guild_only()
    async def option_list(self, ctx: HubContext):
        embed = Embed(ctx, title="Options", description="This Embed contains the option")
        await send_embeds_fields(ctx, embed, list(self.bot.options[getattr(ctx.guild, "id", None)].items()))

    @option.command(name="info", brief="Get information about an option", usage="option_name")
    @discord.ext.commands.guild_only()
    async def option_info(self, ctx: HubContext, *, option_name: str, _fields: Optional[list] = None):
        if option_name not in option_types:
            embed = Embed(ctx, title="Invalid Option",
                          description=f"The option is invalid. Use `{self.bot.command_prefix}option list` to get a list of valid option names.",
                          color=discord.Color.red())
            embed.add_field(name="Option Name", value=option_name)
            await ctx.send(embed=embed)
        else:
            ctx.hub.add_breadcrumb(category="Options", message=f"Getting option {option_name!r}", data={"guild_id": ctx.guild.id})
            val = self.bot.options[ctx.guild.id][option_name]
            long_name, default, description = option_types[option_name]
            embed = Embed(ctx, title=f"{long_name} ({option_name})", description=description,
                          color=discord.Color.green() if val else discord.Color.red())
            embed.add_field(name="Default Value", value=str(default))
            embed.add_field(name="Enabled for Guild", value=str(val))
            embed._fields += (_fields or [])
            await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Delete any mention of a Guild", usage="guild_id")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def delete_guild(self, ctx: HubContext, guild_id: int):
        count = 0
        async with self.bot.conn.execute("""SELECT NAME FROM SQLITE_MASTER WHERE TYPE='table'""") as cursor:
            tables = [name async for name, in cursor]
        for table in tables:
            async with self.bot.conn.execute(f"""SELECT * FROM {table}""") as cursor:
                column_names = [item[0] for item in cursor.description]
                rows = await cursor.fetchall()
            for row in rows:
                to_break = False
                for num, column in enumerate(row):
                    if column == guild_id:
                        name = column_names[num]
                        ctx.hub.add_breadcrumb(category="Deletion", message=f"Deleting all records from {table!r} where field {name!r} is equal to Guild ID {guild_id}.")
                        async with self.bot.conn.execute(f"""DELETE FROM {table} WHERE {name}==?""", [guild_id]):
                            count += 1
                            to_break = True
                if to_break:
                    break
        embed = Embed(ctx, title="Guild Deleted", description=f"Guild with ID {guild_id} has been wiped from all database entries.",
                      color=discord.Color.green())
        embed.add_field(name="Delete Operations Ran", value=str(count))
        await self.bot.execute(ctx.hub.capture_message("Deleted Guild from bot tables"))
        return await ctx.send(embed=embed)


def setup(bot: "PokestarBot"):
    bot.add_cog(Management(bot))
    logger.info("Loaded the Management extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Management extension.")
