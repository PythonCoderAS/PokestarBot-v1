import asyncio
import datetime
import importlib
import io
import itertools
import logging
import os
import re
import pyparsing
import string
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, Union

import discord.ext.commands
import discord.ext.tasks
import owotext
import pytz

from . import PokestarBotCog
from ..const import strftime_format
from ..creds import owner, repo, support_code
from ..utils import Embed, break_into_groups, post_issue, send_embeds, send_embeds_fields, latex_as_png, HubContext

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)

NY = pytz.timezone("America/New_York")


class Misc(PokestarBotCog):
    STRFTIME_FORMAT = strftime_format
    OWO = owotext.OwO()

    @discord.ext.commands.command(brief="Say the message `num` times", usage="num message", enabled=False)
    async def echo(self, ctx: HubContext, num: int, *, message: str):
        if not ctx.author.guild_permissions.administrator and num > 5:
            embed = Embed(ctx, title="Too Many Echoes", description="You hit the echo limit.", color=discord.Color.red())
            embed.add_field(name="Echoes Requested", value=str(num))
            embed.add_field(name="Max Echoes", value=str(5))
            return await ctx.send(embed=embed)
        if num > 50:
            embed = Embed(ctx, title="Too Many Echoes", description="You hit the echo limit.", color=discord.Color.red())
            embed.add_field(name="Echoes Requested", value=str(num))
            embed.add_field(name="Max Echoes", value=str(50))
            return await ctx.send(embed=embed)
        for i in range(num):
            await ctx.send(message)

    @discord.ext.commands.command(brief="Get the time between sending the message and command processing.")
    async def ping(self, ctx: HubContext):
        td = self.bot.ping_timedelta
        ms_list = [int(delta.total_seconds() * 1000) for delta in self.bot.pings]
        avg = sum(ms_list) // len(ms_list)
        embed = Embed(ctx, title="Bot Ping")
        embed.add_field(name="Ping (s)", value=str(td))
        embed.add_field(name="Ping (ms)", value=str(int(td.total_seconds() * 1000)))
        embed.add_field(name="Average Ping", value=str(avg))
        embed.add_field(name="Message Sample", value=str(len(ms_list)))
        await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Send the last image message with a spoiler.", usage="[spoiler_text]", aliases=["spoilermsg"],
                                  not_channel_locked=True)
    @discord.ext.commands.bot_has_guild_permissions(manage_messages=True)
    async def spoiler_msg(self, ctx: HubContext, spoiler_text: Optional[bool] = False):
        ctx.hub.add_breadcrumb(category="History", message="Getting previous image post in order to spoiler.", data={"user": str(ctx.author), "extra_text": spoiler_text})
        async for message in ctx.history(limit=None, before=ctx.message.created_at).filter(lambda msg: msg.author == ctx.author).filter(lambda msg: msg.attachments):
            ctx.hub.add_breadcrumb(category="History", message="Found message that met criteria", data={"message_id": message.id, "message_link": message.jump_url})
            content = message.content
            attachments = message.attachments
            files = []
            for attachment in attachments:
                attachment: discord.Attachment
                file = io.BytesIO()
                await attachment.save(file)
                files.append(discord.File(file, filename=attachment.filename, spoiler=True))
            if spoiler_text:
                if len(content) >= 1996:
                    return await ctx.send(embed=Embed(ctx, title="Message Too Large", description="The message is too large.", color=discord.Color.red()))
                else:
                    content = f"||{content}||"
            await ctx.send(content=content, files=files)
            await message.delete()
            break

    async def expand_message(self, message: discord.Message):
        if getattr(message, "guild", None) and not message.channel.permissions_for(message.guild.get_member(self.bot.user.id)).send_messages:
            return
        if len(message.attachments) == 1:
            ctx = await self.bot.get_context(message)
            attachment = message.attachments[0]
            ctx.hub.add_breadcrumb(category="Attachments", message="Found attachment", data={"attachment": attachment})
            if not attachment.filename == "message.txt":
                return
            try:
                data = await attachment.read()
            except discord.NotFound:
                return
            except discord.HTTPException as e:
                return logger.warning("Fetching of asset failed", exc_info=e)
            else:
                try:
                    text = data.decode()
                except UnicodeDecodeError:
                    return
            embed = Embed(message, title="Expanded Message", color=discord.Color.green())
            fields = [("User", message.author.mention), ("Content", text)]
            return await send_embeds_fields(await self.bot.get_context(message), embed, fields)

    @discord.ext.commands.command(brief="Get the emoji for a specific letter", usage="letter [letter]", enabled=False)
    async def letter(self, ctx: HubContext, *letters: str):
        if len(letters) == 0:
            self.bot.missing_argument("letter")
        letrz = []
        s = []
        for letter in letters:
            letter = letter.lower()
            if letter == "all":
                letrz.extend(string.ascii_lowercase)
            elif letter not in string.ascii_lowercase or len(letter) > 1:
                embed = Embed(ctx, title="Non-letter", description="The provided character is not a letter.", color=discord.Color.red())
                embed.add_field(name="Character", value=letter)
                await ctx.send(embed=embed)
            else:
                letrz.append(letter)
        for letter in sorted(set(letrz)):
            s.append(f":regional_indicator_{letter}:")
        await send_embeds_fields(ctx, Embed(ctx, title="Letter Emojis"), ["\n".join(s)])

    @discord.ext.commands.command(brief="Convert between number bases", usage="base_from base_to num [num]")
    async def convert(self, ctx: HubContext, base_from: Union[int, str], base_to: Union[int, str], *numbers: str):
        if len(numbers) == 0:
            self.bot.missing_argument("number")
        else:
            if isinstance(base_from, str):
                base_from = base_from.lower()
                if base_from in ["binary", "bin", "base2", "basetwo"]:
                    base_from = 2
                elif base_from in ["base10", "int", "integer", "decimal", "baseten"]:
                    base_from = 10
                elif base_from in ["hex", "hexadecimal", "base16", "basesixteen"]:
                    base_from = 16
                else:
                    raise discord.ext.commands.BadArgument("base_from must be one of `binary`, `decimal` or `hexadecimal`")
            if not (2 <= base_from <= 36 or base_from == 0):
                raise discord.ext.commands.BadArgument("base_from must be between `2` and `36`, including `2` and `36`.")
            if isinstance(base_to, str):
                base_to = base_to.lower()
                if base_to in ["binary", "bin", "base2"]:
                    base_to = 2
                elif base_to in ["base10", "int", "integer", "decimal"]:
                    base_to = 10
                elif base_to in ["hex", "hexadecimal", "base16"]:
                    base_to = 16
                else:
                    raise discord.ext.commands.BadArgument("base_to must be one of `binary`, `decimal` or `hexadecimal`")
            if base_to not in [2, 10, 16]:
                raise discord.ext.commands.BadArgument("base_to must be one of `2`, `10` or `16`")
            if base_to == 2:
                func = bin
            elif base_to == 10:
                func = int
            elif base_to == 16:
                func = hex
            else:
                raise ValueError("base_to must be one of `2`, `10` or `16`")
            failed = []
            fields = [("Converting From Base", str(base_from)), ("Converting To Base", str(base_to))]
            for number in numbers:
                try:
                    fields.append((number, str(func(int(number, base=base_from)))))
                except ValueError:
                    failed.append(number)
            embed = Embed(ctx, title="Converted Numbers", color=discord.Color.red() if failed else discord.Color.green())
            fields.append(("Failed", "\n".join(failed)))
            await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.group(name="bot_stats", brief="Random bot stats", invoke_without_command=True)
    async def cmd_bot_stats(self, ctx: HubContext):
        guilds = len(self.bot.guilds)
        users = len({member.id for member in itertools.chain(*(guild.members for guild in self.bot.guilds))})
        commands = self.bot.commands_processed
        events = self.bot.events_processed
        async with self.bot.conn.execute("""SELECT SUM(NUM) FROM STAT""") as cursor:
            num, = await cursor.fetchone()
        embed = Embed(ctx, title="Bot Statistics", color=discord.Color.green())
        embed.add_field(name="Guilds Bot is Part Of", value=str(guilds))
        embed.add_field(name="Unique Users Bot Sees", value=str(users))
        embed.add_field(name="Bot Started Up At",
                        value=(self.bot.started + NY.utcoffset(self.bot.started)).strftime(strftime_format) + " " + NY.tzname(self.bot.started))
        embed.add_field(name="Bot Uptime", value=str(datetime.datetime.utcnow() - self.bot.started))
        embed.add_field(name="Total Counted Messages", value=str(num))
        embed.add_field(name="Commands Used Since Last Restart", value=str(commands))
        embed.add_field(name="Total Bot Events Since Last Restart", value=str(events))
        await ctx.send(embed=embed)

    @cmd_bot_stats.command(name="event", brief="Event stats", usage="[event]")
    async def cmd_bot_stats_event(self, ctx: HubContext, event: Optional[str] = None):
        if event is not None:
            try:
                num = self.bot.events[event]
            except KeyError:
                embed = Embed(ctx, title="Event Does Not Exist (yet)",
                              description=f"The given event is not valid, or has not received by the bot yet. Use `"
                                          f"{self.bot.command_prefix}bot_stats event` to get all of the events the bot has received.",
                              color=discord.Color.red())
                return await ctx.send(embed=embed)
            else:
                embed = Embed(ctx, title=event.replace("_", " ").title(), description=f"The bot has received **{num}** occurrences of this event.",
                              color=discord.Color.green())
                return await ctx.send(embed=embed)
        else:
            fields = [(key, str(value) + " occurrences") for key, value in self.bot.events.items()]
            embed = Embed(ctx, title="Bot Events", color=discord.Color.green())
            return await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(name="issue", significant=True, brief="File an issue with the bot. Please use as much detail as possible.",
                                  usage="description")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.user)
    async def file_issue(self, ctx: HubContext, *, description: str):
        await self.bot.report_message(description, context=ctx, tag_data={"manual": True})
        embed = Embed(ctx, title=f"Your issue has been reported.", description=description, color=discord.Color.green())
        await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Get the plaintext version of a message", usage="message", enabled=False)
    async def plaintext(self, ctx: HubContext, message: discord.Message):
        await ctx.send(embed=Embed(ctx, description=f"```markdown\n{message.content}\n```"))

    @discord.ext.commands.command(brief="Get the link to the bot support server.", significant=True)
    async def support(self, ctx: HubContext):
        await ctx.send(f"https://discord.gg/{support_code}")

    @discord.ext.commands.command(brief="Display the time in various timezones", usage="[timezone]", enabled=False)
    async def time(self, ctx: HubContext, timezone: str = None):
        base_time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        if timezone is None:
            logger.info("Requested default times.")
            timezones = ["America/New_York", "UTC", "Asia/Kolkata", "Asia/Dhaka"]
            fields = []
            for tz in timezones:
                tzobj = pytz.timezone(tz)
                fields.append((tz, base_time.astimezone(tzobj).strftime(self.STRFTIME_FORMAT)))
            embed = Embed(ctx, title="Current Time", description="Here is the current time in **{}** timezones.".format(len(timezones)))
            await send_embeds_fields(ctx, embed, fields)
        else:
            try:
                tz = pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                embed = Embed(ctx, color=discord.Color.red(), title="Invalid Timezone",
                              description="The provided timezone does not exist. Please double check that the timezone exists by doing `{}"
                                          "timezones`.".format(self.bot.command_prefix))
                embed.add_field(name="Timezone", value=timezone)
                await ctx.send(embed=embed)
            else:
                logger.info("Requested time in %s", timezone)
                await ctx.send(embed=Embed(ctx, title="Current Time in **{}**".format(timezone),
                                           description=base_time.astimezone(tz).strftime(self.STRFTIME_FORMAT)))

    @discord.ext.commands.group(invoke_without_command=True, brief="Display the list of timezones", usage="[prefix]", enabled=False)
    async def timezones(self, ctx: HubContext, prefix: str = None):
        if prefix is None:
            data = list(pytz.all_timezones)
            items = {}
            for tz in data:
                prefix, sep, suffix = tz.partition("/")
                if not sep:
                    prefix = "No Prefix"
                l = items.setdefault(prefix, [])
                l.append(tz)
            final_items = [(prefix, "\n".join(prefix_data)) for prefix, prefix_data in items.items()]
            embed = Embed(ctx, title="All Timezones", description="Here is the list of all timezones, delimited by prefix.")
            await send_embeds_fields(ctx, embed, final_items)
        else:
            data = list(filter(lambda _tz: _tz.startswith(prefix), pytz.all_timezones))
            if len(data) == 0:
                embed = Embed(ctx, color=discord.Color.red(), title="No Timezones Found",
                              description="There were no timezones found with the given prefix.")
                embed.add_field(name="Prefix", value=prefix)
                return await ctx.send(embed=embed)
            else:
                groups = await break_into_groups(template="", ending="", lines=data)
                embed = Embed(ctx, title="Timezones".format(prefix), description="Here is the list of timezones that contain this prefix.")
                embed.add_field(name="Prefix", value=prefix)
                await send_embeds(ctx, embed, groups)

    @timezones.command(brief="Get the list of prefixes", enabled=False)
    async def prefix(self, ctx: HubContext):
        data = list({tz.partition("/")[0] for tz in pytz.all_timezones if tz.count("/") >= 1})
        embed = Embed(ctx, title="Prefixes",
                      description="Here is the list of timezones prefixes that can be used with the `{}timezones` command.".format(
                          self.bot.command_prefix))
        groups = await break_into_groups(template="", ending="", lines=data)
        await send_embeds(ctx, embed, groups)

    @staticmethod
    def make_directory(guild_id: int):
        path = os.path.abspath(os.path.join(__file__, "..", "..", "embeds", f"g_{guild_id}"))
        os.makedirs(path, exist_ok=True)
        open(os.path.join(path, "__init__.py"), "a").close()

    @discord.ext.commands.group(invoke_without_command=True, brief="Spawn the custom Embed with the given name.", usage="name",
                                not_channel_locked=True)
    @discord.ext.commands.guild_only()
    async def embed(self, ctx: HubContext, name: str):
        if name.startswith("_"):
            raise discord.ext.commands.BadArgument("Private modules cannot be displayed.")
        try:
            module = importlib.import_module(f"bot_data.embeds.g_{getattr(ctx.guild, 'id', None)}." + name)
        except ModuleNotFoundError:
            embed = Embed(ctx, color=discord.Color.red(), title="Invalid Custom Embed",
                          description="The given custom Embed does not exist. Type `{}embed list` to get the list of Embeds.".format(
                              self.bot.command_prefix))
            embed.add_field(name="Embed Name", value=name)
            await ctx.send(embed=embed)
        else:
            new_mod = importlib.reload(module)
            assert hasattr(new_mod, "generate_embed"), "Embed is missing a `generate_embed` entry point."
            is_fields, data = await discord.utils.maybe_coroutine(new_mod.generate_embed, self.bot)
            is_fields: bool
            data: Union[List[Tuple[Optional[str], Optional[discord.Embed]]], Tuple[discord.Embed, List[Union[Tuple[str, str], str]]]]
            if not is_fields:
                for content, embed in data:
                    await ctx.send(content=content, embed=embed)
            else:
                embed, fields = data
                await send_embeds_fields(ctx, embed, fields)

    @embed.command(brief="List all custom Embeds.")
    @discord.ext.commands.guild_only()
    async def list(self, ctx: HubContext):
        self.make_directory(getattr(ctx.guild, "id", None))
        embed_path = os.path.abspath(os.path.join(__file__, "..", "..", "embeds", f"g_{getattr(ctx.guild, 'id', None)}"))
        embed = Embed(ctx, title="Custom Embeds", description="A list of the custom Embeds that the bot can send.")
        items = []
        for file in os.listdir(embed_path):
            if not os.path.isfile(os.path.join(embed_path, file)) or file.startswith("_") or not file.endswith(".py"):
                logger.debug("Skipped %s (full path: %s) (not isfile: %s, startswith _: %s, not endswith .py: %s", file,
                             os.path.join(embed_path, file), not os.path.isfile(os.path.join(embed_path, file)), file.startswith("_"),
                             not file.endswith(".py"))
                continue
            items.append(file.rpartition(".")[0])
            logger.debug("Found Embed file: %s, shown as %s", file, file.rpartition(".")[0])
        groups = await break_into_groups(template="", ending="", line_template="* **{}**", lines=items)
        await send_embeds(ctx, embed, groups, description="A list of the custom Embeds that the bot can send.")

    @embed.command(brief="Pre-create embed folders for each guild the bot is connected to.")
    @discord.ext.commands.is_owner()
    async def pre_create(self, ctx: HubContext):
        for num, guild in enumerate(self.bot.guilds):
            self.make_directory(guild.id)
        embed = Embed(ctx, title="Created Directories", description=f"The bot has created directories for **{len(self.bot.guilds)}** Guilds.",
                      color=discord.Color.green())
        await ctx.send(embed=embed)

    @discord.ext.commands.group(invoke_without_command=True, brief="Manage bot extensions.", aliases=["ext"])
    @discord.ext.commands.is_owner()
    async def extension(self, ctx: HubContext):
        """Manage the bot extensions."""
        await self.bot.generic_help(ctx)

    @extension.command(brief="Get loaded extensions", aliases=["show", "list"])
    @discord.ext.commands.is_owner()
    async def view(self, ctx: HubContext):
        """View the loaded bot extensions."""
        embed = Embed(ctx, title="Bot Extensions", description="\n".join(
            "**{}**".format(extension) for package, sep, extension in (key.rpartition(".") for key in self.bot.extensions)))
        await ctx.send(embed=embed)

    @extension.command(brief="Reload extensions", usage="extension_name_or_all [extension_name] [...]")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def reload(self, ctx: HubContext, *extensions: str):
        """Reload all or specific extensions"""
        extension_pairings: Dict[str, str] = {}
        successful = []
        failed = []
        for key, value in self.bot.extensions.items():
            package, sep, ext = key.rpartition(".")
            extension_pairings[ext] = key
        if len(extensions) < 1:
            return await ctx.send(embed=Embed(ctx, title="No Extension Specified", color=discord.Color.red(),
                                              description="An extension was not specified. View the current extensions with `{}extension "
                                                          "view`.".format(self.bot.command_prefix)))
        for extension in extensions:
            if "all" in extension:
                for key, value in self.bot.extensions.copy().items():
                    try:
                        self.bot.reload_extension(key)
                    except discord.ext.commands.ExtensionError as exc:
                        await self.bot.on_command_error(ctx, exc, custom_message="There was an exception while reloading the **{}** extension".format(
                            extension))
                        failed.append(key)
                    else:
                        successful.append(key)
            else:
                if extension in extension_pairings:
                    extension = extension_pairings[extension]
                if extension in self.bot.extensions:
                    try:
                        self.bot.reload_extension(extension)
                    except discord.ext.commands.ExtensionError as exc:
                        await self.bot.on_command_error(ctx, exc, custom_message="There was an exception while reloading the **{}** extension".format(
                            extension))
                        failed.append(extension)
                    else:
                        successful.append(extension)
                else:
                    logger.warning("Extension %s does not exist", extension)
                    embed = Embed(ctx, title="Extension Does Not Exist", color=discord.Color.red(),
                                  description="The provided Extension does not exist. Use `{}extension view` to check the avaliable "
                                              "extensions.".format(self.bot.command_prefix))
                    embed.add_field(name="Extension Name", value=extension)
                    await ctx.send(embed=embed)
                    failed.append(extension)
        successful_str = "\n".join("**{}**".format(item) for item in set(successful)) or "None"
        failed_str = "\n".join("**{}**".format(item) for item in set(failed)) or "None"
        embed = Embed(ctx, title="Extension Reload Finished", description="The specified extensions have been reloaded.",
                      color=discord.Color.green() if not failed else discord.Color.red())
        await send_embeds_fields(ctx, embed, [("Successfully Reloaded Extensions", successful_str), ("Failed To Reload Extensions", failed_str)])

    @discord.ext.commands.command(brief="OwOify text or an uploaded file", usage="text", aliases=["owoify", "uwu", "uwuify"])
    async def owo(self, ctx: HubContext, *, text: Optional[str] = None):
        if text is None:
            message: discord.Message = ctx.message
            if not message.attachments:
                self.bot.missing_argument("text")
            else:
                attachment = message.attachments[0]
                data = await attachment.read()
                try:
                    decoded = data.decode("utf-8")
                except UnicodeError as exc:
                    embed = Embed(ctx, title="Invalid Content")

    @discord.ext.commands.command(brief="Convert text in LaTeX format into a rendered PNG, and upload it.", usage="text", aliases=["tex"])
    async def latex(self, ctx: HubContext, *, text: str):
        try:
            png = latex_as_png(text)
        except ValueError as exc:
            original = exc.__cause__
            if isinstance(original, pyparsing.ParseFatalException):
                embed = Embed(ctx, title="Error Parsing Text", description=original.msg + ". (Hint, you may need to separate backslashes `\\` with braces, such as `${\\beta}...$`.)", color=discord.Color.red())
                return await ctx.send(embed=embed)
            else:
                raise exc
        else:
            return await ctx.send(file=discord.File(png, filename="render.png"))

    @discord.ext.commands.command(brief="Test")
    @discord.ext.commands.is_owner()
    async def test(self, ctx: HubContext, embed: bool = False):
        if embed:
            await ctx.send(embed=Embed(ctx))
        else:
            await ctx.send("test")

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        coros = []
        if self.bot.get_option(getattr(getattr(message, "guild", None), "id", None), "message_txt", allow_dm=True):
            coros.append(self.expand_message(message))
        return await asyncio.gather(*coros)


def setup(bot: "PokestarBot"):
    bot.add_cog(Misc(bot))
    logger.info("Loaded the Misc extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Misc extension.")
