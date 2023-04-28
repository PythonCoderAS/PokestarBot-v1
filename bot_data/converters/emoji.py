import re

import discord.ext.commands
from ..utils import HubContext


class EmojiConverter(discord.ext.commands.Converter):
    EMOJI_REGEX = re.compile(r"^<?a?:([a-zA-Z0-9_]+):(?:[0-9]*)>?$")

    def __init__(self, strict_emoji: bool = False):
        self.strict = strict_emoji

    async def convert(self, ctx: HubContext, argument: str):
        try:
            emoji: discord.Emoji = await discord.ext.commands.EmojiConverter().convert(ctx, argument)
        except discord.ext.commands.BadArgument:
            try:
                partial_emoji: discord.PartialEmoji = await discord.ext.commands.PartialEmojiConverter().convert(ctx, argument)
            except discord.ext.commands.BadArgument:
                if match := self.EMOJI_REGEX.match(argument):
                    ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Argument {argument!r} matched emoji regex, returning {match.group(1)!r}")
                    return match.group(1)
                else:
                    if not argument.isalnum():
                        raise discord.ext.commands.BadArgument(
                            "Emoji specified does not match discord.Emoji or discord.PartialEmoji or the emoji syntax and is not alphanumeric.")
                    else:
                        if not self.strict:
                            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Strict matching disabled, returning {argument!r}")
                            return argument
                        else:
                            raise discord.ext.commands.BadArgument("Emoji not matched and strict checking is enabled.")
            else:
                ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Partial emoji {partial_emoji!r} found.")
                return partial_emoji.name
        else:
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Emoji {emoji!r} found.")
            return emoji.name
