import logging
import random
import string
from typing import Optional, TYPE_CHECKING, Union

import discord.ext.commands

from . import PokestarBotCog
from ..utils import Embed, StopCommand, partition, send_embeds_fields

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Private(PokestarBotCog):

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.bot.add_check_recursive(self.private, discord.ext.commands.bot_has_guild_permissions(manage_channels=True))

    async def pre_create(self):
        async with self.bot.conn.execute("""CREATE TABLE IF NOT EXISTS PRIVATE_CHANNELS(CHANNEL_ID BIGINT PRIMARY KEY, OWNER BIGINT)"""):
            pass
        async with self.bot.conn.execute(
                """CREATE TABLE IF NOT EXISTS BLOCKED_PRIVATE_CHANNELS(ID INTEGER PRIMARY KEY, CHANNEL_ID BIGINT, USER_ID BIGINT, UNIQUE (CHANNEL_ID, 
                USER_ID))"""):
            pass

    @property
    def random_code(self):
        return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(10))

    @discord.ext.commands.group(brief="Work with private channels", invoke_without_command=True)
    async def private(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @private.command(brief="Make a private channel", usage="[name]")
    @discord.ext.commands.cooldown(1, 60, discord.ext.commands.BucketType.member)
    async def create(self, ctx: discord.ext.commands.Context, *, name: Optional[str] = None):
        await self.pre_create()
        name = name or ("private-channel-" + self.random_code)
        category = self.bot.get_channel_data(ctx.guild.id, "private-channel")
        if category and type(category) is not discord.CategoryChannel:
            category = None
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False), ctx.author: discord.PermissionOverwrite(read_messages=True)
        }
        channel: discord.TextChannel = await ctx.guild.create_text_channel(name, category=category,
                                                                           reason=f"Creating private channel requested by {ctx.author}",
                                                                           overwrites=overwrites)
        async with self.bot.conn.execute("""INSERT INTO PRIVATE_CHANNELS(CHANNEL_ID, OWNER) VALUES (?, ?)""", [channel.id, ctx.author.id]):
            pass
        await channel.send(embed=Embed(ctx, title="Channel Created",
                                       description=f"Your private channel has been created! Add some members using `"
                                                   f"{self.bot.command_prefix}private add`!",
                                       color=discord.Color.green()))

    @private.command(name="import", brief="Import an existing private channel that is not under the bot", usage="[channel] [owner]",
                     not_channel_locked=True)
    @discord.ext.commands.has_guild_permissions(manage_channels=True)
    async def import_channel(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel], user: Optional[discord.Member]):
        channel = channel or ctx.channel
        user = user or ctx.author
        in_bot = await self.check_in_bot(channel)
        if in_bot:
            embed = Embed(ctx, title="Channel Already In The Bot",
                          description="The channel is already in the bot's database, and cannot be imported.", color=discord.Color.red())
            embed.add_field(name="Channel", value=channel.mention)
            return await ctx.send(embed=embed)
        else:
            perms: discord.PermissionOverwrite = channel.overwrites_for(channel.guild.default_role)
            if perms.read_messages is not False:
                embed = Embed(ctx, title="Not Private Channel", description="The channel is not private.", color=discord.Color.red())
                embed.add_field(name="Channel", value=channel.mention)
                return await ctx.send(embed=embed)
            else:
                overwrites = channel.overwrites
                overwrites[user] = discord.PermissionOverwrite(read_messages=True)
                await channel.edit(overwrites=overwrites, reason="Adding user to the channel as owner")
                async with self.bot.conn.execute("""INSERT INTO PRIVATE_CHANNELS(CHANNEL_ID, OWNER) VALUES (?, ?)""", [channel.id, user.id]):
                    pass
                embed = Embed(ctx, title="Imported", description="The channel has been imported.")
                embed.add_field(name="Channel", value=channel.mention)
                embed.add_field(name="Channel Owner", value=user.id)
                return await ctx.send(embed=embed)

    async def check_in_bot(self, channel: discord.TextChannel):
        await self.pre_create()
        async with self.bot.conn.execute("""SELECT OWNER FROM PRIVATE_CHANNELS WHERE CHANNEL_ID==?""", [channel.id]) as cursor:
            data = await cursor.fetchone()
        return bool(data is None)

    async def verify_owner(self, ctx: discord.ext.commands.Context, user: discord.Member, channel: discord.TextChannel,
                           verifying_existence_only: bool = False):
        await self.pre_create()
        async with self.bot.conn.execute("""SELECT OWNER FROM PRIVATE_CHANNELS WHERE CHANNEL_ID==?""", [channel.id]) as cursor:
            data = await cursor.fetchone()
        if data is None:
            embed = Embed(ctx, title="Channel not a Bot Private Channel", description="The channel is not a private channel created by the bot.",
                          color=discord.Color.red())
            embed.add_field(name="Channel", value=channel.mention)
            await ctx.send(embed=embed)
            raise StopCommand
        if verifying_existence_only:
            return True
        owner_id, = data
        if user.id != owner_id and not user.guild_permissions.administrator:
            embed = Embed(ctx, title="Not Owner", description="You are not the owner of the Private Channel.", color=discord.Color.red())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Owner", value=self.bot.get_user(ctx.guild, owner_id).mention)
            await ctx.send(embed=embed)
            raise StopCommand
        else:
            return ctx.guild.get_member(owner_id)

    @private.command(brief="Add users/roles to the channel", usage="[channel] user_or_role [user_or_role] [...]", not_channel_locked=True)
    async def add(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None,
                  *member_or_roles: Union[discord.Member, discord.Role]):
        channel = channel or ctx.channel
        await self.verify_owner(ctx, ctx.author, channel)
        if len(member_or_roles) == 0:
            self.bot.missing_argument("member_or_role")
        existing_overwrites = channel.overwrites
        async with self.bot.conn.execute("""SELECT USER_ID FROM BLOCKED_PRIVATE_CHANNELS WHERE CHANNEL_ID==?""", [channel.id]) as cursor:
            data = [user_id async for user_id in cursor]
        blocked = []
        for member_or_role in member_or_roles:
            if isinstance(member_or_role, discord.Role):
                for member in member_or_role.members:
                    if member.id in data:
                        if not ctx.author.permissions_in(channel).manage_channels:
                            existing_overwrites[member] = discord.PermissionOverwrite(read_messages=False)
                            blocked.append(member)
                existing_overwrites[member_or_role] = discord.PermissionOverwrite(read_messages=True)
            else:
                if member_or_role.id in data:
                    if not ctx.author.permissions_in(channel).manage_channels:
                        existing_overwrites[member_or_role] = discord.PermissionOverwrite(read_messages=False)
                        blocked.append(member_or_role)
                else:
                    existing_overwrites[member_or_role] = discord.PermissionOverwrite(read_messages=True)
        await channel.edit(overwrites=existing_overwrites, reason=f"Users added by {ctx.author}")
        users, roles = partition(member_or_roles, lambda item: isinstance(item, discord.Member))
        embed = Embed(ctx, title="Users/Roles Added", description="The provided users/roles have been added to the channel.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        fields = [("Users Added", "\n".join(user.mention for user in users) or "None"),
                  ("Roles Added", "\n".join(role.mention for role in roles) or "None"),
                  ("Blocked Users Not Added", "\n".join(blocked_user.mention for blocked_user in blocked) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @private.command(brief="Remove users/roles from the channel", usage="[channel] user_or_role [user_or_role] [...]", not_channel_locked=True)
    async def remove(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None,
                     *member_or_roles: Union[discord.Member, discord.Role]):
        channel = channel or ctx.channel
        await self.verify_owner(ctx, ctx.author, channel)
        if len(member_or_roles) == 0:
            self.bot.missing_argument("member_or_role")
        existing_overwrites: dict = channel.overwrites
        for member_or_role in member_or_roles:
            existing_overwrites[member_or_role] = discord.PermissionOverwrite(read_messages=False)
        await channel.edit(overwrites=existing_overwrites, reason=f"Users removed by {ctx.author}")
        users, roles = partition(member_or_roles, lambda item: isinstance(item, discord.Member))
        embed = Embed(ctx, title="Users/Roles Removed", description="The provided users/roles have been removed from the channel.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        fields = [("Users Removed", "\n".join(user.mention for user in users) or "None"),
                  ("Roles Removed", "\n".join(role.mention for role in roles) or "None")]
        await send_embeds_fields(ctx, embed, fields)

    @private.command(brief="Leave this channel so you cannot see it", usage="[channel]", not_channel_locked=True)
    async def leave(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        await self.verify_owner(ctx, ctx.author, channel, verifying_existence_only=True)
        existing_overwrites: dict = channel.overwrites
        existing_overwrites[ctx.author] = discord.PermissionOverwrite(read_messages=False)
        await channel.edit(overwrites=existing_overwrites, reason=f"{ctx.author} left Private Channel")
        embed = Embed(ctx, title="Left Channel", description="You have left the private channel.", color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        return await ctx.send(embed=embed)

    @private.command(brief="Block yourself from being added to the channel. Also leaves the channel.", usage="[channel]")
    async def block(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        await self.leave.fully_run_command(ctx, channel)
        async with self.bot.conn.execute("""INSERT INTO BLOCKED_PRIVATE_CHANNELS(CHANNEL_ID, USER_ID) VALUES (?, ?)""", [channel.id, ctx.author.id]):
            pass
        embed = Embed(ctx, title="Blocked",
                      description="You have been blocked from being able to see the channel. If the user adding can manage the channel, "
                                  "you can be added regardless.",
                      color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        return await ctx.send(embed=embed)

    @private.group(brief="Edit parts of the channel.", invoke_without_command=True)
    async def modify(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @modify.command(name="name", brief="Edit the channel name", usage="[channel] [name]", not_channel_locked=True)
    async def modify_name(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None, *, name: Optional[str] = None):
        channel = channel or ctx.channel
        old_name = channel.name
        await self.verify_owner(ctx, ctx.author, channel)
        if name is None:
            embed = Embed(ctx, title="Name", description="Enter the channel's new name. Channel names can be up to 100 characters.",
                          color=discord.Color.green())
            await ctx.send(embed=embed)
            msg = await self.bot.wait_for("message", check=lambda
                message: message.author == ctx.author and message.channel == ctx.channel and message.content and len(message.content) <= 100,
                                          timeout=120)
            name = msg.content
        if len(name) > 100:
            embed = Embed(ctx, title="Name Too Long", description="The channel name can only be up to 100 characters.", color=discord.Color.red())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Name", value=name)
            embed.add_field(name="Length", value=str(len(name)))
            return await ctx.send(embed=embed)
        else:
            await channel.edit(reason=f"Name Modification by {ctx.author}", name=name)
            embed = Embed(ctx, title="Channel Name Changed", description="The channel name has been successfully changed.",
                          color=discord.Color.green())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Old Name", value=old_name)
            embed.add_field(name="New Name", value=name)
            return await ctx.send(embed=embed)

    @modify.command(name="description", brief="Edit the channel description", usage="[channel] [description]", not_channel_locked=True)
    async def modify_description(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel] = None, *,
                                 description: Optional[str] = None):
        channel = channel or ctx.channel
        old_description = channel.topic
        await self.verify_owner(ctx, ctx.author, channel)
        if description is None:
            embed = Embed(ctx, title="Description",
                          description="Enter the channel's new description. Channel description can be up to 1024 characters.",
                          color=discord.Color.green())
            await ctx.send(embed=embed)
            msg = await self.bot.wait_for("message", check=lambda
                message: message.author == ctx.author and message.channel == ctx.channel and message.content and len(message.content) <= 1024,
                                          timeout=120)
            description = msg.content
        if len(description) > 1024:
            embed = Embed(ctx, title="Description Too Long", description="The channel description can only be up to 1024 characters.",
                          color=discord.Color.red())
            fields = [("Description", description), ("Length", str(len(description)))]
            await send_embeds_fields(ctx, embed, fields)
        else:
            await channel.edit(reason=f"Description Modification by {ctx.author}", topic=description)
            embed = Embed(ctx, title="Channel Description Changed", description="The channel description has been successfully changed.",
                          color=discord.Color.green())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Old Description", value=old_description)
            embed.add_field(name="New Description", value=description)
            return await ctx.send(embed=embed)

    @modify.command(name="owner", brief="Edit the channel's owner", usage="[channel] owner", not_channel_locked=True)
    async def modify_owner(self, ctx: discord.ext.commands.Context, channel: Optional[discord.TextChannel], owner: Optional[discord.Member]):
        channel = channel or ctx.channel
        new_owner = owner or ctx.author
        old_owner = await self.verify_owner(ctx, ctx.author, channel)
        if old_owner == new_owner:
            embed = Embed(ctx, title="Owners are identical", description="The new owner and old owner is identical.", color=discord.Color.red())
            embed.add_field(name="Owner", value=new_owner.id)
            return await ctx.send(embed=embed)
        else:
            async with self.bot.conn.execute("""UPDATE PRIVATE_CHANNELS SET OWNER=? WHERE CHANNEL_ID==?""", [new_owner.id, channel.id]):
                pass
            embed = Embed(ctx, title="Owner Changed", description="The owner has been changed.", color=discord.Color.green())
            embed.add_field(name="Channel", value=channel.mention)
            embed.add_field(name="Old Owner", value=old_owner.mention if old_owner else "None")
            embed.add_field(name="New Owner", value=new_owner.mention)
            return await ctx.send(embed=embed)

    @discord.ext.commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        async with self.bot.conn.execute("""SELECT CHANNEL_ID FROM PRIVATE_CHANNELS WHERE OWNER==?""", [member.id]) as cursor:
            data = [channel_id async for channel_id, in cursor]
        for channel_id in data:
            guild: discord.Guild = member.guild
            channel: Optional[discord.TextChannel] = guild.get_channel(channel_id)
            if channel is not None:
                await channel.set_permissions(member, read_messages=True, reason="Restoring access to private channels owned by user")


def setup(bot: "PokestarBot"):
    bot.add_cog(Private(bot))
    logger.info("Loaded the Private extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Private extension.")
