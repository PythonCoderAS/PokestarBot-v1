import abc
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from .exceptions import TitleDoesNotMatchException
from ...base import BDCMeta, BaseDataClass
from ...util import remove_suffix

_T = TypeVar("_T")


class BaseTitleParser(BaseDataClass):
    REQUIRED_FIELDS = REPR_FIELDS = ("name", "number", "resolution")
    COMP_FIELD = "_comp"
    __slots__ = ("name", "number", "resolution", "version", "season", "hash")

    _bracket_pattern = re.compile(r"([\[\(\{])([^\(\)\[\]\{\}]*)([\)\}\]])")
    _ep_and_version_pattern = re.compile(r"([0-9]+)v([0-9]+)", flags=re.IGNORECASE)
    _season_and_ep_version_pattern = re.compile(r"S([0-9]+)E([0-9]+)", flags=re.IGNORECASE)

    name: str
    number: int
    resolution: int
    version: Optional[int]
    season: Optional[int]
    hash: Optional[str]

    @property
    def _comp(self):
        return self.name.lower(), self.season or -1, self.number, self.resolution, self.version or -1

    @classmethod
    def _get_brackets(cls, string: str):
        matches = []
        for match in cls._bracket_pattern.finditer(string):
            start, end = match.group(1, 3)
            text = match.group(2)
            if (start, end) in [tuple("[]"), tuple("()"), tuple("{}")] and start not in text and end not in text:
                matches.append(text)
        return matches

    @classmethod
    def _remove_brackets(cls, string: str):
        return cls._bracket_pattern.sub("", string)

    def __init__(self, name: str, number: int, resolution: int, **kwargs):
        super().__init__(name=name.strip(), number=number, resolution=resolution, **kwargs)

    @classmethod
    def _check_for_name(cls, string: str, bracket_data: list, name: Optional[str] = None):
        if name is None:
            name = remove_suffix(cls.__name__, "TitleParser")
        if name.lower() not in [item.lower() for item in bracket_data]:
            raise TitleDoesNotMatchException(string, cls.__name__, specific=f"the matcher's name ({name!r}) was not found in the bracket data")

    @classmethod
    def _common_ep_logic(cls, data: str, name: Optional[str] = None, does_batch: bool = True):
        if name is None:
            name = remove_suffix(cls.__name__, "TitleParser")
        bracket_data = cls._get_brackets(data)
        cls._check_for_name(data, bracket_data, name=name)
        remainder = cls._remove_brackets(data).strip().partition(".")[0].strip()  # remove extension
        anime_name, sep, ep = remainder.rpartition(" - ")
        version = None
        if sep is None:
            raise TitleDoesNotMatchException(data, name,
                                             specific=f"the version number could not be identified from the remaining string: {remainder!r}")
        if ep.isnumeric():
            pass
        elif match := cls._ep_and_version_pattern.search(ep):
            ep, version = match.group(1, 2)
        else:
            raise TitleDoesNotMatchException(data, name, specific=f"the version number ({ep!r}) is not numeric")
        return anime_name, ep, version, None, bracket_data, remainder

    @classmethod
    def _ep_logic_season(cls, data: str, name: Optional[str] = None):
        if name is None:
            name = remove_suffix(cls.__name__, "TitleParser")
        bracket_data = cls._get_brackets(data)
        cls._check_for_name(data, bracket_data, name=name)
        remainder = cls._remove_brackets(data).strip().partition(".")[0].strip()  # remove extension
        if match := cls._season_and_ep_version_pattern.search(remainder):
            season, ep = match.group(1, 2)
            remainder = remainder.replace(match.group(0), "")
            return remove_suffix(remainder, " - "), ep, None, season, bracket_data, ""
        else:
            raise TitleDoesNotMatchException(data, name, specific=f"could not identify the episode number")

    @classmethod
    def _common_res_logic(cls, data: str, name: Optional[str] = None,
                          ep_method: Optional[Callable[[str, str], Tuple[str, str, str, str, List[str], str]]] = None,
                          hash_chars: Optional[int] = None,
                          extra_bracket_data_callables: Optional[List[Callable[[str], Dict[str, Optional[Any]]]]] = None):
        if name is None:
            name = remove_suffix(cls.__name__, "TitleParser")
        if ep_method is None:
            ep_method = cls._common_ep_logic
        anime_name, ep, version, season, bracket_data, remainder = ep_method(data, name)
        item_hash = resolution = None
        extra = {}
        for item in bracket_data:
            if " " in item:
                items = item.split(" ")
                for item2 in items:
                    if item2.endswith("p"):
                        res = item2[:-1]
                        if res.isnumeric():
                            resolution = res
                    elif hash_chars and item2.isalnum() and len(item2) == hash_chars:
                        item_hash = item2
                    elif extra_bracket_data_callables:
                        for func in extra_bracket_data_callables:
                            extra.update(func(item2))
            if item.endswith("p"):
                res = item[:-1]
                if res.isnumeric():
                    resolution = res
            elif hash_chars and item.isalnum() and len(item) == hash_chars:
                item_hash = item
            elif extra_bracket_data_callables:
                for func in extra_bracket_data_callables:
                    extra.update(func(item))
        if resolution is not None:
            self = cls(anime_name, int(ep), int(resolution))
            if version is not None:
                self.version = int(version)
            if season is not None:
                season: str
                self.season = int(season)
            if item_hash is not None:
                self.hash = item_hash
            if extra:
                for key, value in extra.items():
                    if value is not None:
                        setattr(self, key, value)
            return self
        else:
            raise TitleDoesNotMatchException(data, name, specific="the resolution could not be identified")

    @classmethod
    @abc.abstractmethod
    def parse(cls: Type[_T], data: str) -> _T:
        raise NotImplementedError("Implement in subclass.")
