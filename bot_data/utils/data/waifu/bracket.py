from typing import Any, Dict, List, Optional, Tuple, Type, Union

import aiosqlite
import discord.ext.commands

from .enum import BracketStatus
from .exceptions import InvalidBracketID, InvalidBracketName, InvalidGlobalWaifuID, InvalidRank, InvalidWaifuName, TooManyBrackets, TooManyWaifuNames, InvalidWaifuID
from .waifu import Waifu, UniqueWaifuContainerMixin
from .. import BotBaseDataClass


class Bracket(BotBaseDataClass, UniqueWaifuContainerMixin):
    REPR_FIELDS = ("id", "name", "status", "waifu_count")
    REQUIRED_FIELDS = ("id", "name", "_creator", "status")
    COMP_FIELD = "id"
    __slots__ = ("id", "name", "_creator", "_guild", "status", "_waifu_data", "_rank_data")

    id: int
    name: str
    _creator: Union[discord.Member, discord.User, discord.Object]
    _guild: Optional[Union[discord.Guild, discord.Object]]
    status: BracketStatus
    _waifu_data: Dict[int, Waifu]
    _rank_data: List[int]

    @classmethod
    async def create(cls, name: str, owner: Union[discord.Member, int], guild: Union[discord.Guild, int]) -> "Bracket":
        user_id = owner.id if isinstance(owner, discord.Member) else owner
        guild_id = guild.id if isinstance(guild, discord.Guild) else guild
        async with cls.bot.conn.execute_insert("""INSERT INTO BRACKETS(NAME, GUILD_ID, OWNER_ID) VALUES (?, ?, ?)""",
                                               [name, guild_id, user_id]) as data:
            bracket_id, = data
        return await cls.from_data(bracket_id, name=name, creator=user_id, guild=guild_id, status=BracketStatus.OPEN)

    @classmethod
    async def from_data(cls, id: Optional[int] = None, name: Optional[str] = None, creator: Optional[Union[discord.Member, int]] = None,
                        status: Optional[Union[BracketStatus, int]] = None, guild: Optional[Union[discord.Guild, int]] = None) -> "Bracket":
        # Using this instead of __init__ as __init__ cannot be async.
        if (id, name).count(None) == 2:
            raise ValueError("Either id or name must be specified.")
        elif id is None:
            if guild is None:
                raise ValueError("Guild has to be specified if using name-only lookup.")
            id, name = cls.resolve_bracket_id_from_name(name, guild)
        if (name, creator, guild, status).count(None) > 0:
            async with cls.bot.conn.execute("""SELECT NAME, OWNER_ID, STATUS, GUILD_ID FROM BRACKETS WHERE ID==?""", [id]) as cursor:
                data = await cursor.fetchone()
                if data is None:
                    raise InvalidBracketID(id)
                name, creator, status, guild = data
        if isinstance(guild, int):
            guild = cls.bot.get_guild(guild, return_psuedo_object=True)
        if isinstance(creator, int):
            if isinstance(guild, discord.Guild):
                creator = cls.bot.get_user(guild, creator)
            else:
                creator = cls.bot.get_user(creator, return_psuedo_object=True)
        if isinstance(status, int):
            status = BracketStatus(status)
        return cls(id=id, name=name, _creator=creator, _guild=guild, status=status)

    @classmethod
    async def resolve_bracket_id_from_name(cls, name: str, guild: Union[discord.Guild, int]) -> Tuple[int, str]:
        guild_id = guild.id if isinstance(guild, discord.Guild) else guild
        async with cls.bot.conn.execute("""SELECT ID, NAME FROM BRACKETS WHERE NAME LIKE '%'||?||'%' COLLATE NOCASE AND GUILD_ID==?""",
                                        [name, guild_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) == 0:
            raise InvalidBracketName(name)
        elif len(data) > 1:
            raise TooManyBrackets(name, **{n: id for id, n in data})
        else:
            id, name = data
            return int(id), name

    @property
    def creator(self) -> Union[discord.Member, discord.User, discord.Object]:
        if not isinstance(self._creator, discord.Member):
            if isinstance(self.guild, discord.Guild):
                self._creator = self.bot.get_user(self.guild, self._creator.id)
        else:
            return self._creator

    @property
    def guild(self) -> Optional[Union[discord.Guild, discord.Object]]:
        if self._guild is not None and not isinstance(self._guild, discord.Guild):
            self._guild = self.bot.get_guild(self._guild.id, return_psuedo_object=True)
        return self._guild

    async def waifu_data(self):
        self._waifu_data: Dict[int, Waifu] = {}
        self._rank_data = []
        async with self.bot.conn.execute("""SELECT GID, RANK FROM BRACKET_DATA WHERE BRACKET_ID==? ORDER BY RANK ASC""", [self.id]) as cursor:
            async for gid, rank in cursor:
                self._waifu_data[gid] = await Waifu.from_bracket(self, gid, rank)
                self._rank_data.append(gid)
        async with self.bot.conn.execute("""SELECT GID, USER_ID FROM VOTES WHERE BRACKET_ID==?""", [self.id]) as cursor:
            async for gid, user_id in cursor:
                assert gid in self._waifu_data, f"Check vote data for bracket {self.id} GID {gid} and user ID {user_id}"
                self._waifu_data[gid].votes.append(self.bot.get_user(self.guild, user_id))

    def get_ranked_waifu(self, rank: int):
        if self._rank_data is None:
            return None
        elif rank > len(self._rank_data):
            raise InvalidRank(rank, self)
        return self._waifu_data[self._rank_data[rank]]

    def check_permissions(self, user: discord.Member):
        if self.guild is None:
            return user.id == self.creator.id
        else:
            return user.id == self.creator.id or user.guild_permissions.administrator

    def bracket_in_guild(self, guild: discord.Guild):
        return self.guild.id == guild.id

    @property
    def votable(self):
        length = len(self)
        return self.status == BracketStatus.OPEN and self and length & (length - 1) == 0

    async def resolve_waifu_from_name(self, partial_name: str) -> Waifu:
        candidates = {}
        async with self.bot.conn.execute("""SELECT ID, NAME FROM WAIFUS WHERE NAME LIKE '%'||?||'%' COLLATE NOCASE""", [partial_name]) as cursor:
            candidates.update({id: name async for id, name in cursor})
        async with self.bot.conn.execute(
                """SELECT WAIFUS.ID, WAIFUS.NAME FROM WAIFUS INNER JOIN ALIASES on ALIASES.NAME = WAIFUS.NAME WHERE ALIASES.ALIAS LIKE 
                '%'||?||'%'""") as cursor:
            candidates.update({id: name async for id, name in cursor})
        if len(candidates) == 0:
            raise InvalidWaifuName(partial_name)
        elif len(candidates) > 1:
            raise TooManyWaifuNames(partial_name, candidates)
        else:
            return self.get_waifu(next(iter(candidates.keys())))

    def get_waifu(self, gid: int, exception: Type[InvalidWaifuID] = InvalidWaifuID) -> Waifu:
        if gid not in self._waifu_data:
            raise exception(gid, self)
        else:
            return self._waifu_data[gid]

    @property
    def waifu_count(self):
        return len(self)

    def representation(self, show_status: bool = True, show_owner: bool = True, show_waifu_count: bool = True):
        base = f"**{self.id}**: {self.name}"
        if show_owner:
            base += f" (Owned by {self.creator.mention})"
        if show_status:
            base += f" ({self.status.name.title()})"
        if show_waifu_count:
            base += f" (**{self.waifu_count}** waifus)"
        return base


class BracketContainer(dict, Dict[int, Bracket]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    async def from_conn(cls, conn: aiosqlite.Connection):
        async with conn.execute("""SELECT ID FROM BRACKETS""") as cursor:
            self = cls({id: await Bracket.from_data(id) async for id, in cursor})
        [await bracket.waifu_data() for bracket in self.values()]
        self[0] = Bracket.GLOBAL
        return self

    def filter_guild(self, guild: discord.Guild) -> "BracketContainer":
        return self.filter_attribute("guild", guild)

    def filter_status(self, status: BracketStatus) -> "BracketContainer":
        if status == status.ALL:
            return self
        else:
            return type(self)({bracket_id: bracket for bracket_id, bracket in self.items() if bracket.status in status})

    def get_voting(self, guild: discord.Guild) -> Optional[Bracket]:
        return next(iter(self.filter_guild(guild).filter_status(BracketStatus.VOTABLE).values()), None)

    def get_bracket(self, bracket_id: int, allow_global_id: bool = True) -> Bracket:
        if bracket_id == 0:
            if allow_global_id:
                return Bracket.GLOBAL
            else:
                raise InvalidBracketID(0)
        elif bracket_id not in self:
            raise InvalidBracketID(bracket_id)
        else:
            return self[bracket_id]

    def in_guild(self, bracket_id: int, guild: discord.Guild):
        return self.get_bracket(bracket_id).guild == guild

    async def create_and_add(self, name: str, owner: discord.Member, guild: discord.Guild) -> Bracket:
        bracket = await Bracket.create(name, owner, guild)
        self[bracket.id] = bracket
        return bracket

    def __repr__(self):
        return f"{type(self).__name__}{repr(sorted(id for id in self.keys()))}"

    def attributes(self, *attributes) -> Dict[Bracket, Tuple[Any, ...]]:
        data = {}
        for obj in self.values():
            data[obj] = tuple(getattr(obj, attribute) for attribute in attributes)
        return data

    def filter_attribute(self, attribute: str, expected_value: Any) -> "BracketContainer":
        return type(self)({bracket_id: bracket for bracket_id, bracket in self.items() if getattr(bracket, attribute) == expected_value})
