import abc
from typing import Any, Collection, Dict, Iterable, Iterator, List, Optional, TYPE_CHECKING, Tuple, Union

import discord

from .exceptions import InvalidGlobalWaifuID
from .mixins import GlobalMixin
from .. import BotBaseDataClass

if TYPE_CHECKING:
    from .bracket import Bracket


class Waifu(BotBaseDataClass, GlobalMixin):
    REPR_FIELDS = ("gid", "name")
    REQUIRED_FIELDS = ("gid",)
    __slots__ = ("gid", "_name", "_description", "_image_link", "_anime", "bracket", "_aliases", "_global", "rank", "votes", "_global_connections")

    gid: int
    _name: str
    _description: str
    _image_link: str
    _anime: str
    bracket: Optional["Bracket"]
    _aliases: Optional[List[str]]
    _global: Optional["Waifu"]
    rank: Optional[int]
    votes: List[Union[discord.Member, discord.User, discord.Object]]

    @property
    def is_global(self) -> bool:
        return self._global is None

    @classmethod
    async def from_bracket(cls, bracket: "Bracket", gid: int, rank: int):
        if gid not in cls.GLOBAL:
            raise InvalidGlobalWaifuID(gid)
        else:
            return cls(bracket=bracket, gid=gid, _global=cls.GLOBAL.get_waifu(gid), rank=rank)

    @property
    def name(self) -> str:
        return self._global._name if self._global else self._name

    @property
    def description(self) -> str:
        return self._global._description if self._global else self._description

    @property
    def image_link(self) -> str:
        return self._global._image_link if self._global else self._image_link

    @property
    def anime(self) -> str:
        return self._global._anime if self._global else self._anime

    @property
    def aliases(self) -> List[str]:
        return self._global._aliases if self._global else self._aliases

    @property
    def unique_id(self):
        if self.bracket is None:
            return f"G{self.gid}"
        else:
            return f"{self.bracket.id}-{self.gid}"

    @property
    def division(self) -> Optional[int]:
        if self.rank is None:
            return None
        else:
            return (self.rank + 1) // 2

    async def get_aliases(self):
        if not self.GLOBAL:
            async with self.connection.execute("""SELECT ALIAS FROM ALIASES WHERE NAME==?""", [self.name]) as cursor:
                self._aliases = [alias async for alias, in cursor]
        else:
            return self._aliases

    async def get_votes(self):
        async with self.connection.execute("""SELECT USER_ID FROM VOTES WHERE BRACKET_ID==? AND GID==?""", [self.bracket.id, self.gid]) as cursor:
            self.votes = [self.bot.get_user(self.bracket.guild, user_id) async for user_id, in cursor]

    def __init__(self, **data):
        super().__init__(**data)
        if self._global:
            self.votes = []
            self.GLOBAL.get_waifu(self.gid)._global_connections.append(self)
        else:
            self._global_connections = MutableWaifuContainer()

    def representation(self, show_rank: bool = False, show_votes: bool = False):
        base = f"(**{self.unique_id}**): [{self.name} (*{self.anime}*)]({self.image_link})"
        if show_rank:
            base = f"{self.rank}. " + base
        if show_votes:
            base += f" ({len(self.votes)} votes)"
        return base

    @property
    def global_connections(self):
        if self._global:
            conns = self._global._global_connections
        else:
            conns = self._global_connections
        return WaifuContainer({num: item for num, item in enumerate(conns, start=1)})

    def __eq__(self: "Waifu", other: "Waifu") -> bool:
        return self.bracket == other.bracket and self.gid == other.gid

    def __lt__(self: "Waifu", other: "Waifu"):
        if self.bracket != other.bracket:
            return NotImplemented
        if self.rank and other.rank:
            return self.rank < other.rank
        elif bool(self.rank) != bool(other.rank):
            return NotImplemented
        else:
            return self.gid < other.gid

    def __gt__(self: "Waifu", other: "Waifu"):
        if self.bracket != other.bracket:
            return NotImplemented
        if self.rank and other.rank:
            return self.rank > other.rank
        elif bool(self.rank) != bool(other.rank):
            return NotImplemented
        else:
            return self.gid > other.gid

    def __le__(self: "Waifu", other: "Waifu"):
        if self.bracket != other.bracket:
            return NotImplemented
        if self.rank and other.rank:
            return self.rank <= other.rank
        elif bool(self.rank) != bool(other.rank):
            return NotImplemented
        else:
            return self.gid <= other.gid

    def __ge__(self: "Waifu", other: "Waifu"):
        if self.bracket != other.bracket:
            return NotImplemented
        if self.rank and other.rank:
            return self.rank >= other.rank
        elif bool(self.rank) != bool(other.rank):
            return NotImplemented
        else:
            return self.gid >= other.gid

    def __bool__(self):
        return True


