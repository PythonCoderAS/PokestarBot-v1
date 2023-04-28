import discord.ext.commands

from ..utils import HubContext
from ..utils.data.waifu import BracketStatus


class BracketStatusConverter(discord.ext.commands.Converter):
    async def convert(self, ctx: HubContext, argument: str):
        if argument.isnumeric():
            try:
                status = BracketStatus(int(argument))
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Interpreted argument {argument!r} as {status}.")
                return status
            except ValueError as exc:
                raise discord.ext.commands.BadArgument(f"The Status code `{argument}` is invalid.") from exc
        else:
            if val := getattr(BracketStatus, argument.upper(), None):
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Interpreted argument {argument!r} as {val}.")
                return val
            else:
                raise discord.ext.commands.BadArgument(f"The Status name `{argument}` is invalid.")
