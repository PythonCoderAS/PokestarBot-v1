class Byte:
    __slots__ = "value"

    _base_mappings = "", "K", "M", "G", "T", "P"

    def __init__(self, byte: int):
        self.value = byte

    def _x_byte_base(self, magnitude):
        result = self.value / (1024 ** magnitude)
        if result > 100:
            return round(result)
        else:
            return round(result, 2)

    @property
    def kilobyte(self):
        return self._x_byte_base(1)

    @property
    def megabyte(self):
        return self._x_byte_base(2)

    @property
    def gigabyte(self):
        return self._x_byte_base(3)

    @property
    def terabyte(self):
        return self._x_byte_base(4)

    @property
    def petabyte(self):
        return self._x_byte_base(5)

    # Defined up to petabyte, since I don't think any storage solution other than an enterprise solution could store more than 1024 petabytes.

    @property
    def largest_representation(self):
        for base, name in enumerate(self._base_mappings):
            val = self._x_byte_base(base)
            if val < 1024:
                return f"{round(val, 2) if isinstance(val, float) else val} {name}B"
        else:
            return f"{round(val, 2) if isinstance(val, float) else val} {name}B"

    def __repr__(self):
        return f"<{type(self).__name__}: {self.largest_representation}>"

    @classmethod
    def from_unit(cls, val: float, unit_char: str):
        base = cls._base_mappings.index(unit_char)
        return cls(round(val * (1024 ** base)))
