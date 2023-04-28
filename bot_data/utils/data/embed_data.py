import asyncio
import logging
from typing import Any, Iterable, Tuple

import discord

from .exceptions import InvalidPage

logger = logging.getLogger(__name__)


class EmbedData(tuple, Tuple[discord.Embed, ...]):

    @property
    def pages(self):
        return len(self)

    @property
    def current_page(self):
        return self[self.num - 1]

    def __init__(self, _: Iterable[Any]) -> None:
        super().__init__()
        if len(self) == 0:
            raise ValueError("At least one Embed must exist.")
        self.num = 1
        self.lock = asyncio.Lock()

    def valid_page(self, num: int):
        if num in range(1, self.pages + 1):
            logger.debug("Valid.")
            return True
        else:
            raise InvalidPage(num, self.pages)

    async def next(self):
        async with self.lock:
            num = self.num + 1
        if self.valid_page(num):
            async with self.lock:
                self.num = num
                return self.current_page

    async def previous(self):
        async with self.lock:
            num = self.num - 1
            if self.valid_page(num):
                self.num = num
                return self.current_page

    async def at_page(self, page: int):
        if self.valid_page(page):
            async with self.lock:
                self.num = page
                return self.current_page
