from typing import Optional


class TitleDoesNotMatchException(ValueError):
    __slots__ = ("string", "matcher", "specific")

    def __init__(self, string: str, matcher_name: str, specific: Optional[str] = None):
        msg = f"The string {string!r} does not match for the {matcher_name!r} matcher."
        if specific:
            msg += f" Specifically, {specific}."
        super().__init__(msg)
        self.string: str = string
        self.matcher: str = matcher_name
        self.specific: Optional[str] = specific
