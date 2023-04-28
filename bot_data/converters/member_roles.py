import logging
from typing import List, Union

from ..utils import HubContext

import discord.ext.commands

logger = logging.getLogger(__name__)


class MemberRolesConverter(discord.ext.commands.Converter):
    @staticmethod
    async def _convert(ctx: HubContext, argument: Union[
        str,  # Member ID as string
        # Role ID as string
        # Username#Discriminator
        # Nickname
        # Role Name
        # Role Number as string
        # Negation of any at the top
        int,  # User ID
        # Role ID
        # Role Number
        discord.Member,  # Member
        discord.Role  # Role
    ]) -> List[discord.Member]:
        """Gets a list of member(s) that fall under the given user ID or role ID.

        The given data can be negated, so that everything **except** the user or role members are returned.

        Accepts:

        * Member ID (as a string or integer)

        * Role ID (as a string or integer)

        * A username in the form `Username#XXXX` where the X's represent the **discriminator**, the numbers that follow
        your username.

        * A role name

        * The role number. This is a list where the bottom-most role is Role #0 and the top-most role is the number of
        roles that exist minus 1. You can specify a negative number to reverse this order, but when doing so,
        the top-most role is #-1 instead of #-0.
        """
        try:
            member = await discord.ext.commands.MemberConverter().convert(ctx, argument)
        except discord.ext.commands.BadArgument:
            try:
                logger.debug("Argument %s not detected as a Member, checking for Role", argument)
                role = await discord.ext.commands.RoleConverter().convert(ctx, argument)
            except discord.ext.commands.BadArgument:
                try:
                    voice_channel = await discord.ext.commands.VoiceChannelConverter().convert(ctx, argument)
                except discord.ext.commands.BadArgument:
                    if isinstance(argument, str):
                        if argument.isnumeric():
                            argument = int(argument)
                        elif argument.lower().lstrip("@") == "everyone":
                            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified everyone, returning the default role (@everyone)")
                            return ctx.guild.default_role
                        else:
                            raise discord.ext.commands.BadArgument("Item `{}` did not represent a member or role or voice channel.".format(argument))
                    if isinstance(argument, int):
                        try:
                            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified a number, returning role in that position")
                            return ctx.guild.roles[argument]
                        except KeyError:
                            raise discord.ext.commands.BadArgument("Item `{}` did not represent a member or role or voice channel.".format(argument))
                else:
                    ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified voice channel, returning it.")
                    return voice_channel
            else:
                ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified role, returning it.")
                return role
        else:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified member, returning it.")
            return member
        raise ValueError("Item `{!r}` did not meet any criteria and did not get raised appropriately.".format(argument))

    async def convert(self, ctx: HubContext, argument: str) -> List[discord.Member]:
        if argument[0] == "!":
            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified a negation, negating the content after it.")
            members = ctx.guild.members
            to_assign = await self.convert(ctx, argument[1:])
            return list(filter(lambda member: member not in to_assign, members))
        member_or_role = await self._convert(ctx, argument)
        if isinstance(member_or_role, discord.Member):
            return [member_or_role]
        elif isinstance(member_or_role, (discord.Role, discord.VoiceChannel)):
            return member_or_role.members
        else:
            raise discord.ext.commands.BadArgument("Invalid type for member_or_role: {}, value: `{!r}`".format(type(member_or_role), member_or_role))
