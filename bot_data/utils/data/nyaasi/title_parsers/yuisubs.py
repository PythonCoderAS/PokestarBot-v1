from .base import BaseTitleParser


class YuiSubsTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data)
