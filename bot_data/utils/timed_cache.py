import collections
import datetime
from typing import Dict, Generic, Iterator, MutableMapping, TypeVar, Union

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")


class TimedCache(Generic[_KT, _VT], MutableMapping[_KT, _VT], collections.MutableMapping):
    def __setitem__(self, k: _KT, v: _VT):
        return self.add(k, v)

    def __delitem__(self, v: _KT):
        return self.remove(v)

    def __getitem__(self, k: _KT) -> _VT:
        if k not in self._data:
            raise KeyError(k)
        return self.get(k)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[_KT]:
        return iter(self._data)

    __slots__ = ("_cache_delta", "_access_data", "_data", "keep_time_on_add")

    @property
    def cache_time(self) -> datetime.timedelta:
        return self._cache_delta

    @cache_time.setter
    def cache_time(self, val: Union[int, datetime.timedelta]):
        if not isinstance(val, datetime.timedelta):
            val = datetime.timedelta(seconds=val)
        self._cache_delta = val

    def __init__(self, cache_time: Union[int, datetime.timedelta] = 5 * 60, keep_time_on_add: bool = False):
        self.cache_time = cache_time
        self._access_data: Dict[_KT, datetime.datetime] = {}
        self._data: Dict[_KT, _VT] = {}
        self.keep_time_on_add = keep_time_on_add

    def inspect_cache(self, key: _KT):
        if key not in self._access_data:
            return
        if datetime.datetime.now() - self._access_data[key] > self.cache_time:
            self.remove(key)

    def add(self, key: _KT, value: _VT):
        self._data[key] = value
        if not (key in self._access_data and self.keep_time_on_add):
            self._access_data[key] = datetime.datetime.now()

    def get(self, key: _KT, default: _T = None) -> Union[_VT, _T]:
        self.inspect_cache(key)
        if key in self._data:
            self._access_data[key] = datetime.datetime.now()
            return self._data[key]
        return default

    def remove(self, key: _KT):
        self._access_data.pop(key)
        self._data.pop(key)

    def __repr__(self):
        return f"{type(self).__name__}(cache_time={self.cache_time!r})"

    __hash__ = None
