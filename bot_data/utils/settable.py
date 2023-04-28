from typing import Any


class SettableProperty(property):

    def __set__(self, obj: object, value: Any):
        obj.__dict__[self.fget.__name__] = value
