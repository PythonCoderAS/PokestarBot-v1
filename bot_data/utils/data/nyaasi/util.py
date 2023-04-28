from typing import Optional, Union, overload

from .category import NyaaCategory, category_lookup
from .enum import NyaaCategoryTypes, NyaaFilter


@overload
def get_category(major_minor_str: str) -> NyaaCategory:
    pass


@overload
def get_category(major: int, minor: int) -> NyaaCategory:
    pass


def get_category(major_minor_str_or_major: Union[str, int], minor: Optional[int] = None) -> NyaaCategory:
    if isinstance(major_minor_str_or_major, int):
        if minor is None:
            raise ValueError("Minor must be provided if major is provided")
        else:
            major_minor_str = f"{major_minor_str_or_major}_{minor}"
    else:
        major_minor_str = major_minor_str_or_major
    return category_lookup[major_minor_str]


def search_string_builder(query: Optional[str] = None, user: Optional[str] = None, category: Union[str, NyaaCategory, NyaaCategoryTypes] = "0_0",
                          search_filter: NyaaFilter = NyaaFilter.NONE, rss: bool = True):
    query = query.replace(" ", "+") if query else query
    if isinstance(category, str):
        category = get_category(category)
    final = f"https://nyaa.si/?f={int(search_filter)}&c={category.major}_{category.minor}"
    if query:
        final += "&q=" + query
    if user:
        final += "&u=" + user
    if rss:
        final += "&page=rss"
    return final