class WaifuContainerMixin(GlobalMixin):
    @property
    def is_global(self) -> bool:
        return self == self.GLOBAL

    @property
    @abc.abstractmethod
    def _waifu_object_stream(self) -> Iterator[Waifu]:
        return NotImplemented

    async def filter_anime(self, anime: str) -> Tuple[str, "WaifuContainerMixin"]:
        true_name = await self.GLOBAL.resolve_anime_from_name(anime)
        return true_name, self.filter_attributes(anime=true_name)

    def attributes(self, *attributes) -> Dict[Waifu, Tuple[Any, ...]]:
        data = {}
        for obj in self._waifu_object_stream:
            data[obj] = tuple(getattr(obj, attribute) for attribute in attributes)
        return data

    @abc.abstractmethod
    def filter_attributes(self, **attribute_values) -> "WaifuContainerMixin":
        return NotImplemented

    @property
    def total_votes(self):
        return sum(len(waifu.votes) for waifu in self._waifu_object_stream)


class UniqueWaifuContainerMixin(Collection[Waifu], Iterable[Tuple[int, Waifu]], WaifuContainerMixin):

    _waifu_data: Dict[int, Waifu]

    def __contains__(self, obj: object) -> bool:
        return obj in self._waifu_data

    def __len__(self) -> int:
        return len(self._waifu_data)

    def __iter__(self) -> Iterator[Tuple[int, Waifu]]:
        return iter(self._waifu_data.items())

    def __bool__(self):
        return bool(self._waifu_data)

    @property
    def _waifu_object_stream(self) -> Iterator[Waifu]:
        return iter(self._waifu_data.values())

    def filter_attributes(self, **attribute_values) -> "WaifuContainer":
        data = {}
        for id, obj in self:
            for attribute_name, attribute_value in attribute_values.items():
                if getattr(obj, attribute_name) != attribute_value:
                    break
            else:
                data[id] = obj
        return WaifuContainer(waifu_data=data)


class WaifuContainer(UniqueWaifuContainerMixin):
    __slots__ = ("_waifu_data",)

    def __init__(self, waifu_data: Optional[Dict[int, Waifu]] = None):
        self._waifu_data = waifu_data or {}

    def __repr__(self):
        return f"<{type(self).__name__} with {len(self._waifu_data)} waifus>"


class MutableWaifuContainer(list, List[Waifu], WaifuContainerMixin):
    @property
    def _waifu_object_stream(self) -> Iterator[Waifu]:
        return iter(self)

    def filter_attributes(self, **attribute_values) -> "WaifuContainerMixin":
        data = []
        for obj in self:
            for attribute_name, attribute_value in attribute_values.items():
                if getattr(obj, attribute_name) != attribute_value:
                    break
            else:
                data.append(obj)
        return MutableWaifuContainer(data)

    def __repr__(self):
        return type(self).__name__ + super().__repr__()

    def to_waifu_container(self) -> WaifuContainer:
        return WaifuContainer({obj.id: obj for obj in self})
