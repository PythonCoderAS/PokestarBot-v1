from typing import Optional, Union

from ..base import BaseDataClass


class MangadexGroup(BaseDataClass):
    REPR_FIELDS = __slots__ = ("id", "name")
    COMP_FIELD = "id"
    REQUIRED_FIELDS = ("id",)

    id: int
    name: Optional["str"]

    @classmethod
    def from_api_v2(cls, data: Union[int, dict]):
        if isinstance(data, dict):
            return cls(**data)
        else:
            return cls(id=data)
