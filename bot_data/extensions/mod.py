import itertools
import logging
import sqlite3
from collections import defaultdict
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, Union

import discord.ext.commands

from . import PokestarBotCog
from ..converters import AllConverter, EmojiConverter, MemberRolesConverter
from ..utils import CustomContext, Embed, send_embeds_fields

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Mod(PokestarBotCog):
    converter = EmojiConverter(strict_emoji=True)

    async def invite_snapshot(self, ctx: discord.ext.commands.Context) -> Tuple[Dict[str, int], Dict[str, discord.Invite]]:
        if not ctx.me.guild_permissions.manage_guild:
            raise discord.ext.commands.BotMissingPermissions(["manage_guild"])
        guild: discord.Guild = ctx.guild
        async with self.bot.conn.execute("""SELECT CODE, USES FROM INVITES WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]) as cursor:
            data1 = await cursor.fetchall()
        data2 = {}
        for invite in await guild.invites():
            invite: discord.Invite
            data2[invite.code] = invite
        async with self.bot.conn.execute("""DELETE FROM INVITES WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]), self.bot.conn.executemany(
                """INSERT INTO INVITES(CODE, GUILD_ID, USES) VALUES(?, ?, ?)""",
                [(invite.code, getattr(ctx.guild, "id", None), invite.uses) for invite in data2.values()]):
            pass
        return dict(data1), data2

    async def parse_invite_differences(self, ctx: discord.ext.commands.Context, member: Optional[discord.Member] = None,
                                       invite_that_got_deleted: Optional[discord.Invite] = None):
        channel = self.bot.get_channel_data(ctx.guild, "admin-log")
        if channel is None:
            return
        if not self.bot.get_option(getattr(ctx.guild, "id", None), "invite_track"):
            return
        try:
            old, new = await self.invite_snapshot(ctx)
        except discord.ext.commands.BotMissingPermissions:
            return
        new_dict = {invite.code: invite.uses for invite in new.values()}
        removed = old.keys() - new_dict.keys()
        added = new_dict.keys() - old.keys()
        changed = dict(new_dict.items() - old.items())
        for key in added | removed:
            changed.pop(key, None)
        if changed:
            for code in changed.keys():
                invite: discord.Invite = new[code]
                if not member:
                    embed = Embed(ctx, title="Invite Used", description="An invite was used.", color=discord.Color.green())
                else:
                    embed = Embed(ctx, title="Member Joined", description="A member has joined the guild.", color=discord.Color.green())
                    embed.add_field(name="Member", value=member.mention)
                    member = None
                embed.add_field(name="Inviter", value=invite.inviter.mention)
                embed.add_field(name="Total Uses", value=invite.uses)
                await channel.send(embed=embed)
        if added:
            for code in added:
                invite: discord.Invite = new[code]
                embed = Embed(ctx, title="Invite Created", description="An invite was created.", color=discord.Color.green())
                embed.add_field(name="Code", value=code)
                embed.add_field(name="Link", value=invite.url)
                embed.add_field(name="Inviter", value=invite.inviter.mention)
                embed.add_field(name="Total Uses", value=invite.uses)
                await channel.send(embed=embed)
        if removed:
            for code in removed:
                embed = Embed(ctx, title="Invite Deleted", description="An invite was deleted.", color=discord.Color.red())
                if member is not None:  # reasonably assume member took this invite, and it had limited uses.
                    embed.add_field(name="Member", value=member.mention)
                    member = None
                embed.add_field(name="Code", value=code)
                if invite_that_got_deleted is not None:
                    embed.add_field(name="Link", value=invite_that_got_deleted.url)
                    if invite_that_got_deleted.inviter:
                        embed.add_field(name="Inviter", value=invite_that_got_deleted.inviter.mention)
                    if invite_that_got_deleted.uses:
                        embed.add_field(name="Total Uses", value=invite_that_got_deleted.uses)
                    invite_that_got_deleted = None
                await channel.send(embed=embed)

    @discord.ext.commands.command(brief="Mass move users to a voice channel", usage="voice_channel_name member [member] [member] ...")
    @discord.ext.commands.has_guild_permissions(move_members=True)
    @discord.ext.commands.bot_has_guild_permissions(move_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def move(self, ctx: discord.ext.commands.Context, channel: discord.VoiceChannel, *users: Union[AllConverter, MemberRolesConverter]):
        success = []
        fail = []
        full_users = []
        if not users:
            return await ctx.send(embed=Embed(ctx, color=discord.Color.red(), title="No Users Specified",
                                              description="You need to specify a user, role, voice channel, or `all` (pull out of all voice "
                                                          "channels into the current channel) to move into the given voice channel."))
        for user in users:
            if user == AllConverter.All:
                for voice_channel in ctx.guild.voice_channels:
                    if voice_channel == channel:
                        break
                    voice_channel: discord.VoiceChannel
                    full_users.extend(voice_channel.members)
            else:
                full_users.extend(user)
        full_users = set(full_users)
        for user in full_users:
            user: discord.Member
            try:
                logger.debug("Moving %s to %s", user, channel)
                if user.permissions_in(channel).connect:
                    await user.move_to(channel, reason="Mass Move requested by {}".format(ctx.author))
                else:
                    fail.append(user)
                    continue
            except discord.DiscordException:
                fail.append(user)
            else:
                success.append(user)
        embed = Embed(ctx, title="Voice Channel Mass Move", color=discord.Color.green())
        fields = [("Moved To Voice Channel", str(channel)), ("User That Requested Move", ctx.author.mention),
                  ("Successfully Moved", "\n".join(user.mention for user in success) or "None"),
                  ("Failed To Move", "\n".join(user.mention for user in fail) or "None")]
        if fail:
            logger.warning("Unable to move these users to %s: %s", channel, ", ".join(user.mention for user in fail))
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(brief="Kick all users that belong to a Role (very dangerous)", usage="user_or_role [user_or_role] [...]")
    @discord.ext.commands.has_guild_permissions(kick_members=True)
    @discord.ext.commands.bot_has_guild_permissions(kick_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def kick(self, ctx: discord.ext.commands.Context, *member_roles: MemberRolesConverter):
        if len(member_roles) == 0:
            self.bot.missing_argument("user_or_role")
        members = list(itertools.chain(*member_roles))
        fields = []
        mentions = []
        for member in members:
            mentions.append(member.mention)
        fields.append(("Users To Be Kicked", "\n".join(mentions) or "None"))
        if self.bot.get_option(getattr(ctx.guild, "id", None), "warn_kick"):
            embed = Embed(ctx, title="Kicking Users", description="This action is *irreversible*. Send `y` to confirm.", color=discord.Color.red())
            await send_embeds_fields(ctx, embed, fields)
            await self.bot.wait_for("message",
                                    check=lambda
                                        message: message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in [
                                        "y", "yes", "confirm", "1"], timeout=60)
        guild: discord.Guild = ctx.guild
        for member in members:
            await guild.kick(member, reason=f"Mass Kick by {ctx.author}")
        return await ctx.send(embed=Embed(ctx, title="Kicked", description="All members specified have been kicked.", color=discord.Color.green()))

    @discord.ext.commands.command(brief="Mute all members in a voice channel (except the exceptions provided)",
                                  usage="voice_channel [exception] [exception]")
    @discord.ext.commands.bot_has_guild_permissions(mute_members=True)
    @discord.ext.commands.has_guild_permissions(mute_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def mute(self, ctx: discord.ext.commands.Context, voice_channel: discord.VoiceChannel, *exceptions: MemberRolesConverter):
        exception_members = list(itertools.chain(*exceptions))
        to_mute = [member for member in voice_channel.members if member not in exception_members]
        await ctx.trigger_typing()
        for member in to_mute:
            member: discord.Member
            await member.edit(mute=True, reason=f"Mass Mute by {ctx.author}")
        embed = Embed(ctx, title="Muted Users", description="The following users (minus exceptions) were muted.", color=discord.Color.green())
        fields = [("Muted", "\n".join(user.mention for user in to_mute) or "None"),
                  ("Exceptions", "\n".join(user.mention for user in exception_members) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(brief="Deafen all members in a voice channel (except the exceptions provided)",
                                  usage="voice_channel [exception] [exception]")
    @discord.ext.commands.bot_has_guild_permissions(deafen_members=True)
    @discord.ext.commands.has_guild_permissions(deafen_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def deafen(self, ctx: discord.ext.commands.Context, voice_channel: discord.VoiceChannel, *exceptions: MemberRolesConverter):
        exception_members = list(itertools.chain(*exceptions))
        to_deafen = [member for member in voice_channel.members if member not in exception_members]
        await ctx.trigger_typing()
        for member in to_deafen:
            member: discord.Member
            await member.edit(deafen=True, reason=f"Mass Deafen by {ctx.author}")
        embed = Embed(ctx, title="Deafened Users", description="The following users (minus exceptions) were deafened.", color=discord.Color.green())
        fields = [("Deafened", "\n".join(user.mention for user in to_deafen) or "None"),
                  ("Exceptions", "\n".join(user.mention for user in exception_members) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(brief="Unmute all members in a voice channel (except the exceptions provided)",
                                  usage="voice_channel [exception] [exception]")
    @discord.ext.commands.bot_has_guild_permissions(mute_members=True)
    @discord.ext.commands.has_guild_permissions(mute_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def unmute(self, ctx: discord.ext.commands.Context, voice_channel: discord.VoiceChannel, *exceptions: MemberRolesConverter):
        exception_members = list(itertools.chain(*exceptions))
        to_mute = [member for member in voice_channel.members if member not in exception_members]
        await ctx.trigger_typing()
        for member in to_mute:
            member: discord.Member
            await member.edit(mute=False, reason=f"Mass Unmute by {ctx.author}")
        embed = Embed(ctx, title="Unmuted Users", description="The following users (minus exceptions) were unmuted.", color=discord.Color.green())
        fields = [("Unmuted", "\n".join(user.mention for user in to_mute) or "None"),
                  ("Exceptions", "\n".join(user.mention for user in exception_members) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(brief="Undeafen all members in a voice channel (except the exceptions provided)",
                                  usage="voice_channel [exception] [exception]")
    @discord.ext.commands.bot_has_guild_permissions(deafen_members=True)
    @discord.ext.commands.has_guild_permissions(deafen_members=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def undeafen(self, ctx: discord.ext.commands.Context, voice_channel: discord.VoiceChannel, *exceptions: MemberRolesConverter):
        exception_members = list(itertools.chain(*exceptions))
        to_deafen = [member for member in voice_channel.members if member not in exception_members]
        await ctx.trigger_typing()
        for member in to_deafen:
            member: discord.Member
            await member.edit(deafen=False, reason=f"Mass Undeafen by {ctx.author}")
        embed = Embed(ctx, title="Undeafened Users", description="The following users (minus exceptions) were undeafened.",
                      color=discord.Color.green())
        fields = [("Undeafened", "\n".join(user.mention for user in to_deafen) or "None"),
                  ("Exceptions", "\n".join(user.mention for user in exception_members) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @discord.ext.commands.command(brief="Panel that allows moderators to perform mutes/unmutes, deafen/undeafens and moves on a channel.",
                                  usage="voice_channel")
    async def voice_control(self, ctx: discord.ext.commands.Context, voice_channel: discord.VoiceChannel):
        embed = Embed(ctx, title="Voice Control")
        embed.add_field(name="Voice Channel", value=voice_channel.name)
        embed.add_field(name="Channel ID", value=str(voice_channel.id))
        embed.add_field(name="🔇", value="Mute")
        embed.add_field(name="🔈", value="Unmute")
        embed.add_field(name="➡", value="Move To")
        embed.add_field(name="🎵", value="Undeafen")
        embed.add_field(name="🎧", value="Deafen")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🔇")
        await msg.add_reaction("🔈")
        await msg.add_reaction("➡")
        await msg.add_reaction("🎵")
        await msg.add_reaction("🎧")

    @discord.ext.commands.group(brief="Deal with the emoji blacklist", invoke_without_command=True)
    @discord.ext.commands.has_guild_permissions(administrator=True)
    async def emoji_blacklist(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @emoji_blacklist.command(name="add", brief="Add an emoji to the blacklist.", usage="emoji")
    @discord.ext.commands.has_guild_permissions(administrator=True)
    async def emoji_add(self, ctx: discord.ext.commands.Context, emoji: EmojiConverter):
        emoji = emoji.lower()
        try:
            async with self.bot.conn.execute("""INSERT INTO BLACKLISTED_EMOJIS(GUILD_ID, EMOJI) VALUES (?, ?)""",
                                             [getattr(ctx.guild, "id", None), emoji]):
                pass
        except sqlite3.IntegrityError:
            embed = Embed(ctx, title="Emoji Exists", description="The emoji has already been added to the blacklist.", color=discord.Color.red())
        else:
            embed = Embed(ctx, title="Emoji Added", description="The emoji was added to the blacklist.", color=discord.Color.green())
        embed.add_field(name="Emoji Name", value=emoji)
        await ctx.send(embed=embed)
        await self.bot.get_blacklist_mappings()

    @emoji_blacklist.command(name="remove", brief="Remove an emoji from the blacklist.", usage="emoji")
    @discord.ext.commands.has_guild_permissions(administrator=True)
    async def emoji_remove(self, ctx: discord.ext.commands.Context, emoji: EmojiConverter):
        emoji = emoji.lower()
        async with self.bot.conn.execute("""DELETE FROM BLACKLISTED_EMOJIS WHERE GUILD_ID==? AND EMOJI==?""",
                                         [getattr(ctx.guild, "id", None), emoji]):
            pass
        embed = Embed(ctx, title="Emoji Removed", description="The emoji was removed from the blacklist.", color=discord.Color.green())
        embed.add_field(name="Emoji Name", value=emoji)
        await ctx.send(embed=embed)
        await self.bot.get_blacklist_mappings()

    @emoji_blacklist.command(name="list", brief="List blacklisted emoji.")
    @discord.ext.commands.has_guild_permissions(administrator=True)
    async def emoji_list(self, ctx: discord.ext.commands.Context):
        async with self.bot.conn.execute("""SELECT EMOJI FROM BLACKLISTED_EMOJIS WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        embed = Embed(ctx, title="Blacklisted Emojis")
        await send_embeds_fields(ctx, embed, ["\n".join(emoji for emoji, in data)])

    @discord.ext.commands.command(brief="Lock a channel", usage="[channel]", not_channel_locked=True) 
    @discord.ext.commands.bot_has_guild_permissions(manage_channels=True)
    @discord.ext.commands.has_guild_permissions(manage_channels=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def lock(self, ctx: discord.ext.commands.Context, channel: discord.TextChannel = None):
        channel: discord.TextChannel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        overwrites = channel.overwrites
        overwrites[ctx.guild.default_role] = overwrite
        await channel.edit(reason=f"Locking channel by {ctx.author}", overwrites=overwrites)
        embed = Embed(ctx, title="Locked Channel", description="The channel has been locked.", color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Unlock a channel", usage="[channel]", not_channel_locked=True)
    @discord.ext.commands.bot_has_guild_permissions(manage_channels=True)
    @discord.ext.commands.has_guild_permissions(manage_channels=True)
    @discord.ext.commands.max_concurrency(1, discord.ext.commands.BucketType.guild)
    async def unlock(self, ctx: discord.ext.commands.Context, channel: discord.TextChannel = None):
        channel: discord.TextChannel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        overwrites = channel.overwrites
        overwrites[ctx.guild.default_role] = overwrite
        await channel.edit(reason=f"Unlocking channel by {ctx.author}", overwrites=overwrites)
        embed = Embed(ctx, title="Unlocked Channel", description="The channel has been unlocked.", color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Get total invite counts", usage="[min] [member] [role]",
                                  not_channel_locked=True)
    @discord.ext.commands.bot_has_guild_permissions(manage_guild=True)
    @discord.ext.commands.has_guild_permissions(manage_guild=True)
    async def invite_count(self, ctx: discord.ext.commands.Context, min: int = 0, member: Optional[discord.Member] =
    None, role: Optional[discord.Role] = None):
        ctx.guild: discord.Guild
        invites: List[discord.Invite] = await ctx.guild.invites()
        counts = defaultdict(lambda: 0)
        for invite in invites:
            counts[invite.inviter] += invite.uses
        if member is None:
            embed = Embed(ctx, title="Invites", description=f"Threshold: {min}")
            lines = []
            for user, total in sorted(counts.items(), key=lambda item: item[1], reverse=True):
                if total >= min:
                    lines.append(f"{user.mention} ({user.id}): **{total}**")
                    if role:
                        member: discord.Member = ctx.guild.get_member(user.id)
                        if member and role not in member.roles:
                            await member.add_roles(role, reason="Invite count command")
            await send_embeds_fields(ctx, embed, ["\n".join(lines)])

        else:
            ids_mapped = defaultdict(lambda:0, **{user.id: count for user, count in counts.items()})
            embed = Embed(ctx, title="Invites for Member", description=f"Has **{ids_mapped[member.id]}**\nMeets "
                                                                       f"Threshold: **"
                                                                       f"{ids_mapped[member.id] >= min}**")
            return await ctx.send(embed=embed)

    async def on_reaction(self, msg: discord.Message, emoji: Union[discord.PartialEmoji, discord.Emoji], user: discord.Member):
        if user.id == self.bot.user.id or user.bot or msg.author.id != self.bot.user.id or not msg.embeds or not msg.embeds[0].title:
            return
        embed: discord.Embed = msg.embeds[0]
        ctx: CustomContext = await self.bot.get_context(msg, cls=CustomContext)
        ctx.author = user
        if embed.title == "Voice Control":
            channel_id = int(embed.fields[1].value)
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                embed = Embed(ctx, title="Invalid Voice Channel", description="The provided voice channel no longer exists.",
                              color=discord.Color.red())
                embed.add_field(name="Channel ID", value=str(channel_id))
                return await ctx.send(embed=embed)
            if "🔇" in str(emoji):
                return await self.mute.fully_run_command(ctx, channel)
            elif "🔈" in str(emoji):
                return await self.unmute.fully_run_command(ctx, channel)
            elif "➡" in str(emoji):
                embed = Embed(ctx, title="New Channel", description="Enter the name of the voice channel to move to.", color=discord.Color.green())
                await ctx.send(embed=embed)

                def check(message: discord.Message):
                    return message.channel == ctx.channel and message.author == ctx.author

                message = await self.bot.wait_for("message", check=check, timeout=60)

                try:
                    channel2 = await discord.ext.commands.VoiceChannelConverter().convert(ctx, message.content)
                except discord.ext.commands.BadArgument:
                    embed = Embed(ctx, title="Invalid Voice Channel Name",
                                  description="The provided name is not the name of an existing voice channel.", color=discord.Color.red())
                    embed.add_field(name="Provided Name", value=message.content if len(message.content) <= 1024 else "[Too Long]")
                    return await ctx.send(embed=embed)
                else:
                    await self.move.fully_run_command(ctx, channel2, channel.members)
                    return await self.voice_control.fully_run_command(ctx, channel2)
            elif "🎵" in str(emoji):
                return await self.undeafen.fully_run_command(ctx, channel)
            elif "🎧" in str(emoji):
                return await self.deafen.fully_run_command(ctx, channel)

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.content or (message.content or "").startswith(self.bot.command_prefix + "emoji_blacklist") or not (
                self.bot.blacklisted_emojis.get(getattr(getattr(message, "guild", None), "id", None), [])):
            return
        context = await self.bot.get_context(message)
        words = (message.content or "").replace("\n", " ").split(" ")
        emojis = []
        for word in words:
            try:
                emoji = await self.converter.convert(context, word)
                emoji = emoji.lower()
            except discord.ext.commands.BadArgument:
                continue
            else:
                emojis.append(emoji)
        if context.guild and emojis and await self.bot.blacklisted(context.guild.id, *emojis):
            await self.remove_blacklisted(context)

    async def remove_blacklisted(self, ctx: discord.ext.commands.Context):
        if not ctx.channel.permissions_for(ctx.me).manage_messages:
            if channel := self.bot.get_channel_data(getattr(ctx.guild, "id", None), "admin-log"):
                embed = Embed(ctx, title="Unable to Remove Message",
                              description="The bot is unable to remove a message containing a blacklisted emoji.", color=discord.Color.red())
                embed.add_field(name="Channel", value=ctx.channel.mention)
                embed.add_field(name="Message", value=ctx.message.jump_url)
                return await channel.send(embed=embed)
            else:
                return
        else:
            await ctx.message.delete()
            embed = Embed(ctx, title="Removed", description="You used an emoji that is blacklisted.", color=discord.Color.red())
            return await ctx.send(embed=embed)

    @discord.ext.commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        guild: discord.Guild = self.bot.get_guild(invite.guild.id)
        context = CustomContext(bot=self.bot, prefix=self.bot.command_prefix)
        context.guild = guild
        context.author = context.me
        context.cog = self
        await self.parse_invite_differences(context)

    @discord.ext.commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        guild: discord.Guild = self.bot.get_guild(invite.guild.id)
        context = CustomContext(bot=self.bot, prefix=self.bot.command_prefix)
        context.guild = guild
        context.author = context.me
        context.cog = self
        await self.parse_invite_differences(context, invite_that_got_deleted=invite)

    @discord.ext.commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        context = CustomContext(bot=self.bot, prefix=self.bot.command_prefix)
        context.guild = member.guild
        context.author = context.me
        context.cog = self
        await self.parse_invite_differences(context, member=member)


def setup(bot: "PokestarBot"):
    bot.add_cog(Mod(bot))
    logger.info("Loaded the Mod extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Mod extension.")
