from typing import Dict, Iterable, TYPE_CHECKING

from ..exceptions import DiscordDataException

if TYPE_CHECKING:
    from .bracket import Bracket


class WaifuException(DiscordDataException):
    exception_name = "Waifu Exception"


class InvalidBracketID(WaifuException):
    __slots__ = "id"

    exception_name = "Invalid Bracket ID"

    def __init__(self, bracket_id: int):
        super().__init__(f"The bracket ID {bracket_id} is an invalid bracket ID.")
        self.id = bracket_id


class InvalidBracketName(WaifuException):
    __slots__ = "name"

    exception_name = "Invalid Bracket Name"

    def __init__(self, name: str):
        super().__init__(f"The bracket name `{name}` does not exist for the Guild. Check that your spelling is correct.")
        self.name = name


class TooManyBrackets(WaifuException):
    __slots__ = ("name", "data")

    exception_name = "Too Many Brackets"

    def __init__(self, name: str, **name_to_id_mapping):
        super().__init__(f"The bracket name `{name}` matches multiple brackets.")
        self.data = {v: k for k, v in name_to_id_mapping.items()}

    @property
    def data_string(self):
        return "\n".join(f"**{id}**: {name}" for id, name in self.data.items())

class InvalidWaifuID(WaifuException):
    __slots__ = ("id", "bracket")

    exception_name = "Invalid Waifu ID"

    def __init__(self, id: int, bracket: "Bracket", message: str = "The Waifu ID `{self.id}` is not a valid Waifu ID for the bracket {self.bracket.name}."):
        self.id = id
        self.bracket = bracket
        super().__init__(message.format(self=self))


class InvalidGlobalWaifuID(InvalidWaifuID):

    exception_name = "Invalid Global Waifu ID"

    def __init__(self, gid: int, global_bracket: "Bracket"):
        super().__init__(gid, global_bracket, message="The Global Waifu ID `{self.id}` is not a valid Global Waifu ID.")


class InvalidRank(WaifuException):
    __slots__ = "rank"

    exception_name = "Invalid Waifu Rank"

    def __init__(self, rank: int, bracket: "Bracket"):
        super().__init__(f"The rank {rank} does not exist in the `{bracket.name}` bracket.")
        self.rank = rank


class InvalidName(WaifuException):
    __slots__ = "name"

    noun: str = None
    exception_name = "Invalid Name"

    def __init__(self, name: str):
        super().__init__(f"The name `{name}` does not match the name of any {self.noun} in the system. Please double-check the spelling.")
        self.name = name


class TooManyNames(WaifuException):
    __slots__ = ("original", "names")

    original: str
    names: Iterable[str]

    noun: str = None
    exception_name = "Too Many Names"

    def __init__(self, original_name: str, names: Iterable[str]):
        super().__init__(f"The name `{original_name}` matches multiple {self.noun}s in the system. Please use a more specific variant of the name.")
        self.original = original_name
        self.names = names


class InvalidWaifuName(InvalidName):
    noun = "waifu"
    exception_name = "Invalid Waifu Name"


class TooManyWaifuNames(TooManyNames):
    noun = "waifu"
    exception_name = "Too Many Waifu Names"

    names: Dict[int, str]

    def __init__(self, original_name: str, names: Dict[int, str]):
        super().__init__(original_name, names)
        msg: str = self.args[0]
        msg = msg.rstrip(".") + ", or use the waifu's GID or bracket ID."
        self.args[0] = msg


class InvalidAnimeName(InvalidName):
    noun = "anime"
    exception_name = "Invalid Anime Name"


class TooManyAnimeNames(TooManyNames):
    noun = "anime"
    exception_name = "Too Many Anime Names"
