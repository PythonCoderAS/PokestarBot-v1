from typing import Callable, Iterable, Tuple, TypeVar

_T = TypeVar("_T")


def partition(items: Iterable[_T], check: Callable[[_T], bool]) -> Tuple[Iterable[_T], Iterable[_T]]:
    return filter(check, items), filter(lambda item: not check(item), items)
