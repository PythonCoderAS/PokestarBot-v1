import datetime
import io
import logging
from typing import List, Optional, TYPE_CHECKING, Union

import discord.ext.commands
import discord.iterators

from . import PokestarBotCog
from ..converters import TimeConverter
from ..utils import Embed, admin_or_bot_owner, partition, send_embeds_fields, HubContext

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class History(PokestarBotCog):

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        check = self.bot.has_channel("message-goals")
        self.bot.add_check_recursive(self.clean_message_goals, check, discord.ext.commands.guild_only())
        for command in self.walk_commands():
            command.not_channel_locked = True

    async def batch_delete(self, ctx: HubContext, channel: Union[discord.TextChannel], messages: List[discord.Message]):
        if not ctx.me.permissions_in(channel).manage_messages:
            raise discord.ext.commands.BotMissingPermissions(["manage_messages"])
        count = len(messages)
        new, old = partition(messages, lambda message: (datetime.datetime.utcnow() - message.created_at).total_seconds() < (3600 * 24 * 14))
        old = list(old)
        new = list(new)
        if self.bot.get_option(getattr(ctx.guild, "id", None), "warn_mass_delete"):
            embed = Embed(ctx, title="Confirm Delete?",
                          description=f"You will delete **{count}** messages in {channel.mention}. Type `y` to confirm.", color=discord.Color.red())
            m1 = await ctx.send(embed=embed)
            m2 = await self.bot.wait_for("message", check=lambda
                message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in ["y", "yes", "confirm", "1"],
                                         timeout=60)
            new.append(m1)
            new.append(m2)
            count += 2
        logger.info("Deleting %s messages from channel %s", count, channel)
        while new:
            batch = new[:100]
            new = new[100:]
            ctx.hub.add_breadcrumb(category="Message Deletion", message=f"Deleting {len(batch)} messages from {channel}.", data={"message_list": batch})
            await channel.delete_messages(batch)
        if old:
            ctx.hub.add_breadcrumb(category="Message Deletion", message=f"Deleting {len(old)} messages from {channel}.",
                                   data={"message_list": old})
            for msg in old:
                await msg.delete()
        return count

    @discord.ext.commands.command(brief="Remove `-ad` messages by Paisley Park.")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def prune_ad(self, ctx: HubContext):
        """Prune all of Paisley Park's `Get double rewards with -ad` messages."""
        channel: discord.TextChannel = self.bot.get_channel_data(getattr(ctx.guild, "id", None), "bot-spam")
        if channel is None:
            channel = ctx.channel
        messages = await channel.history(limit=None).filter(lambda message: "remove this message with -goaway" in message.content.lower()).flatten()
        count = await self.batch_delete(ctx, channel, messages)
        embed = Embed(ctx, color=discord.Color.green(), title="Prune Successful", description="The pruning was successful.")
        embed.add_field(name="Messages Deleted", value=str(count))
        await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Remove all Embeds post in the channel by the bot.")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def clean_embeds(self, ctx: HubContext, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            channel = ctx.channel
        messages = await channel.history(limit=None).filter(lambda message: message.author == ctx.me).filter(
            lambda message: bool(message.embeds)).flatten()
        count = await self.batch_delete(ctx, channel, messages)
        embed = Embed(ctx, color=discord.Color.green(), title="Batch Delete Successful", description="The batch delete was successful.")
        embed.add_field(name="Channel", value=ctx.channel.mention)
        embed.add_field(name="Messages Deleted", value=str(count))
        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            embed.add_field(name="Note",
                            value="The bot attempted to DM you this info, but was unable to. Check that you have allowed DMs from other people in "
                                  "this Guild.")
            channel: discord.TextChannel = self.bot.get_channel_data(getattr(ctx.guild, "id", None), "bot-spam")
            if channel is None:
                return
            await channel.send(ctx.author.mention, embed=embed)

    @discord.ext.commands.command(brief="Remove all messages in the #message-goals channel that are not from the bot.")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def clean_message_goals(self, ctx: HubContext):
        channel: discord.TextChannel = self.bot.get_channel_data(getattr(ctx.guild, "id", None), "message-goals")
        if channel is None:
            return
        messages = await channel.history(limit=None).filter(lambda msg: msg.author != ctx.me).filter(
            lambda msg: str(msg.author.discriminator) == "0000").flatten()
        count = await self.batch_delete(ctx, channel, messages)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="Messages Deleted", value=str(count))
        await ctx.send(embed=embed)

    @discord.ext.commands.group(brief="Replay all messages in a channel starting with a certain prefix or from a certain user.",
                                usage="[channel] [user] [user] [...] [prefix]", aliases=["replaymode", "replay"], invoke_without_command=True)
    @admin_or_bot_owner()
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def replay_mode(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                          users: discord.ext.commands.Greedy[discord.Member], *, prefix: Optional[str] = "%"):
        if channel is None:
            channel = ctx.channel
        await self.replay_mode_pre(ctx, prefix, users)
        embed = Embed(ctx, title="Started Replay Mode", description="Messages are in this channel are going to get replayed.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Selected Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Prefix", value=prefix)
        await ctx.send(embed=embed)
        base = channel.history(limit=None)
        await self.replay_mode_base(ctx, channel, users, prefix, base)

    async def replay_mode_pre(self, ctx: HubContext, prefix: str, users):
        if self.bot.get_option(getattr(ctx.guild, "id", None), "warn_replay"):
            embed = Embed(ctx, title="Performing Replay Mode",
                          description="You are about to perform a Replay. This will replay *all* messages with the given prefix. Type `y` to "
                                      "confirm.",
                          color=discord.Color.red())
            embed.add_field(name="Prefix", value=prefix)
            await send_embeds_fields(ctx, embed, [("Users", "\n".join(user.mention for user in users) or "All Users")])
            return await self.bot.wait_for("message", check=lambda
                message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                "y", "yes", "confirm", "1"], timeout=60)

    async def replay_mode_base(self, ctx: HubContext, channel, users, prefix, base: discord.iterators.HistoryIterator):
        ctx.hub.add_breadcrumb(category="Replay", message="Starting replay mode")
        base = base.filter(lambda message: not (
                message.content.startswith(f"{self.bot.command_prefix}replay_mode") or message.content.startswith(
            f"{self.bot.command_prefix}replaymode") or message.content.startswith(f"{self.bot.command_prefix}replay")))
        if users:
            base = base.filter(lambda message: message.author in users)
        if prefix:
            base = base.filter(lambda message: message.content.startswith(prefix))
        count = 0
        async for message in base:
            logger.info("Replaying message #%s: %s", count, message.id)
            count += 1
            await self.bot.on_message(message, _replay=True, _hub=ctx.hub)
        embed = Embed(ctx, title="Replay Mode Finished", description="All eligible messages have been replayed.", color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Selected Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Prefix", value=prefix)
        embed.add_field(name="Replayed Message Count", value=str(count))
        await ctx.send(embed=embed)

    @replay_mode.command(name="after",
                         brief="Replay all messages in a channel starting with a certain prefix or from a certain user after a certain message.",
                         usage="[channel] [user] [user] [...] message [prefix]")
    @admin_or_bot_owner()
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def replay_mode_after(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                                users: discord.ext.commands.Greedy[discord.Member], message: discord.Message, *, prefix: Optional[str] = "%"):
        if channel is None:
            channel = ctx.channel
        await self.replay_mode_pre(ctx, prefix, users)
        embed = Embed(ctx, title="Started Replay Mode", description="Messages are in this channel are going to get replayed.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Selected Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Prefix", value=prefix)
        await ctx.send(embed=embed)
        base = channel.history(limit=None, after=message)
        await self.replay_mode_base(ctx, channel, users, prefix, base)

    @replay_mode.command(name="before",
                         brief="Replay all messages in a channel starting with a certain prefix or from a certain user before a certain message.",
                         usage="[channel] [user] [user] [...] message [prefix]")
    @admin_or_bot_owner()
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def replay_mode_before(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                                 users: discord.ext.commands.Greedy[discord.Member], message: discord.Message, *, prefix: Optional[str] = "%"):
        if channel is None:
            channel = ctx.channel
        await self.replay_mode_pre(ctx, prefix, users)
        embed = Embed(ctx, title="Started Replay Mode", description="Messages are in this channel are going to get replayed.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Selected Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Prefix", value=prefix)
        await ctx.send(embed=embed)
        base = channel.history(limit=None, before=message)
        await self.replay_mode_base(ctx, channel, users, prefix, base)

    @replay_mode.command(name="between",
                         brief="Replay all messages in a channel starting with a certain prefix or from a certain user between two certain messages.",
                         usage="[channel] [user] [user] [...] after_message before_message [prefix]")
    @admin_or_bot_owner()
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def replay_mode_between(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                                  users: discord.ext.commands.Greedy[discord.Member], after_message: discord.Message, before_message: discord.Message,
                                  *, prefix: Optional[str] = "%"):
        if channel is None:
            channel = ctx.channel
        await self.replay_mode_pre(ctx, prefix, users)
        embed = Embed(ctx, title="Started Replay Mode", description="Messages are in this channel are going to get replayed.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Selected Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Prefix", value=prefix)
        await ctx.send(embed=embed)
        base = channel.history(limit=None, after=after_message, before=before_message)
        await self.replay_mode_base(ctx, channel, users, prefix, base)

    @discord.ext.commands.group(brief="Delete x amount of messages (from all users or certain users).", usage="[channel] [user] [user] [...] amount",
                                invoke_without_command=True)
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def mass_delete(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                          users: discord.ext.commands.Greedy[discord.Member], amount: int):
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None)
        logger.debug("Users: %s", users)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        count = 0
        msgs = []
        async for item in base:
            item: discord.Message
            count += 1
            if count > amount:
                break
            msgs.append(item)
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages before a message (from all users or certain users).",
                         usage="[channel] [user] [user] [...] message")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def before(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                     users: discord.ext.commands.Greedy[discord.Member], message: discord.Message):
        base = ctx.history(limit=None, before=message)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="Before Message", value=message.jump_url)
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages before a certain time (from all users or certain users).",
                         usage="[channel] [user] [user] [...] time")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def before_time(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                          users: discord.ext.commands.Greedy[discord.Member], *, time: TimeConverter):
        if time.dst():
            zone = "EDT"
        else:
            zone = "EST"
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None, before=time)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="Before Time", value=time.strftime("%A, %B %d, %Y at %I:%M:%S %p {}".format(zone)))
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages after a message (from all users or certain users).",
                         usage="[channel] [user] [user] [...] message")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def after(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                    users: discord.ext.commands.Greedy[discord.Member], message: discord.Message):
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None, after=message)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="After Message", value=message.jump_url)
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages after a certain time (from all users or certain users).",
                         usage="[channel] [user] [user] [...] time")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def after_time(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                         users: discord.ext.commands.Greedy[discord.Member], *, time: TimeConverter):
        time: datetime.datetime
        if time.dst():
            zone = "EDT"
        else:
            zone = "EST"
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None, after=time)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="After Time", value=time.strftime("%A, %B %d, %Y at %I:%M:%S %p {}".format(zone)))
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages between two messages (from all users or certain users).",
                         usage="[channel] [user] [user] [...] after_message before_message")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def between(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                      users: discord.ext.commands.Greedy[discord.Member], after_message: discord.Message, before_message: discord.Message):
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None, after=after_message, before=before_message)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="After Message", value=after_message.jump_url)
        embed.add_field(name="Before Message", value=before_message.jump_url)
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @mass_delete.command(brief="Delete all messages between two times (from all users or certain users).",
                         usage="[channel] [user] [user] [...] after_time before_time")
    @discord.ext.commands.has_guild_permissions(manage_messages=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def between_time(self, ctx: HubContext, channel: Optional[discord.TextChannel],
                           users: discord.ext.commands.Greedy[discord.Member], after_time: TimeConverter, before_time: TimeConverter):
        after_time: datetime.datetime
        before_time: datetime.datetime
        if after_time.dst():
            after_zone = "EDT"
        else:
            after_zone = "EST"
        if before_time.dst():
            before_zone = "EDT"
        else:
            before_zone = "EST"
        if channel is None:
            channel = ctx.channel
        base = channel.history(limit=None, after=after_time, before=before_time)
        if users:
            base = base.filter(lambda msg: msg.author in users)
        msgs = await base.flatten()
        num = await self.batch_delete(ctx, channel, msgs)
        embed = Embed(ctx, color=discord.Color.green(), title="Deletion Successful", description="The deletion was successful.")
        embed.add_field(name="After Time", value=after_time.strftime("%A, %B %d, %Y at %I:%M:%S %p {}".format(after_zone)))
        embed.add_field(name="Before Time", value=before_time.strftime("%A, %B %d, %Y at %I:%M:%S %p {}".format(before_zone)))
        embed.add_field(name="Users", value="\n".join(user.mention for user in users) or "None")
        embed.add_field(name="Messages Deleted", value=str(num))
        await ctx.send(embed=embed)

    @staticmethod
    async def chat_log_base(ctx: HubContext, messages: List[discord.Message]):
        sio = io.StringIO()
        ctx.hub.add_breadcrumb(category="History", message=f"Parsing {len(messages)} messages")
        for message in reversed(messages):
            author: Union[discord.Member, discord.User] = message.author
            if author.display_name != author.name:
                author_str = f"{author.display_name} ({author})"
            else:
                author_str = f"{author}"
            sio.write(f"{author_str}: {message.content or '<empty message>'}\n")
        sio.seek(0)
        await ctx.send(file=discord.File(sio, filename="chat_log.txt"))

    @discord.ext.commands.group(brief="Get a copy of a chat log", usage="[channel] [number]", invoke_without_command=True)
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log(self, ctx: HubContext, channel: Optional[discord.TextChannel] = None, number: Optional[int] = None):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=ctx.message).flatten())

    @chat_log.command(name="after", brief="Get a copy of a chat log after a certain message", usage="[channel] message [number]")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_after(self, ctx: HubContext, channel: Optional[discord.TextChannel], message: discord.Message,
                             number: Optional[int]):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=ctx.message, after=message).flatten())

    @chat_log.command(name="before", brief="Get a copy of a chat log before a certain message", usage="[channel] message [number]")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_before(self, ctx: HubContext, channel: Optional[discord.TextChannel], message: discord.Message,
                              number: Optional[int]):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=message).flatten())

    @chat_log.command(name="between", brief="Get a copy of a chat log between two messages", usage="[channel] after_message before_message [number]")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_between(self, ctx: HubContext, channel: Optional[discord.TextChannel], after_message: discord.Message,
                               before_message: discord.Message, number: Optional[int]):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=before_message, after=after_message).flatten())

    @chat_log.command(name="after_time", brief="Get a copy of a chat log after a certain time", usage="[channel] [number] time")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_after_time(self, ctx: HubContext, channel: Optional[discord.TextChannel], number: Optional[int], *,
                                  time: TimeConverter):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=ctx.message, after=time).flatten())

    @chat_log.command(name="before_time", brief="Get a copy of a chat log before a certain time", usage="[channel] [number] time")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_before_time(self, ctx: HubContext, channel: Optional[discord.TextChannel], number: Optional[int], *,
                                   time: TimeConverter):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=time).flatten())

    @chat_log.command(name="between_time", brief="Get a copy of a chat log between two certain times",
                      usage="[channel] [number] before_time after_time")
    @discord.ext.commands.cooldown(1, 60, type=discord.ext.commands.BucketType.member)
    async def chat_log_between_time(self, ctx: HubContext, channel: Optional[discord.TextChannel], number: Optional[int],
                                    after_time: TimeConverter, before_time: TimeConverter):
        if channel is None:
            channel = ctx.channel
        ctx.hub.add_breadcrumb(category="History", message="Obtaining message history.")
        await self.chat_log_base(ctx, await channel.history(limit=number, oldest_first=False, before=before_time, after=after_time).flatten())


def setup(bot: "PokestarBot"):
    bot.add_cog(History(bot))
    logger.info("Loaded the History extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the History extension.")
