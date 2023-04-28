import abc
import datetime
import json
from typing import Any, Callable, ClassVar, Dict, Iterable, Optional, Type, Union


class BDCMeta(abc.ABCMeta):
    def __new__(mcs, *args, **kwargs):
        cls: Type["BaseDataClass"] = super().__new__(mcs, *args, **kwargs)
        if "BaseDataClass" not in str(cls.mro()):
            raise TypeError("BDCMeta can only be used for subclasses of BaseDataClass.")
        if cls.COMP_FIELD is not None:
            assert hasattr(cls, cls.COMP_FIELD), f"{cls.COMP_FIELD!r} not in defined attributes."
        if cls.REPR_FIELDS is not None:
            for field in cls.REPR_FIELDS:
                assert hasattr(cls, field), f"{field!r} not in defined attributes."
        return cls


class BaseDataClass(metaclass=BDCMeta):
    REPR_FIELDS: ClassVar[Optional[Iterable[str]]] = None
    COMP_FIELD: ClassVar[Optional[str]] = None
    __slots__: ClassVar[Union[str, Iterable[str]]] = ("_serialize_func",)
    REQUIRED_FIELDS: ClassVar[Optional[Iterable[str]]] = None
    _serialize_func: Optional[Callable[[Any], Union[str, int, bool, float, list, dict, None]]]

    @property
    def slots(self):
        return tuple(val for val in ((self.__slots__,) if isinstance(self.__slots__, str) else self.__slots__) if not val.startswith("_"))

    def __init__(self, **data):
        for key, value in data.items():
            if value is not None:
                setattr(self, key, value)
        if self.REQUIRED_FIELDS:
            for attr in self.REQUIRED_FIELDS:
                if getattr(self, attr) is None:
                    raise ValueError(f"Attribute {attr} must be defined during class initialization.")

    def _repr_field_dict(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in self.REPR_FIELDS}

    def __repr__(self) -> str:
        if self.REPR_FIELDS is None:
            return super().__repr__()
        else:
            field_str = ", ".join(f"{name}={value!r}" for name, value in self._repr_field_dict().items())
            return f"{type(self).__name__}({field_str})"

    def __hash__(self) -> int:
        if self.REPR_FIELDS is None:
            raise TypeError(f"unhashable type: {type(self).__name__!r}")
        else:
            val = 0
            for item in self._repr_field_dict().values():
                val ^= hash(item)
            return val

    def __getattr__(self, item: str) -> None:
        if item in self.__slots__:
            return None
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {item!r}")

    def __eq__(self: "BaseDataClass", other: "BaseDataClass") -> bool:
        if type(other) != type(self):
            return NotImplemented
        else:
            for item in self.slots:
                if not getattr(self, item) == getattr(other, item):
                    return False
            return True

    def __lt__(self: "BaseDataClass", other: "BaseDataClass"):
        if self.COMP_FIELD is None or type(other) != type(self):
            return NotImplemented
        return getattr(self, self.COMP_FIELD) < getattr(other, self.COMP_FIELD)

    def __gt__(self: "BaseDataClass", other: "BaseDataClass"):
        if self.COMP_FIELD is None or type(other) != type(self):
            return NotImplemented
        return getattr(self, self.COMP_FIELD) > getattr(other, self.COMP_FIELD)

    def __le__(self: "BaseDataClass", other: "BaseDataClass"):
        if self.COMP_FIELD is None or type(other) != type(self):
            return NotImplemented
        return getattr(self, self.COMP_FIELD) <= getattr(other, self.COMP_FIELD)

    def __ge__(self: "BaseDataClass", other: "BaseDataClass"):
        if self.COMP_FIELD is None or type(other) != type(self):
            return NotImplemented
        return getattr(self, self.COMP_FIELD) >= getattr(other, self.COMP_FIELD)

    def __bool__(self):
        return bool(self.COMP_FIELD)

    @property
    def dict(self):
        return {name: getattr(self, name) for name in self.slots if getattr(self, name) is not None}

    @property
    def json(self):
        return json.dumps(self.dict, default=self._serialize_func)

    @property
    def _dict(self):
        return {name: getattr(self, name) for name in self.__slots__ if getattr(self, name) is not None}

    def merge(self: "BaseDataClass", other: "BaseDataClass", prefer_other: bool = False):
        if type(other) != type(self):
            raise ValueError("Other class must be the same type.")
        for item in self.slots:
            my_val = getattr(self, item)
            other_val = getattr(other, item)
            if my_val is None and other_val is not None or prefer_other and my_val is not None and other_val is not None:
                setattr(self, item, other_val)

    def __setattr__(self, key: str, value: Any):
        if isinstance(value, datetime.datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        super().__setattr__(key, value)
