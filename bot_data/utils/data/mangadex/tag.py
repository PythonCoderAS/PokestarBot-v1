from typing import Optional

from ..base import BaseDataClass


class Tag(BaseDataClass):
    REPR_FIELDS = ("id", "name")
    REQUIRED_FIELDS = REPR_FIELDS
    COMP_FIELD = "id"
    __slots__ = ("id", "name", "group", "description")

    id: int
    name: str
    group: Optional[str]
    description: Optional[str]

    def _full_repr(self):
        field_str = ", ".join(f"{name}={getattr(self, name)!r}" for name in self.slots if getattr(self, name))
        return f"{type(self).__name__}({field_str})"


data = {
    1: Tag(id=1, name='4-Koma', group='Format',
           description='4-koma manga present four panels per comic strip that traditionally are the same size and stack on top of each other '
                       'vertically. These titles are usually gag manga, with a single joke or self-contained story in each strip, and little to no '
                       'continuity between the strips. (Source: Anime-Planet)'),
    2: Tag(id=2, name='Action', group='Genre',
           description='Action is about conflict. Whether with guns, blades, fists, or mysterious powers, these manga feature characters in combat '
                       '- either to protect themselves or the things or people they value, or simply as a way of life. (Source: Anime-Planet)'),
    3: Tag(id=3, name='Adventure', group='Genre',
           description='In these manga, characters embark on a journey to explore the world or to search for something. These wanderers travel to '
                       'many places and meet new people, often encountering hardships along the way, or discovering strengths and weaknesses about '
                       'themselves that are revealed throughout the adventure. (Source: Anime-Planet)'),
    4: Tag(id=4, name='Award Winning', group='Format'),
    5: Tag(id=5, name='Comedy', group='Genre',
           description='These manga aim to make you laugh through satire, parody, humorous observations, slapstick scenarios, or absurd antics. '
                       'Bonus points for spitting your drink all over your screen! (Source: Anime-Planet)'),
    6: Tag(id=6, name='Cooking', group='Theme',
           description='Cooking is the focus of these food-themed manga, whether the characters within attend a Culinary School, '
                       'work in a Restaurant or are simply passionate home cooks. These manga may offer step-by-step Recipes for various dishes or '
                       'plating techniques. (Source: Anime-Planet)'),
    7: Tag(id=7, name='Doujinshi', group='Format',
           description='Doujin are a popular type of independently produced and distributed magazine, generally made in small print runs and often '
                       'written by fans of manga and/or anime, including fan-fiction based on pre-existing characters from other authors. (Source: '
                       'Anime-Planet)'),
    8: Tag(id=8, name='Drama', group='Genre',
           description="Drama manga heavily emphasize their characters' emotional development. Whether by experiencing the protagonist’s emotional "
                       "turmoil, viewing heated character interactions, or exploring a passionate romance, any manga that humanizes its characters "
                       "through emphasizing their flaws qualifies as a Drama. (Source: Anime-Planet)"),
    9: Tag(id=9, name='Ecchi', group='Content',
           description='Constant panty shots, bouncing breasts and dubious camera angles are hallmarks of an Ecchi title. These titles are usually '
                       'sexualized and designed to titillate, depicting perverted themes and focusing heavily on the female body. Nosebleeds, '
                       'suspicious hand positions, faceplanting into bosoms, expressive and exaggerated body parts and other tropes characterize '
                       'this genre. Ecchi is all about fanservice, while Borderline H and Smut titles focus more on sexual content. (Source: '
                       'Anime-Planet)'),
    10: Tag(id=10, name='Fantasy', group='Genre',
            description='Fantasy manga take place in a broad range of settings influenced by mythologies, legends, or popular and defining works of '
                        'the genre such as The Lord of the Rings. They are generally characterized by a low level of technological development, '
                        'though fantasy stories can just as easily take place in our modern world, or in a Post-apocalyptic society where '
                        'technology was buried alongside the old world. These manga also tend to feature magic or other extraordinary abilities, '
                        'strange or mysterious creatures, or humanoid races which coexist with humanity or inhabit their own lands removed from '
                        'ours. (Source: Anime-Planet)'),
    11: Tag(id=11, name='Gyaru', group='Theme'),
    12: Tag(id=12, name='Harem', group='Theme',
            description='A harem includes three or more characters who potentially show romantic interest in a male protagonist. The sex, gender, '
                        'or orientation of the harem members is irrelevant as long as they exclusively, or at least primarily, are vying for the '
                        'affections of the same individual - who may or may not reciprocate towards one, several, or none of these romantic rivals. '
                        '(Source: Anime-Planet)'),
    13: Tag(id=13, name='Historical', group='Genre',
            description="The setting of a historical manga takes place at some point in Earth's past. The level of dedication to portraying the "
                        "lifestyles, societies, and technologies of past periods and peoples accurately or believably can vary greatly between "
                        "different works."),
    14: Tag(id=14, name='Horror', group='Genre',
            description='Horror manga create an atmosphere of unease. Like Mystery manga, they encourage viewers to learn more about their world... '
                        'but there may be secrets that are better left unexplored. Through eerie music and sounds, visceral or disturbing imagery, '
                        'or startling moments, works of Horror make you worry about what gruesome thing is coming next. (Source: Anime-Planet)'),
    16: Tag(id=16, name='Martial Arts', group='Theme'),
    17: Tag(id=17, name='Mecha', group='Genre',
            description="Mecha are self-propelling machines that are modeled after humans; some can change into multiple, non-humanoid formats as "
                        "well. They're usually controlled by an internal pilot or by remote, but are sometimes sentient beings that move "
                        "autonomously. A mecha's size ranges from bulky, wearable armor to a massive, towering contraption and beyond. While mecha "
                        "have a wide range of applications, such as making manual labor easier, they are most commonly portrayed as heavily-armed "
                        "war machines. (Source: Anime-Planet)"),
    18: Tag(id=18, name='Medical', group='Genre',
            description='These manga feature medical professionals such as doctors, surgeons and other staff, as they perform their medical duties '
                        'at hospitals, clinics, or other locations. (Source: Anime-Planet)'),
    19: Tag(id=19, name='Music', group='Theme',
            description='These manga are all about the appreciation or performance of music, no matter the genre, or the skill level any musicians '
                        'involved. Music lives in the soul of these characters!'),
    20: Tag(id=20, name='Mystery', group='Genre',
            description="Mystery manga focus on unresolved questions, and the efforts of characters to discover the answers to them. Whether "
                        "curious and deadly events are afoot, or some part of the world itself is strange or inexplicable, or someone's past or "
                        "identity seems strangely shrouded, these characters are set on learning the truth. (Source: Anime-Planet)"),
    21: Tag(id=21, name='Oneshot', group='Format'),
    22: Tag(id=22, name='Psychological', group='Genre',
            description="Psychological manga delve into mental or emotional states of a character in the midst of a difficult situation, "
                        "letting you observe them change as tension increases. Internal monologues are a key feature, allowing narration to delve "
                        "into a character's mind, revealing their innermost ideas and motivations - even as they may be driven to the brink of "
                        "sanity. (Source: Anime-Planet) "),
    23: Tag(id=23, name='Romance', group='Genre',
            description='These manga showcase the joys and hardships of falling in love, whether a schoolgirl has an unrequited crush on her '
                        'senpai, a Love Triangle occurs within a group of friends, or rivals become lovers through competition or their intense '
                        'passion for each other. (Source: Anime-Planet)'),
    24: Tag(id=24, name='School Life', group='Theme'),
    25: Tag(id=25, name='Sci-Fi', group='Genre'),
    28: Tag(id=28, name='Shoujo Ai', group='Genre'),
    30: Tag(id=30, name='Shounen Ai', group='Genre'),
    31: Tag(id=31, name='Slice of Life', group='Genre'),
    32: Tag(id=32, name='Smut', group='Content',
            description="Smut manga are typically written by women, for women, for genres like Shoujo, Josei, and Yaoi. There's a strong focus on "
                        "seduction, characters being swept off their feet, and other buildups to having sex that make you feel hot and bothered. "
                        "Smutty manga frequently, but not always, includes explicit sexual content. (Source: Anime-Planet)"),
    33: Tag(id=33, name='Sports', group='Genre'),
    34: Tag(id=34, name='Supernatural', group='Theme',
            description='Also called paranormal, supernatural events are those modern science has difficulty explaining. Supernaturally oriented '
                        'titles are often steeped in folklore, myth, or Urban Legend. They may involve strange or inexplicable phenomena, '
                        'Psychic Powers or emanations, and/or ghosts or other fantastic creatures. Supernatural events are those that lie at the '
                        'edge of our understanding - they are easy to believe in, but difficult to prove. (Source: Anime-Planet)'),
    35: Tag(id=35, name='Tragedy', group='Genre'),
    36: Tag(id=36, name='Long Strip', group='Format'),
    37: Tag(id=37, name='Yaoi', group='Genre',
            description="Yaoi, also known as Boys' Love or BL in Japan, is a genre mostly written by women, for women, that depicts homosexual "
                        "relationships between men. Japan typically uses this single category for all forms of these relationships, sexual or not. "
                        "In the West, the term Shounen-ai categorizes stories that focus on emotional aspects of relationships, "
                        "while Yaoi categorizes more of the sexual aspects, such as Smut, or explicit content. As Anime-Planet's audience is mostly "
                        "based in the West, we use the Western definition for both Yaoi and Shounen-ai. See BL for a list of both titles. (Source: "
                        "Anime-Planet)"),
    38: Tag(id=38, name='Yuri', group='Genre',
            description="Yuri is a genre that depicts homosexual relationships between women. Japan typically uses this single category for all "
                        "forms of these relationships, sexual or not. In the West, the term Shoujo-ai categorizes stories that focus on the "
                        "emotional aspects of the relationships, while Yuri categorizes more of the sexual aspects and explicit content. As "
                        "Anime-Planet's audience is mostly based in the West, we use the Western definition for both Yuri and Shoujo-ai. (Source: "
                        "Anime-Planet)"),
    40: Tag(id=40, name='Video Games', group='Theme'),
    41: Tag(id=41, name='Isekai', group='Genre'),
    42: Tag(id=42, name='Adaptation', group='Format'),
    43: Tag(id=43, name='Anthology', group='Format'),
    44: Tag(id=44, name='Web Comic', group='Format'),
    45: Tag(id=45, name='Full Color', group='Format'),
    46: Tag(id=46, name='User Created', group='Format'),
    47: Tag(id=47, name='Official Colored', group='Format'),
    48: Tag(id=48, name='Fan Colored', group='Format'),
    49: Tag(id=49, name='Gore', group='Content'),
    50: Tag(id=50, name='Sexual Violence', group='Content'),
    51: Tag(id=51, name='Crime', group='Genre'),
    52: Tag(id=52, name='Magical Girls', group='Genre'),
    53: Tag(id=53, name='Philosophical', group='Genre'),
    54: Tag(id=54, name='Superhero', group='Genre'),
    55: Tag(id=55, name='Thriller', group='Genre'),
    56: Tag(id=56, name='Wuxia', group='Genre'),
    57: Tag(id=57, name='Aliens', group='Theme'),
    58: Tag(id=58, name='Animals', group='Theme'),
    59: Tag(id=59, name='Crossdressing', group='Theme'),
    60: Tag(id=60, name='Demons', group='Theme'),
    61: Tag(id=61, name='Delinquents', group='Theme'),
    62: Tag(id=62, name='Genderswap', group='Theme'),
    63: Tag(id=63, name='Ghosts', group='Theme'),
    64: Tag(id=64, name='Monster Girls', group='Theme'),
    65: Tag(id=65, name='Loli', group='Theme'),
    66: Tag(id=66, name='Magic', group='Theme'),
    67: Tag(id=67, name='Military', group='Theme'),
    68: Tag(id=68, name='Monsters', group='Theme'),
    69: Tag(id=69, name='Ninja', group='Theme'),
    70: Tag(id=70, name='Office Workers', group='Theme'),
    71: Tag(id=71, name='Police', group='Theme'),
    72: Tag(id=72, name='Post-Apocalyptic', group='Theme'),
    73: Tag(id=73, name='Reincarnation', group='Theme'),
    74: Tag(id=74, name='Reverse Harem', group='Theme'),
    75: Tag(id=75, name='Samurai', group='Theme'),
    76: Tag(id=76, name='Shota', group='Theme'),
    77: Tag(id=77, name='Survival', group='Theme'),
    78: Tag(id=78, name='Time Travel', group='Theme'),
    79: Tag(id=79, name='Vampires', group='Theme'),
    80: Tag(id=80, name='Traditional Games', group='Theme'),
    81: Tag(id=81, name='Virtual Reality', group='Theme'),
    82: Tag(id=82, name='Zombies', group='Theme'),
    83: Tag(id=83, name='Incest', group='Theme'),
    84: Tag(id=84, name='Mafia', group='Theme', description='Mafia description'),
    85: Tag(id=85, name='Villainess', group='Theme',
            description='Originating from the term Villainous Noble Lady, the Villainess does nothing but cause trouble, or sometimes even tries to '
                        'kill, the Heroine. At least, that would be the case if the story followed its original course, but due to time leaps, '
                        'reincarnations, transmigrations, or other circumstances, in almost all cases the villainess is no longer the same person '
                        'she was meant to be. This in turn causes changes to the original story, whether they try to follow the original course of '
                        'events, or break them completely.')
}
