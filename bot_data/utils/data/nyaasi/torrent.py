import datetime
import logging
import time
from typing import Dict, List, Optional, Tuple, Union

import bs4
import feedparser

from .category import NyaaCategory
from .enum import NyaaTitleParseWarningLevel
from .title_parsers.base import BaseTitleParser
from .title_parsers.exceptions import TitleDoesNotMatchException
from .title_parsers.mapping import author_parser_mapping
from .util import get_category
from .. import BaseDataClass
from ..byte import Byte
from ..util import dict_copy, remove_prefix

logger = logging.getLogger(__name__)


class NyaaTorrent(BaseDataClass):
    REQUIRED_FIELDS = REPR_FIELDS = ("id", "title")
    COMP_FIELD = "id"
    __slots__ = (
        "title", "id", "timestamp", "seeders", "leechers", "downloads", "infohash", "category", "size", "comments", "trusted", "remake", "user")

    title: str
    id: int
    timestamp: Optional[datetime.datetime]
    seeders: Optional[int]
    leechers: Optional[int]
    downloads: Optional[int]
    infohash: Optional[str]
    category: Optional[NyaaCategory]
    size: Optional[Byte]
    user: Optional[str]
    comments: Optional[int]
    trusted: Optional[bool]
    remake: Optional[bool]

    @staticmethod
    def _bool(val: str):
        if val.lower() == "yes":
            return True
        elif val.lower() == "no":
            return False
        else:
            raise ValueError(f"_bool() excepted 'Yes' or 'No', got {val!r}")

    @classmethod
    def single_from_rss_feed(cls, data: dict):
        final_data = {"id": int(data["id"].split("/")[-1])}
        dict_copy(data, final_data, "title")
        dict_copy(data, final_data, "nyaa_seeders", "nyaa_leechers", "nyaa_downloads", "nyaa_infohash", "nyaa_comments", prefix_to_remove="nyaa_",
                  on_item=lambda item: int(item) if item.isnumeric() else item)
        dict_copy(data, final_data, "nyaa_trusted", "nyaa_remake", prefix_to_remove="nyaa_", on_item=lambda item: cls._bool(item))
        self = cls(**final_data)
        self.category = get_category(data["nyaa_categoryid"])
        num, unit = data["nyaa_size"].split(" ")
        self.size = Byte.from_unit(float(num), unit[0])
        time_data: time.struct_time = data["published_parsed"]
        self.timestamp = datetime.datetime(*time_data[:6])
        return self

    @property
    def view_link(self):
        return f"https://nyaa.si/view/{self.id}"

    @property
    def download_link(self):
        return f"https://nyaa.si/download/{self.id}.torrent"

    @classmethod
    def from_web_page(cls, id: int, data: str):
        final_data = {"id": id}
        soup = bs4.BeautifulSoup(data, features="lxml")
        info_panel: bs4.Tag = soup.find_all("div", class_="panel-body")[0]
        row1, row2, row3, row4, row5 = info_panel.find_all("div", class_="row", recursive=False)
        category_tag, timestamp_tag = row1.find_all("div", class_="col-md-5", recursive=False)
        final_data["category"] = get_category(remove_prefix(str(category_tag.find_all("a")[-1]["href"]).rpartition("?")[-1], "c="))
        final_data["timestamp"] = datetime.datetime.fromtimestamp(int(timestamp_tag["data-timestamp"]))
        submitter_tag, seeder_tag = row2.find_all("div", class_="col-md-5", recursive=False)
        final_data["user"] = str(submitter_tag.text)
        final_data["seeders"] = int(seeder_tag.text)
        info_tag, leecher_tag = row3.find_all("div", class_="col-md-5", recursive=False)
        final_data["leechers"] = int(leecher_tag.text)
        size_tag, downloads_tag = row4.find_all("div", class_="col-md-5", recursive=False)
        num, unit = str(size_tag.text).split(" ")
        final_data["size"] = Byte.from_unit(float(num), unit[0])
        final_data["downloads"] = int(downloads_tag.text)
        final_data["infohash"] = str(row5.find("div", class_="col-md-5").text)
        title_tag, file_tag, comments_tag = soup.find_all("h3", class_="panel-title")
        final_data["title"] = str(title_tag.text)
        final_data["comments"] = int(str(comments_tag.text).rpartition(" - ")[-1])
        final_data = {key: (item.strip() if isinstance(item, str) else item) for key, item in final_data.items()}
        return cls(**final_data)

    def parse_title(self) -> Optional[Union[BaseTitleParser, List[Tuple[str, TitleDoesNotMatchException]]]]:
        exceptions = []
        for user, parser in author_parser_mapping.items():
            try:
                data = parser.parse(self.title)
                self.user = user
                return data
            except TitleDoesNotMatchException as exc:
                if not (exc.specific and "was not found in the bracket data" in exc.specific):
                    exceptions.append((user, exc))
        return exceptions or None


