from .base import BaseTitleParser


class ZahuczkyTitleParser(BaseTitleParser):
    @classmethod
    def _get_season(cls, item: str):
        if match := cls._season_and_ep_version_pattern.search(item):
            return {"season": int(match.group(1))}
        else:
            return {}

    @classmethod
    def parse(cls, data: str):
        return cls._common_res_logic(data, name="Zahuczky Sub Team", extra_bracket_data_callables=[cls._get_season])
