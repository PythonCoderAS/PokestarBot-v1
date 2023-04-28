from .base import BaseTitleParser


class RipTimeTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data, name="Rip Time")
