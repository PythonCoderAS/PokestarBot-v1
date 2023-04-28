import datetime
from typing import List, Optional

from .. import BaseDataClass
from ..util import try_num


class GuyamoeChapter(BaseDataClass):
    REPR_FIELDS = ("num", "title")
    REQUIRED_FIELDS = ("title",)
    COMP_FIELD = "num"
    __slots__ = ("num", "title", "volume", "pages", "timestamp")

    num: float
    title: str
    volume: Optional[int]
    pages: Optional[List[str]]
    timestamp: Optional[datetime.datetime]

    @classmethod
    def from_api(cls, slug: str, num: str, data: dict):
        self = cls(title=data["title"], volume=int(data["volume"]))
        group_num = next(iter(data["groups"]))
        folder = data["folder"]
        self.timestamp = datetime.datetime.utcfromtimestamp(data["release_date"][group_num])
        try_num(self, num)
        num = self.num
        base = f"https://guya.moe/media/manga/{slug}/chapters/{folder}/{num}"
        self.pages = [f"{base}/{url}" for url in data["groups"][group_num]]
        return self

    @property
    def chapter_str(self):
        return (str(self.num) or "") + ": " + (self.title or "")


class GuyamoeChapterList(list, List[GuyamoeChapter]):
    __slots__ = ()

    @property
    def latest(self) -> Optional[GuyamoeChapter]:
        return sorted(self)[-1] if self else None

    @classmethod
    def from_api(cls, slug: str, data: dict):
        self = cls()
        for num, chap_data in data.items():
            self.append(GuyamoeChapter.from_api(slug, num, chap_data))
        return self

    def __repr__(self) -> str:
        return f"GuyamoeChapterList<{len(self)} chapters, latest={self.latest!r}>"
