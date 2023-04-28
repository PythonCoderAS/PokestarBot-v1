from .base import BaseTitleParser


class AnimeTimeTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data, name="Anime Time")
