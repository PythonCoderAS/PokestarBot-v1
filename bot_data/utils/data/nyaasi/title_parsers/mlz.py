from .base import BaseTitleParser


class MLZTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data, name="mal lu zen")
