import discord.ext.commands
from ..utils import HubContext

from ..const import ANIMELIST_REGEX, ANIME_REGEX, MANGALIST_REGEX


class MALAnimeConverter(discord.ext.commands.Converter):
    def __init__(self, strict: bool = False):
        self.strict = strict

    async def convert(self, ctx: HubContext, argument: str):
        if match := ANIME_REGEX.search(argument):
            anime_id = int(match.group(1))
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified anime ID {anime_id} from {argument!r}.")
            return anime_id
        elif argument.isnumeric() and not self.strict:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified {argument!r} as anime ID.")
            return int(argument)
        else:
            raise discord.ext.commands.BadArgument(f"{argument} is not an MAL anime link or MAL anime ID.")


class MALAnimeListConverter(discord.ext.commands.Converter):
    def __init__(self, strict: bool = False):
        self.strict = strict

    async def convert(self, ctx: HubContext, argument: str):
        if match := ANIMELIST_REGEX.search(argument):
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified user {match.group(1)!r} from {argument!r}.")
            return match.group(1)
        elif "/" not in argument and not self.strict:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified {argument!r} as user.")
            return argument
        else:
            raise discord.ext.commands.BadArgument(f"{argument} is not an MAL Anime List link or username.")


class MALMangaListConverter(discord.ext.commands.Converter):
    def __init__(self, strict: bool = False):
        self.strict = strict

    async def convert(self, ctx: HubContext, argument: str):
        if match := MANGALIST_REGEX.search(argument):
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified user {match.group(1)!r} from {argument!r}.")
            return match.group(1)
        elif "/" not in argument and not self.strict:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified {argument!r} as user.")
            return argument
        else:
            raise discord.ext.commands.BadArgument(f"{argument} is not an MAL Manga List link or username.")
