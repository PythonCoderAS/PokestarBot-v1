from .base import BaseTitleParser


class SheooTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data)
