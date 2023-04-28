from ..base import BaseDataClass


class NyaaCategory(BaseDataClass):
    REQUIRED_FIELDS = REPR_FIELDS = __slots__ = ("major", "minor", "name")
    COMP_FIELD = "_mmcomp"

    major: int
    minor: int
    name: str

    def __init__(self, major: int, minor: int, name: str):
        super().__init__(major=major, minor=minor, name=name)

    @property
    def _mmcomp(self):
        return self.major, self.minor

    @property
    def __str__(self):
        return "%s_%s" % self._mmcomp


category_data_dict = {
    "Anime": ("Anime Music Video", "English-translated", "Non-English-translated", "Raw"),
    "Audio": ("Lossless", "Lossy"),
    "Literature": ("English-translated", "Non-English-translated", "Raw"),
    "Live Action": ("English-translated", "Idol/Promotional Video", "Non-English-translated", "Raw"),
    "Pictures": ("Graphics", "Photos"),
    "Software": ("Applications", "Games")
}
category_lookup = {"0_0": NyaaCategory(0, 0, "All categories")}
for major_num, (name, sub_categories) in enumerate(category_data_dict.items(), start=1):
    category_lookup[f"{major_num}_0"] = NyaaCategory(major_num, 0, f"{name}")
    for minor_num, subname in enumerate(sub_categories, start=1):
        category_lookup[f"{major_num}_{minor_num}"] = NyaaCategory(major_num, minor_num, f"{name} - {subname}")

del category_data_dict, major_num, name, sub_categories, minor_num, subname
