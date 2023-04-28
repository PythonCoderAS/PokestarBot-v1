from ..base import BaseDataClass


class MangadexCover(BaseDataClass):
    REPR_FIELDS = __slots__ = ("volume", "url")
    COMP_FIELD = "volume"
    REQUIRED_FIELDS = ("url",)

    @classmethod
    def from_api_v2(cls, data: dict):
        return cls(**data)

    @classmethod
    def from_api_v1(cls, url: str):
        return cls(url="https://mangadex.org" + url)
