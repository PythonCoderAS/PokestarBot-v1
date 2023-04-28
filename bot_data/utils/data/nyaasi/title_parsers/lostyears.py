from .base import BaseTitleParser


class LostYearsTitleParser(BaseTitleParser):
    @staticmethod
    def _get_episode(item: str):
        if item.isnumeric():
            return {"number": int(item)}
        else:
            return {}

    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data, ep_method=cls._ep_logic_season, extra_bracket_data_callables=[cls._get_episode])
