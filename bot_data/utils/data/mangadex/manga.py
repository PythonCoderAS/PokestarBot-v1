import datetime
import html
import json
from typing import Any, Dict, List, Optional, Union

from .chapter import MangadexChapter, MangadexChapterList
from .cover import MangadexCover
from .enum import Demographic, Relation, Status
from .tag import Tag, data as tag_data
from ..base import BaseDataClass
from ..util import convert_to_enums, dict_copy, dict_copy_mapping


class MangadexManga(BaseDataClass):
    REPR_FIELDS = ("id", "title")
    COMP_FIELD = "id"
    __slots__ = (
        "cover_url", "description", "title", "alt_names", "id", "artist", "author", "status", "demographic", "tags", "last_chapter", "last_volume",
        "last_updated", "language", "hentai", "al_id", "ap_slug", "kt_id", "mu_id", "mal_id", "bw_slug", "amazon_link", "cdjapan_link", "raw_link",
        "relations", "relation", "bayesian_rating", "mean_rating", "rating_users", "views", "follows", "comments", "covers", "chapters",
        "english_link", "nu_slug", "ebj_url", "dj_id")

    cover_url: Optional[str]
    description: Optional[str]
    title: Optional[str]
    alt_names: Optional[List[str]]
    id: Optional[int]
    artist: Optional[List[str]]
    author: Optional[List[str]]
    status: Optional[Status]
    demographic: Optional[Demographic]
    tags: Optional[List[Tag]]
    last_chapter: Optional[int]
    last_volume: Optional[int]
    last_updated: Optional[datetime.datetime]
    language: Optional[str]
    hentai: Optional[bool]
    al_id: Optional[int]
    ap_slug: Optional[str]
    kt_id: Optional[int]
    mu_id: Optional[int]
    mal_id: Optional[int]
    bw_slug: Optional[str]
    amazon_link: Optional[str]
    cdjapan_link: Optional[str]
    raw_link: Optional[str]
    relations: Optional[List["MangadexManga"]]
    relation: Optional[Relation]
    bayesian_rating: Optional[float]
    mean_rating: Optional[float]
    rating_users: Optional[int]
    views: Optional[int]
    follows: Optional[int]
    comments: Optional[int]
    covers: Optional[List[MangadexCover]]
    chapters: Optional[MangadexChapterList]
    english_link: Optional[str]
    nu_slug: Optional[str]
    ebj_url: Optional[str]
    dj_id: Optional[int]

    @staticmethod
    def _serialize_func(obj: Any):
        if isinstance(obj, Tag):
            return obj.id
        elif isinstance(obj, datetime.datetime):
            return int(obj.timestamp())
        elif isinstance(obj, BaseDataClass):
            return obj.json
        else:
            raise TypeError()

    @classmethod
    def from_relation_v1(cls, data: dict) -> "MangadexManga":
        return cls(relation=Relation(data["relation_id"]), id=data["related_manga_id"], title=html.unescape(data["manga_name"]),
                   hentai=bool(data["manga_hentai"]))

    @staticmethod
    def _parse_links(src: Dict[str, Any], dest: Dict[str, Any]):
        dict_copy(src, dest, "al", "kt", "mu", "mal", "dj", suffix="_id", on_item=lambda item: int(item))
        dict_copy_mapping(src, dest, bw="bw_slug", amz="amazon_link", cdj="cdjapan_link", raw="raw_link", engtl="english_link", nu="nu_slug",
                          ebj="ebj_url")

    @staticmethod
    def _parse_rating(src: Dict[str, Any], dest: Dict[str, Any]):
        dict_copy_mapping(src, dest, bayesian="bayesian_rating", mean="mean_rating", on_item=lambda item: float(item))
        dest["rating_users"] = int(str(src["users"]).replace(",", ""))

    @classmethod
    def from_api_v1(cls, manga_id: int, data: dict) -> "MangadexManga":
        final_data = {"id": manga_id}
        manga: dict = data["manga"]
        dict_copy(manga, final_data, "description", "title")
        dict_copy_mapping(manga, final_data, language="lang_flag")
        dict_copy(manga, final_data, "artist", "author", on_item=lambda item: [html.unescape(i) for i in item.split(", ")])
        links = manga["links"]
        cls._parse_links(links, final_data)
        dict_copy(manga, final_data, "last_chapter", "last_volume", "views", "following", "comments",
                  condition=lambda val: str(val).isnumeric() and int(val), on_item=lambda item: int(item))
        dict_copy_mapping(manga["rating"], final_data, bayesian="bayesian_rating", mean="mean_rating", on_item=lambda item: float(item))
        cls._parse_rating(manga["rating"], final_data)
        self = cls(**final_data)
        if "cover_url" in manga:
            self.cover_url = "https://mangadex.org" + manga["cover_url"]
        if "status" in manga:
            self.status = Status(int(manga["status"]))
        if "demographic" in manga:
            self.demographic = Demographic(int(manga["demographic"]))
        self.tags = [tag_data[num] for num in manga["genres"]]
        self.alt_names = [html.unescape(name) for name in manga["alt_names"]]
        self.last_updated = datetime.datetime.utcfromtimestamp(manga["last_updated"])
        self.hentai = bool(int(manga["hentai"]))
        self.relations = [cls.from_relation_v1(item) for item in manga["related"]]
        self.covers = [MangadexCover.from_api_v1(item) for item in manga["covers"]]
        self.chapters = MangadexChapterList.from_chapter_list_v1(data)
        return self

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> "MangadexManga":
        if isinstance(data, str):
            data = json.loads(data)
        self = cls(**data)
        self.last_updated = datetime.datetime.utcfromtimestamp(self.last_updated)
        convert_to_enums(self, status=Status, demographic=Demographic, relation=Relation)
        self.tags = [tag_data[num] for num in self.tags]
        return self

    @classmethod
    def from_relation_v2(cls, data: dict) -> "MangadexManga":
        return cls(relation=Relation(data["type"]), id=data["id"], title=html.unescape(data["title"]), hentai=bool(data["isHentai"]))

    @classmethod
    def from_api_v2(cls, data: dict) -> "MangadexManga":
        actual_data: dict = data["data"]
        final_data = {}
        dict_copy(actual_data, final_data, "title", "description")
        dict_copy(actual_data, final_data, "artist", "author", on_item=lambda item: [html.unescape(i.strip()) for i in item if i])
        publication = actual_data["publication"]
        dict_copy(publication, final_data, "status", "demographic", "language", on_item=lambda item: item)
        dict_copy(actual_data, final_data, "id", "lastChapter", "lastVolume", "views", "following", "comments", do_camel=True,
                  condition=lambda val: str(val).isnumeric() and int(val), on_item=lambda item: int(item))
        dict_copy_mapping(actual_data, final_data, cover_url="mainCover", hentai="isHentai")
        links = actual_data["links"]
        cls._parse_links(links, final_data)
        cls._parse_rating(actual_data["rating"], final_data)
        self = cls(**final_data)
        self.tags = [tag_data[num] for num in actual_data["tags"]]
        convert_to_enums(self, status=Status, demographic=Demographic)
        self.alt_names = [html.unescape(name) for name in actual_data["altTitles"]]
        self.relations = [cls.from_relation_v2(item) for item in actual_data["relations"]]
        return self

    @property
    def artist_str(self):
        return ", ".join(self.artist) if self.artist else None

    @property
    def author_str(self):
        return ", ".join(self.author) if self.author else None

    @property
    def bookwalker_url(self):
        return f"https://bookwalker.jp/{self.bw_slug}" if self.bw_slug is not None else None

    @property
    def mangaupdates_url(self):
        return f"https://www.mangaupdates.com/series.html?id={self.mu_id}" if self.mu_id is not None else None

    @property
    def animeplanet_url(self):
        return f"https://www.anime-planet.com/manga/{self.ap_slug}" if self.ap_slug is not None else None

    @property
    def anilist_url(self):
        return f"https://anilist.co/manga/{self.al_id}/" if self.al_id is not None else None

    @property
    def kitsu_url(self):
        return f"https://kitsu.io/manga/{self.kt_id}" if self.kt_id is not None else None

    @property
    def myanimelist_url(self):
        return f"https://myanimelist.net/manga/{self.mal_id}" if self.mal_id is not None else None

    @property
    def novelupdates_url(self):
        return f"https://www.novelupdates.com/series/{self.nu_slug}/" if self.nu_slug is not None else None

    def add_covers_from_v2(self, data: list):
        self.covers = [MangadexCover.from_api_v2(item) for item in data]

    def add_chapters_data_v2(self, data: dict):
        self.chapters = MangadexChapterList.from_chapter_list_v2(data)

    def add_chapter_data_v2(self, data: dict):
        if self.chapters is None:
            self.chapters = MangadexChapterList()
        self.chapters.append(MangadexChapter.from_api_v2_individual(data))
