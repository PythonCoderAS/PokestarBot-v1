import abc
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .global_bracket import GlobalBracket


class GlobalMixin(abc.ABC):
    GLOBAL: Optional["GlobalBracket"] = None

    @property
    @abc.abstractmethod
    def is_global(self) -> bool:
        raise NotImplementedError
