import functools
from typing import Callable
import discord


class Mention(discord.Object):
    """Stores an object ID that is mentionable"""
    __slots__ = ("id", "symbol")

    id: int
    symbol: str

    @property
    def mention(self):
        return f"<{self.symbol}{self.id}>"

    def __init__(self, id: int, symbol: str):
        super().__init__(id)
        self.symbol = symbol

    def __repr__(self):
        return f"{type(self).__name__}(symbol={self.symbol!r}, id={self.id})"


UserMention: Callable[[int], Mention] = functools.partial(Mention, symbol="@")
RoleMention: Callable[[int], Mention] = functools.partial(Mention, symbol="@&")
ChannelMention: Callable[[int], Mention] = functools.partial(Mention, symbol="#")
