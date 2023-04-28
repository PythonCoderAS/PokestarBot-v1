import enum

from .category import NyaaCategory, category_lookup


def _get_category(major: int, minor: int):  # redefined to prevent circular import
    return category_lookup[f"{major}_{minor}"]


class NyaaTitleParseWarningLevel(enum.IntFlag):
    NONE = 0
    EXCEPTION = 1
    NULL = 2
    ALL = 3


class NyaaFilter(enum.IntEnum):
    NONE = 0
    NO_REMAKES = 1
    TRUSTED_ONLY = 2


class NyaaCategoryTypes(enum.Enum):
    All = _get_category(0, 0)
    Anime = _get_category(1, 0)
    AMV = _get_category(1, 1)
    Anime_ENG = _get_category(1, 2)
    Anime_Non_ENG = _get_category(1, 3)
    Anime_Raw = _get_category(1, 4)
    Audio = _get_category(2, 0)
    Audio_Lossless = _get_category(2, 1)
    Audio_Lossy = _get_category(2, 2)
    Literature = _get_category(3, 0)
    Literature_ENG = _get_category(3, 1)
    Literature_Non_ENG = _get_category(3, 2)
    Literature_Raw = _get_category(3, 3)
    Live_Action = _get_category(4, 0)
    Live_Action_ENG = _get_category(4, 1)
    Live_Action_Idol = Live_Action_PV = _get_category(4, 2)
    Live_Action_Non_ENG = _get_category(4, 3)
    Live_Action_Raw = _get_category(4, 4)
    Pictures = _get_category(5, 0)
    Pictures_Graphics = _get_category(5, 1)
    Pictures_Photos = _get_category(5, 2)
    Software = _get_category(6, 0)
    Software_Applications = Software_Apps = _get_category(6, 1)
    Software_Games = _get_category(6, 2)

    @property
    def major(self):
        self.value: NyaaCategory
        return self.value.major

    @property
    def minor(self):
        self.value: NyaaCategory
        return self.value.minor

    @property
    def name(self):
        self.value: NyaaCategory
        return self.value.name

    @property
    def _mmcomp(self):
        self.value: NyaaCategory
        return self.value._mmcomp
