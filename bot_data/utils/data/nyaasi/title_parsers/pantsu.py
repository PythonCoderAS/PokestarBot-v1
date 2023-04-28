from .base import BaseTitleParser


class PantsuTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        real_data = data.replace("_", " ")
        return cls._common_res_logic(real_data, hash_chars=8)
