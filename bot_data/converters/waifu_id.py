import discord.ext.commands


class WaifuIDConverter(discord.ext.commands.Converter):
    async def convert(self, ctx: discord.ext.commands.Context, argument: str):
        if argument.lower().startswith("g") and argument[1:].isnumeric():
            argument = "0-"+argument[1:]
        bracket_id, sep, waifu_gid = argument.partition("-")
        if not sep:
            raise discord.ext.commands.BadArgument("Bracket-Waifu ID separator not found.")
        if not bracket_id.isnumeric():
            raise discord.ext.commands.BadArgument("Bracket ID is not numeric.")
        if not waifu_gid.isnumeric():
            raise discord.ext.commands.BadArgument("Waifu GID is not numeric.")
        else:
            bracket = ctx.bot.bracket_cache.get_bracket(bracket_id)
            return bracket, bracket.get_waifu(waifu_gid)