class NyaaTorrentList(list, List[NyaaTorrent]):
    __slots__ = ("parsed_titles", "_filtered")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parsed_titles: Optional[Dict[NyaaTorrent, BaseTitleParser]] = None
        self._filtered: Optional[NyaaTorrentList] = None
        self.sort(reverse=True)
        # Prefer a reversed torrent sort, so when multiple torrents with the same anime and/or episode number are filtered out, the oldest (and
        # probably fastest to download) torrent is left.

    def parse_titles(self, display_warnings: NyaaTitleParseWarningLevel = NyaaTitleParseWarningLevel.NONE):
        if not self.parsed_titles or display_warnings:
            self.parsed_titles = {}
            for item in self:
                response = item.parse_title()
                if isinstance(response, list):
                    if NyaaTitleParseWarningLevel.EXCEPTION in display_warnings:
                        logger.warning("Could not match title %s, skipping", item.title)
                        logger.info("Encountered %d exception(s), displaying them all.", len(response))
                        for user, exc in response:
                            logger.error("%s (for user %s)", author_parser_mapping[user].__name__, user, exc_info=exc)
                    self.parsed_titles[item] = None
                    continue
                elif response is None and NyaaTitleParseWarningLevel.NULL in display_warnings:
                    logger.warning("Could not match title %s, skipping", item.title)
                self.parsed_titles[item] = response
        return self.parsed_titles

    @property
    def valid_titles(self):
        if self._filtered is None:
            valid = {torrent: title for torrent, title in self.parse_titles().items() if title is not None}
            new = type(self)(valid)
            new.parsed_titles = valid
            self._filtered = new
            new._filtered = new
            return new
        else:
            return self._filtered

    def filter_episode(self, num: int):  # Implies valid_title
        valid = {torrent: title for torrent, title in self.valid_titles.parsed_titles.items() if title.number == num}
        new = type(self)(valid)
        new.parsed_titles = valid
        new._filtered = new
        return new

    def filter_resolution(self, res: int):  # Implies valid_title
        valid = {torrent: title for torrent, title in self.valid_titles.parsed_titles.items() if title.resolution == res}
        new = type(self)(valid)
        new.parsed_titles = valid
        new._filtered = new
        return new

    def filter_ids(self, *ids: int):
        return type(self)(torrent for torrent in self if torrent.id not in ids)

    @property
    def episode_mapping(self):
        return {title.number: torrent for torrent, title in self.valid_titles.parsed_titles.items()}

    @property
    def episodes(self):
        return set(title.number for title in self.valid_titles.parsed_titles.values())

    @property
    def max_episode(self):
        return max(self.episodes)

    @property
    def torrent_ids(self):
        return [torrent.id for torrent in self]

    @classmethod
    def from_rss_feed(cls, data: str):
        final_data: dict = feedparser.parse(data)
        return cls(NyaaTorrent.single_from_rss_feed(item) for item in final_data["entries"])

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {len(self)} torrents {len(self.episodes)} episodes max_episode={self.max_episode}>"
