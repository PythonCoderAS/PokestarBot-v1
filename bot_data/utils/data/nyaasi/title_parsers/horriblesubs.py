from .base import BaseTitleParser
from .exceptions import TitleDoesNotMatchException


class HorribleSubsTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        name, ep, _, _, bracket_data, remainder = cls._common_ep_logic(data)
        for item in bracket_data:
            if item.endswith("p"):
                res = item[:-1]
                if res.isnumeric():
                    return cls(name, int(ep), int(res))
        else:
            raise TitleDoesNotMatchException(data, "HorribleSubs", specific="the resolution could not be identified")
