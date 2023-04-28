import textwrap
from typing import Any, Optional, Pattern


class CustomTextWrap(textwrap.TextWrapper):
    __slots__ = ("custom_regex",)

    @property
    def wordsep_simple_re(self):
        return self.custom_regex or super().wordsep_simple_re

    @wordsep_simple_re.setter
    def wordsep_simple_re(self, new_regex: Optional[Pattern[str]]):
        self.custom_regex = new_regex

    def __init__(self, *args: Any, regex: Optional[Pattern[str]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_regex = regex
