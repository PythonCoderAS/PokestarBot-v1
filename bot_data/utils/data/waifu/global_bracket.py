import logging
from typing import Type

from .bracket import Bracket
from .enum import BracketStatus
from .exceptions import InvalidAnimeName, InvalidGlobalWaifuID, InvalidWaifuID, TooManyAnimeNames
from .waifu import Waifu
from .mixins import GlobalMixin

logger = logging.getLogger(__name__)


class GlobalBracket(Bracket):
    @classmethod
    async def create(cls) -> "GlobalBracket":
        self = cls(id=0, name="Global Bracket", _creator=cls.bot.owner_id, status=BracketStatus.OPEN)
        self._waifu_data = {}
        async with cls.bot.conn.execute("""SELECT ID, NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS""") as cursor:
            async for gid, name, description, anime, image in cursor:
                waifu = Waifu(gid=gid, _name=name, _description=description, _anime=anime, _image_link=image)
                await waifu.get_aliases()
                self._waifu_data[gid] = waifu
        return self

    async def resolve_anime_from_name(self, partial_name: str) -> str:
        candidates = []
        async with self.bot.conn.execute("""SELECT ANIME FROM WAIFUS WHERE ANIME LIKE '%'||?||'%' COLLATE NOCASE""", [partial_name]) as cursor:
            candidates.extend(name async for name, in cursor)
        async with self.bot.conn.execute("""SELECT WAIFUS.ANIME FROM WAIFUS INNER JOIN ALIASES ON 
                ALIASES.NAME = WAIFUS.ANIME WHERE ALIASES.ALIAS LIKE '%'||?||'%'""") as cursor:
            candidates.extend(name async for name, in cursor)
        final_candidates = set(candidates)
        if len(final_candidates) == 0:
            raise InvalidAnimeName(partial_name)
        elif len(final_candidates) > 0:
            raise TooManyAnimeNames(partial_name, final_candidates)
        else:
            return next(iter(final_candidates))

    def get_waifu(self, gid: int, exception: Type[InvalidWaifuID] = InvalidGlobalWaifuID) -> Waifu:
        return super().get_waifu(gid, exception)


async def generate_global_data():
    global_bracket = await GlobalBracket.create()
    GlobalMixin.GLOBAL = global_bracket
    return global_bracket
