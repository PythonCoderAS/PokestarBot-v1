from .base import BaseTitleParser


class GolumpaTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data)
