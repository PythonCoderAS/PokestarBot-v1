import discord.ext.commands
from ..utils import HubContext


class RolesConverter(discord.ext.commands.RoleConverter):
    async def convert(self, ctx: HubContext, argument: str) -> discord.Role:
        try:
            return await super().convert(ctx, argument)
        except discord.ext.commands.BadArgument as ba:
            if argument.isnumeric():
                try:
                    ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified a number, returning role in that position")
                    return ctx.guild.roles[int(argument)]
                except IndexError:
                    raise ba
