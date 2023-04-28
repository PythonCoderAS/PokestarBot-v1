import discord.ext.commands
from ..utils import HubContext

class WaifuIDConverter(discord.ext.commands.Converter):
    async def convert(self, ctx: HubContext, argument: str):
        if argument.lower().startswith("g-") and argument[2:].isnumeric():
            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Identified a Global Waifu ID.")
            argument = "0-"+argument[2:]
        bracket_id, sep, waifu_gid = argument.partition("-")
        if not sep:
            raise discord.ext.commands.BadArgument("Bracket-Waifu ID separator not found.")
        if not bracket_id.isnumeric():
            raise discord.ext.commands.BadArgument("Bracket ID is not numeric.")
        if not waifu_gid.isnumeric():
            raise discord.ext.commands.BadArgument("Waifu GID is not numeric.")
        else:
            bracket = ctx.bot.bracket_cache.get_bracket(bracket_id)
            waifu = bracket.get_waifu(waifu_gid)
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified ID {argument!r} as {waifu.name!r} (GID #{waifu.gid}).")
