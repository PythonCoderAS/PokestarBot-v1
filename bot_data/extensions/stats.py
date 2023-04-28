import collections
import csv
import datetime
import io
import itertools
import logging
import sqlite3
import zipfile
from typing import List, Optional, TYPE_CHECKING

import asyncio
import discord.ext.commands

from . import PokestarBotCog
from ..const import stats_template
from ..utils import CustomContext, Embed, admin_or_bot_owner, send_embeds_fields

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Stats(PokestarBotCog):
    STATS_TEMPLATE = STATS_CHANNEL_TEMPLATE = stats_template

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        check = self.bot.has_channel("message-goals")
        self.bot.add_check_recursive(self.stats_channel, check)

    @discord.ext.commands.group(name="stats", invoke_without_command=True, brief="Get channel statistics",
                                usage="[channel] [...] [min_messages] [limit]")
    @discord.ext.commands.guild_only()
    async def command_stats(self, ctx: discord.ext.commands.Context, channels: discord.ext.commands.Greedy[discord.TextChannel],
                            min_messages: int = 5, limit: Optional[int] = 24):
        channels: List[discord.TextChannel] = list(channels)
        if not self.bot.get_channel_data(getattr(ctx.guild, "id", None), "message-goals"):
            raise discord.ext.commands.CheckFailure("The guild does not have a message-goals guild-channel mapping.")
        if len(channels) == 0:
            channels.append(ctx.channel)
        if len(channels) > 1:
            for channel in channels:
                await self.command_stats(ctx, channel, min_messages=min_messages)
        else:
            channel: discord.TextChannel = channels[0]
            guild_id = getattr(getattr(channel, "guild", None), "id", 0)
            logger.info("Requested stats on channel %s", channel)
            waiting = False
            if not self.bot.stats_working_on(ctx.guild.id).is_set():
                await ctx.send("Bot is updating message cache. Once it is finished, you will be pinged and the stats will be sent.")
                waiting = True
            await self.bot.stats_working_on(ctx.guild.id).wait()
            async with self.bot.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==?""", [guild_id, channel.id]) as cursor:
                messages, = await cursor.fetchone()
            if waiting:
                await ctx.send(ctx.author.mention + ", here are the stats you requested:")
            embed = Embed(ctx, title="Stats for Channel **{}**".format(str(channel)),
                          description="The channel contains **{}** messages. The fields below contain the messages sent by each user in the "
                                      "channel.".format(
                              messages))
            fields = []
            num = 0
            async with self.bot.conn.execute(
                    """SELECT AUTHOR_ID, SUM(NUM) FROM STAT WHERE GUILD_ID==? AND CHANNEL_ID==? GROUP BY GUILD_ID, CHANNEL_ID, AUTHOR_ID""",
                    [guild_id, channel.id]) as cursor:
                data = dict(await cursor.fetchall())
            for user_id, user_data in sorted(data.items(), key=lambda keyvaluepair: keyvaluepair[1], reverse=True):
                if user_data < min_messages:
                    continue
                if ctx.guild:
                    user = non_member_user = ctx.guild.get_member(int(user_id))
                else:
                    user = non_member_user = None
                user: Optional[discord.Member]
                if not user:
                    try:
                        non_member_user: discord.User = self.bot.get_user(user_id) or await self.bot.fetch_user(int(user_id))
                    except discord.errors.NotFound:
                        user_name = "*[Deleted User]*"
                    else:
                        user_name = str(non_member_user) + " *[Not a guild member]*"
                else:
                    user_name = str(user)
                if getattr(user or non_member_user, "bot", None):
                    user_name += " *[BOT]*"
                fields.append((user_name, "**{}** messages".format(user_data)))
                num += 1
                if num == limit:
                    break
            await send_embeds_fields(ctx, embed, fields)

    @command_stats.command(name="global", brief="Gets stats on all channels in the guild", usage="[min_messages] [limit]")
    @discord.ext.commands.guild_only()
    async def stats_global(self, ctx: discord.ext.commands.Context, min_messages: int = 5, limit: Optional[int] = 24):
        guild: discord.Guild = ctx.guild
        logger.info("Getting global statistics.")
        waiting = False
        if not self.bot.stats_working_on(ctx.guild.id).is_set():
            await ctx.send("Bot is updating message cache. Once it is finished, you will be pinged and the stats will be sent.")
            waiting = True
        await self.bot.stats_working_on(ctx.guild.id).wait()
        channels = guild.text_channels
        async with self.bot.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==?""", [guild.id]) as cursor:
            messages, = await cursor.fetchone()
        if waiting:
            await ctx.send(ctx.author.mention + ", here are the stats you requested:")
        message = f"Total Guild Messages: **{messages}**"
        channel_fields = []
        channel_embed = Embed(ctx, title="Guild Stats (Channels)", description=message)
        existing = messages
        excluded = 0
        async with self.bot.conn.execute("""SELECT CHANNEL_ID, SUM(NUM) FROM STAT WHERE GUILD_ID==? GROUP BY CHANNEL_ID""", [guild.id]) as cursor:
            data = dict(await cursor.fetchall())
        for channel in sorted(channels, key=lambda channel: data.get(channel.id, 0), reverse=True):
            msg_sum = data.get(channel.id, 0)
            existing -= msg_sum
            if msg_sum < min_messages:
                excluded += msg_sum
                continue
            channel_fields.append((str(channel), "**{}** messages".format(msg_sum)))
            data.pop(channel.id, None)
        if existing > 0:
            channel_fields.append(("Messages From Deleted Channels", str(existing)))
        if excluded > 0:
            channel_fields.append(("Messages From Excluded Channels", str(excluded)))
        await send_embeds_fields(ctx, channel_embed, channel_fields, description=message)
        user_fields = []
        user_embed = Embed(ctx, title="Guild Stats (Users)", description=message)
        existing = messages
        num = excluded = 0
        async with self.bot.conn.execute("""SELECT AUTHOR_ID, SUM(NUM) FROM STAT WHERE GUILD_ID==? GROUP BY AUTHOR_ID""",
                                         [guild.id]) as cursor:
            data = dict(await cursor.fetchall())
        for user_id, user_data in sorted(data.items(), key=lambda keyvaluepair: keyvaluepair[1], reverse=True):
            existing -= user_data
            if user_data < min_messages:
                excluded += user_data
                continue
            user = non_member_user = ctx.guild.get_member(int(user_id))
            user: Optional[discord.Member]
            if not user:
                try:
                    non_member_user: discord.User = await self.bot.fetch_user(int(user_id))
                except discord.errors.NotFound:
                    user_name = "*[Deleted User]*"
                else:
                    user_name = str(non_member_user) + " *[Not a guild member]*"
            else:
                user_name = str(user)
            if getattr(user or non_member_user, "bot", None):
                user_name += " *[BOT]*"
            # logger.debug("%s (%s / %s)", user, user.id if hasattr(user, "id") else "", user_id)
            user_fields.append((user_name, "**{}** messages".format(user_data)))
            num += 1
            if num == limit:
                break
        if existing > 0 or excluded > 0:
            user_fields.append(("Excluded Users", str(excluded + existing)))
        await send_embeds_fields(ctx, user_embed, user_fields, description=message)

    @command_stats.group(brief="Reset the messages collected for a channel.", usage="channel [channel] [...]", invoke_without_command=True)
    @admin_or_bot_owner()
    async def reset(self, ctx: discord.ext.commands.Context, *channels: discord.TextChannel):
        if len(channels) == 0:
            self.bot.missing_argument("channel")
        embed = Embed(ctx, title="Reset Statistics", description="Statistics for the following channels have been reset", color=discord.Color.green())
        for channel in channels:
            await self.bot.remove_channel(channel, _from_stat_reset=True)
        await send_embeds_fields(ctx, embed, ["\n".join(channel.mention for channel in channels)])
        await self.bot.get_guild_stats(ctx.guild)

    @reset.command(brief="Resets the messages collected for a guild.")
    @admin_or_bot_owner()
    @discord.ext.commands.max_concurrency(1, per=discord.ext.commands.BucketType.guild)
    async def guild(self, ctx: discord.ext.commands.Context):
        async with self.bot.conn.execute("""SELECT SUM(NUM) FROM STAT WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]) as cursor:
            num, = await cursor.fetchone()
        embed = Embed(ctx, title="Confirm Reset",
                      description=f"Are you sure that you want to reset statistics for this Guild? This will delete the **{num}** messages that are "
                                  f"stored under the bot, and re-collect all messages. Send `y` to confirm.",
                      color=discord.Color.red())
        await ctx.send(embed=embed)
        await self.bot.wait_for("message",
                                check=lambda message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                                    "y", "yes", "true", "1"])
        async with self.bot.conn.execute("""DELETE FROM STAT WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]):
            pass
        await ctx.send(embed=Embed(ctx, title="Reset Stats", description="Statistics have been reset. They will be re-collected."))
        await self.bot.get_guild_stats(ctx.guild)

    @reset.command(name="all", brief="Resets the messages collected for all guilds.")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.max_concurrency(1, per=discord.ext.commands.BucketType.user)
    async def reset_all(self, ctx: discord.ext.commands.Context):
        async with self.bot.conn.execute("""SELECT SUM(NUM) FROM STAT""") as cursor:
            num, = await cursor.fetchone()
        embed = Embed(ctx, title="Confirm Reset",
                      description=f"Are you sure that you want to reset all stats? This will delete the **{num}** messages that are "
                                  f"stored under the bot, and re-collect all messages. Send `y` to confirm.",
                      color=discord.Color.red())
        await ctx.send(embed=embed)
        await self.bot.wait_for("message",
                                check=lambda message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                                    "y", "yes", "true", "1"])
        async with self.bot.conn.execute("""DELETE FROM STAT"""):
            pass
        await ctx.send(embed=Embed(ctx, title="Reset Stats", description="Statistics have been reset. They will be re-collected."))
        await self.bot.get_all_stats()

    async def fill_guild_stats(self, guild: discord.Guild, dt_obj: datetime.datetime):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).read_message_history:
                queue = collections.deque()
                async for message in channel.history(limit=None, after=dt_obj, oldest_first=True):
                    queue.appendleft(message)
                    if len(queue) == 100:
                        await self.bot.add_stat(*queue)
                        queue.clear()


    @reset.command(name="fill", brief="Fill in all messages after the specified timestamp.")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.max_concurrency(1, per=discord.ext.commands.BucketType.user)
    async def reset_fill(self, ctx: discord.ext.commands.Context, timestamp: int):
        dt_obj = datetime.datetime.fromtimestamp(timestamp)
        await asyncio.gather(*(self.fill_guild_stats(guild, dt_obj) for guild in self.bot.guilds))
        return await ctx.send("Added!")


    @command_stats.group(brief="Get a CSV file with the statistics for the specified channels and users.",
                         usage="[include_bots] [include_outside_of_guild] [export_as_zip] [channels] [users]", invoke_without_command=True)
    async def export(self, ctx: discord.ext.commands.Context, include_bots: Optional[bool] = True, include_outside_of_guild: Optional[bool] = True,
                     export_as_zip: Optional[bool] = False, channels: discord.ext.commands.Greedy[discord.TextChannel] = None,
                     users: discord.ext.commands.Greedy[discord.Member] = None, *_, _export_as_zip_from_all: bool = False):
        async with self.bot.conn.execute("""SELECT CHANNEL_ID, AUTHOR_ID, NUM FROM STAT WHERE GUILD_ID==?""", [ctx.guild.id]) as cursor:
            d = await cursor.fetchall()
        data = {}
        out_of_guild = []
        bot = []
        non_existent = []
        user_cache = {}
        logger.debug("Here 1!")
        for channel_id, author_id, num in d:
            c_data = data.setdefault(channel_id, {})
            c_data[author_id] = num
        logger.debug("Here 2!")
        if channels:
            c_ids = [channel.id for channel in channels]
            for channel_id in data.copy().keys():
                if channel_id not in c_ids:
                    data.pop(channel_id, None)
        logger.debug("Here 3!")
        if users:
            u_ids = [user.id for user in users]
            for channel_data in data.values():
                for user_id in channel_data.copy().keys():
                    if user_id not in u_ids:
                        channel_data.pop(user_id, None)
        logger.debug("Here 4!")
        for channel_data in data.values():
            for user_id in channel_data.copy().keys():
                if user_id in out_of_guild + bot + non_existent:
                    channel_data.pop(user_id, None)
                    continue
                member = ctx.guild.get_member(int(user_id))
                if member is None and not include_outside_of_guild:
                    channel_data.pop(user_id, None)
                    out_of_guild.append(user_id)
                    continue
                elif member is not None:
                    user = member
                else:
                    try:
                        user: discord.User = user_cache.get(user_id, None) or self.bot.get_user(user_id) or (await self.bot.fetch_user(int(user_id)))
                    except discord.errors.NotFound:
                        channel_data.pop(user_id, None)
                        non_existent.append(user_id)
                        continue
                    else:
                        user_cache[user_id] = user
                if user.bot and not include_bots:
                    channel_data.pop(user_id, None)
                    bot.append(user_id)
                    continue
        logger.debug("Here 5!")
        sio = io.StringIO()
        writer = csv.writer(sio)
        heading = ["User"]
        for channel_id in data.copy().keys():
            if channel := ctx.guild.get_channel(channel_id):
                channel: discord.TextChannel
                heading.append("#" + channel.name)
            else:
                data.pop(channel_id, None)
        total_users = set(itertools.chain(*(item.keys() for item in data.values())))
        rows = []
        for user_id in total_users:
            user = user_cache.get(user_id, None) or self.bot.get_user(user_id) or (await self.bot.fetch_user(int(user_id)))
            row = [str(user)]
            async with self.bot.conn.execute("""SELECT CHANNEL_ID, NUM FROM STAT WHERE GUILD_ID==? AND AUTHOR_ID==?""",
                                             [ctx.guild.id, user_id]) as cursor:
                data2 = dict(await cursor.fetchall())
            for channel_id in data.keys():
                row.append(data2.get(channel_id, 0))
            rows.append(row)
        logger.debug("Rows: %s", rows)
        writer.writerow(heading)
        writer.writerows(rows)
        sio.seek(0)
        if _export_as_zip_from_all:
            return f"stats_{ctx.guild.id}.csv", sio
        elif not export_as_zip:
            return await ctx.send(file=discord.File(sio, filename=f"stats_{ctx.guild.id}.csv"))
        else:
            zf_io = io.BytesIO()
            zip_file = zipfile.ZipFile(zf_io, "w", compression=zipfile.ZIP_BZIP2, compresslevel=9)
            zip_file.writestr(f"stats_{ctx.guild.id}.csv", sio.read())
            zip_file.fp.seek(0)
            return await ctx.send(file=discord.File(zip_file.fp, filename=f"stats_{ctx.guild.id}.zip"))

    @export.command(brief="Get files for every guild the bot has been ever part of",
                    usage="[include_bots] [include_outside_of_guild] [export_as_zip]")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def all(self, ctx: discord.ext.commands.Context, include_bots: Optional[bool] = True, include_outside_of_guild: Optional[bool] = True,
                  export_as_zip: Optional[bool] = False):
        async with self.bot.conn.execute("""SELECT DISTINCT GUILD_ID FROM STAT""") as cursor:
            guild_ids = [guild_id async for guild_id, in cursor]
        ctx2: CustomContext = await self.bot.get_context(ctx.message, cls=CustomContext)
        items = []
        zf_io = io.BytesIO()
        zip_file = zipfile.ZipFile(zf_io, "w", compression=zipfile.ZIP_BZIP2, compresslevel=9)
        for guild_id in guild_ids:
            ctx2.guild = self.bot.get_guild(guild_id)
            data = await self.export.fully_run_command(ctx2, include_bots, include_outside_of_guild, _export_as_zip_from_all=export_as_zip)
            if isinstance(data, tuple):
                items.append(data)
        if items is None:
            return
        for fname, fio in items:
            fname: str
            fio: io.StringIO
            zip_file.writestr(fname, fio.read())
        zip_file.fp.seek(0)
        return await ctx.send(file=discord.File(zip_file.fp, filename=f"stats_all.zip"))

    @discord.ext.commands.group(invoke_without_command=True,
                                brief="Manage the printing of message contents in channels that trigger message stats (such as admin channels).",
                                aliases=["stat_channel", "stats_channels", "stat_channels", "statschannel", "statchannel", "statschannels",
                                         "statchannels"], significant=True)
    @discord.ext.commands.has_guild_permissions(administrator=True)
    async def stats_channel(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @stats_channel.command(brief="Disable the printing of message contents for statistics in these channels", usage="channel [channel] [...]")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    async def disable(self, ctx: discord.ext.commands.Context, *channels: discord.TextChannel):
        if len(channels) == 0:
            self.bot.missing_argument("channel")
        embed = Embed(ctx, title="Disabled Printing Of Messages",
                      description="These channels will no longer show the contents of messages of any statistics that get triggered in them.")
        success = []
        failed = []
        for channel in channels:
            try:
                async with self.bot.conn.execute("""INSERT INTO DISABLED_STATS(GUILD_ID, CHANNEL_ID) VALUES (?, ?)""",
                                                 [getattr(ctx.guild, "id", None), channel.id]):
                    pass
            except sqlite3.IntegrityError:
                failed.append(channel)
            else:
                success.append(channel)
        if failed:
            embed.color = discord.Color.red()
        else:
            embed.color = discord.Color.green()
        await send_embeds_fields(ctx, embed, [("Success", "\n".join(chan.mention for chan in success) or "None"),
                                              ("Failed", "\n".join(chan.mention for chan in failed) or "None")])
        await self.bot.get_disabled_channels()

    @stats_channel.command(brief="Enable the printing of message contents for statistics in these channels", usage="channel [channel] [...]")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    async def enable(self, ctx: discord.ext.commands.Context, *channels: discord.TextChannel):
        if len(channels) == 0:
            self.bot.missing_argument("channel")
        embed = Embed(ctx, title="Enabled Printing Of Messages",
                      description="These channels will start showing the contents of messages of any statistics that get triggered in them.",
                      color=discord.Color.green())
        data = [(channel.id, getattr(ctx.guild, "id", None)) for channel in channels]
        async with self.bot.conn.executemany("""DELETE FROM DISABLED_STATS WHERE CHANNEL_ID==? AND GUILD_ID==?""", data):
            pass
        await send_embeds_fields(ctx, embed, ["\n".join(chan.mention for chan in channels)])
        await self.bot.get_disabled_channels()

    @stats_channel.command(brief="List the disabled channels")
    @discord.ext.commands.guild_only()
    async def list(self, ctx: discord.ext.commands.Context):
        embed = Embed(ctx, title="Disabled Channels", description="These channels are disabled from printing message contents in message goals.")
        async with self.bot.conn.execute("""SELECT CHANNEL_ID FROM DISABLED_STATS WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        channels = [ctx.guild.get_channel(channel_id) for channel_id, in data]
        await send_embeds_fields(ctx, embed, ["\n".join(channel.mention for channel in channels) or "None"])


def setup(bot: "PokestarBot"):
    bot.add_cog(Stats(bot))
    logger.info("Loaded the Stats extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Stats extension.")
