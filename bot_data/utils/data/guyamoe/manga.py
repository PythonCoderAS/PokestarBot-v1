import datetime
from typing import Optional

from .chapter import GuyamoeChapterList
from .. import BaseDataClass
from ..util import dict_copy


class GuyamoeManga(BaseDataClass):
    REPR_FIELDS = REQUIRED_FIELDS = ("slug", "title",)
    COMP_FIELD = "slug"
    __slots__ = ("slug", "title", "description", "artist", "author", "cover_url", "chapters", "next_release_timestamp")

    slug: str
    title: str
    description: Optional[str]
    artist: Optional[str]
    author: Optional[str]
    cover_url: Optional[str]
    chapters: Optional[GuyamoeChapterList]
    next_release_timestamp: Optional[datetime.datetime]

    @classmethod
    def from_api(cls, data: dict):
        final_data = {}
        dict_copy(data, final_data, "slug", "title", "description", "artist", "author")
        self = cls(**final_data)
        self.cover_url = "https://guya.moe/" + data["cover"]
        self.chapters = GuyamoeChapterList.from_api(self.slug, data["chapters"])
        self.next_release_timestamp = datetime.datetime.utcfromtimestamp(data["next_release_time"])
        return self
