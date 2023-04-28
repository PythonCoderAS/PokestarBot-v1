import discord.ext.commands

from ..utils import HubContext

class AllConverter(discord.ext.commands.Converter):
    All = object()

    async def convert(self, ctx: HubContext, argument: str):
        if argument.lower() in ["all", "*"]:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Interpreted {argument!r} as a wildcard/All, returning the A sentinel")
            return self.All
        raise discord.ext.commands.BadArgument(f"{argument} != all or *")
