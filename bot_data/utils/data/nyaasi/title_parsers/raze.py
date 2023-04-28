from .base import BaseTitleParser
from .exceptions import TitleDoesNotMatchException


class RazeTitleParser(BaseTitleParser):
    @classmethod
    def parse(cls, data: str):
        cls._check_for_name(data, cls._get_brackets(data))
        string = cls._remove_brackets(data)
        name, sep, other = string.rpartition(" - ")
        if not sep:
            raise TitleDoesNotMatchException(string, "Raze", specific="the anime name could not be identified")
        parts = other.split(" ")
        num = parts[0]
        if not num.isnumeric():
            raise TitleDoesNotMatchException(string, "Raze", specific="the episode number could not be identified")
        for item in parts[1:]:
            if item.endswith("p"):
                res = item[:-1]
                if res.isnumeric():
                    return cls(name, int(num), int(res))
        else:
            raise TitleDoesNotMatchException(string, "Raze", specific="the resolution could not be identified")
