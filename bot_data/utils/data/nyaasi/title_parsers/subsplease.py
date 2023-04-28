from .base import BaseTitleParser
from .exceptions import TitleDoesNotMatchException


class SubsPleaseTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        name, ep, version, _, bracket_data, remainder = cls._common_ep_logic(data)
        resolution = hash = None
        for item in bracket_data:
            if " " in item:
                item = item.split(" ")[0]
            if item.endswith("p"):
                res = item[:-1]
                if res.isnumeric():
                    resolution = res
            elif item.isalnum() and len(item) == 8:
                hash = item
        if resolution is None:
            raise TitleDoesNotMatchException(data, "SubsPlease", specific="the resolution could not be identified")
        else:
            self = cls(name, int(ep), int(resolution))
            if version is not None:
                self.version = version
            if hash is not None:
                self.hash = hash
            return self
