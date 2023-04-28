from .animetime import AnimeTimeTitleParser
from .ari import AriTitleParser
from .asw import ASWTitleParser
from .dkb import DKBTitleParser
from .edge import EdgeTitleParser
from .ember import EmberTitleParser
from .erairaws import EraiRawsParser
from .ffa import FFATitleParser
from .golumpa import GolumpaTitleParser
from .horriblesubs import HorribleSubsTitleParser
from .judas import JudasTitleParser
from .lostyears import LostYearsTitleParser
from .mlz import MLZTitleParser
from .pantsu import PantsuTitleParser
from .raze import RazeTitleParser
from .riptime import RipTimeTitleParser
from .sheoo import SheooTitleParser
from .ssa import SSATitleParser
from .subsplease import SubsPleaseTitleParser
from .usd import USDTitleParser
from .yuisubs import YuiSubsTitleParser
from .zahuczky import ZahuczkyTitleParser

author_parser_mapping = {
    "HorribleSubs": HorribleSubsTitleParser, "Erai-raws": EraiRawsParser, "_Edge_": EdgeTitleParser, "SmallSizedAnimations": SSATitleParser,
    "sff": AnimeTimeTitleParser, "SubsPlease": SubsPleaseTitleParser, "Ember_Encodes": EmberTitleParser, "FreeForAll": FFATitleParser,
    "mal_lu_zen": MLZTitleParser, "keeso": AriTitleParser, "YuiSubs": YuiSubsTitleParser, "Judas": JudasTitleParser,
    "AkihitoSubsWeeklies": ASWTitleParser, "DKB0512": DKBTitleParser, "rip_time": RipTimeTitleParser, "Golumpa": GolumpaTitleParser,
    "Raze876": RazeTitleParser, "horo747": PantsuTitleParser, "Luxury": USDTitleParser, "Zahuczky": ZahuczkyTitleParser, "Sheoo": SheooTitleParser,
    "LostYears": LostYearsTitleParser
}
