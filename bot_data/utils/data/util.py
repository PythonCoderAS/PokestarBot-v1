import enum
import html
from typing import Any, Callable, Dict, Optional, Type, TypeVar

_T = TypeVar("_T")


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def remove_suffix(text, suffix):
    if text.endswith(suffix):
        return text[:-len(suffix)]
    return text


def dict_copy(src_dict: Dict[str, Any], dest_dict: Dict[str, Any], *keys, prefix: str = "", suffix: str = "", prefix_to_remove: Optional[str] = None,
              suffix_to_remove: Optional[str] = None, condition: Optional[Callable[[_T], _T]] = None, do_camel: bool = False,
              on_item: Callable[[_T], _T] = lambda item: html.unescape(item)):
    for key in keys:
        if key in src_dict:
            if condition is None or condition(src_dict[key]):
                final_key = key
                if prefix_to_remove:
                    final_key = remove_prefix(final_key, prefix_to_remove)
                if suffix_to_remove:
                    final_key = remove_suffix(final_key, suffix_to_remove)
                final_key = prefix + (camel_to_snake(final_key) if do_camel else final_key) + suffix
                dest_dict[final_key] = on_item(src_dict[key])


def dict_copy_mapping(src_dict: Dict[str, Any], dest_dict: Dict[str, Any], condition: Optional[Callable[[_T], _T]] = None,
                      on_item: Callable[[_T], _T] = lambda item: html.unescape(item), **key_mapping):
    for src_key, dest_key in key_mapping.items():
        if src_key in src_dict:
            if condition is None or condition(src_dict[src_key]):
                dest_dict[dest_key] = on_item(src_dict[src_key])


def convert_to_enums(obj, **enum_mapping: Type[enum.Enum]):
    for attr, enum in enum_mapping.items():
        val = getattr(obj, attr)
        if val is not None:
            setattr(obj, attr, enum(val))


def camel_to_snake(camel: str):
    final = camel[0]
    for char in camel[1:]:
        if char.isupper():
            final += "_" + char.lower()
        else:
            final += char
    return final


def try_num(inst, num: str):
    if num:
        try:
            inst.num = int(num)
        except ValueError:
            try:
                inst.num = float(num)
            except ValueError:
                pass
