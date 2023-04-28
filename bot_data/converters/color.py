from typing import Optional, Tuple

import discord.ext.commands

from ..const import css_colors, discord_colors
from ..utils import get_key
from ..utils import HubContext


class ColorConverter(discord.ext.commands.Converter):
    async def convert(self, ctx: HubContext, argument: str) -> Tuple[Optional[str], int]:
        argument = argument.lower()
        if argument.isnumeric():  # RGB color without the #
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Added '#' to numeric argument {argument!r}.")
            argument = "#" + argument
        if argument.startswith("#"):  # RGB color
            if key := get_key(discord_colors, argument):
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Argument {argument!r} found in the discord color mapping, returning that.")
                return key, int(argument[1:], base=16)
            elif key := get_key(css_colors, argument):
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Argument {argument!r} found in the CSS color mapping, returning that.")
                return key, int(argument[1:], base=16)
            else:
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Argument {argument!r} is a random hex, returning that.")
                return None, int(argument[1:], base=16)
        else:
            if argument in discord_colors:
                ctx.hub.add_breadcrumb(category="Argument Parsing",
                                       message=f"Argument {argument!r} found in the discord color mapping, returning that.")
                return argument, int(discord_colors[argument][1:], base=16)
            elif argument in css_colors:
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Argument {argument!r} found in the CSS color mapping, returning that.")
                return argument, int(css_colors[argument][1:], base=16)
            else:
                raise discord.ext.commands.BadArgument(f"The color `{argument}` is not an RGB code nor a valid name for a color.")
