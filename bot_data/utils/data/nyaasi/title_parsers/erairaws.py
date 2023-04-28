from .base import BaseTitleParser


class EraiRawsParser(BaseTitleParser):

    @staticmethod
    def _get_version(item: str):
        if item.startswith("v"):
            v = item[1:]
            if v.isnumeric():
                return {"version": int(v)}
        else:
            return {}

    @classmethod
    def parse(cls, data: str):
        data = data.replace(" END ", " ")
        return cls._common_res_logic(data, name="Erai-raws", extra_bracket_data_callables=[cls._get_version])
