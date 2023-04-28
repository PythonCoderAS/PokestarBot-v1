import asyncio
import logging
import random
import sqlite3
import string
from typing import Callable, Iterable, Literal, Optional, TYPE_CHECKING, Union

import aiosqlite
import discord.ext.commands

from . import PokestarBotCog
from ..const import Status
from ..creds import bot_support_server_id, bot_support_waifu_approval_channel_id, bot_support_waifu_image_channel_id
from ..utils import ConformingIterator, CustomContext, Embed, StopCommand, send_embeds_fields

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Waifu(PokestarBotCog):
    @property
    def conn(self):
        return self.bot.conn

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.guide_data = {}
        self.bot.add_check_recursive(self.waifu_war, discord.ext.commands.guild_only())
        self.embed.add_check(self.bot.has_channel("bot-spam"))
        self.pre_create_ran = False

    def log_and_run(self, /, sql: str,
                    arguments: Optional[Iterable[Union[str, int, float, bool, None, Iterable[Union[str, int, float, bool, None]]]]] = None, *,
                    method: Literal["execute", "executemany", "executescript", "execute_insert", "execute_fetchall"] = "execute"):
        meth: Callable[[str, Optional[Iterable[Union[str, int, float, bool, None]]]], aiosqlite.Cursor] = getattr(self.conn, method)
        # logger.debug("Running %s query:\n%s\nArguments: %s", method, sql, arguments)
        return meth(sql, arguments)

    async def pre_create(self):
        if not self.pre_create_ran:
            async with self.log_and_run(
                    """CREATE TABLE IF NOT EXISTS BRACKETS(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL, 
                    STATUS TINYINT DEFAULT 1, GUILD_ID BIGINT NOT NULL, OWNER_ID BIGINT NOT NULL)"""):
                pass
            async with self.log_and_run(
                    """CREATE TABLE IF NOT EXISTS ALIASES(ALIAS TEXT PRIMARY KEY UNIQUE, NAME TEXT NOT NULL, unique(ALIAS, NAME))"""):
                pass
            async with self.log_and_run("""CREATE TABLE IF NOT EXISTS WAIFUS(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL UNIQUE, 
                DESCRIPTION TEXT NOT NULL, ANIME TEXT NOT NULL COLLATE NOCASE, IMAGE TEXT NOT NULL)"""):
                pass
            async with self.log_and_run(
                    """CREATE TABLE IF NOT EXISTS VOTES(ID INTEGER PRIMARY KEY AUTOINCREMENT, USER_ID UNSIGNED BIG INT NOT NULL, BRACKET INTEGER NOT 
                    NULL, DIVISION INTEGER NOT NULL, CHOICE BOOLEAN NOT NULL, UNIQUE(USER_ID, BRACKET, DIVISION))"""):
                pass
            self.pre_create_ran = True

    async def get_conn(self):
        await self.pre_create()
        return self.conn

    async def get_voting(self, guild_id: int):
        await self.get_conn()
        async with self.log_and_run("""SELECT ID FROM BRACKETS WHERE STATUS==? AND GUILD_ID==?""", [Status.VOTABLE, guild_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return None
        else:
            return data[0][0]

    @discord.ext.commands.group(brief="Main group for the Waifu Wars command", invoke_without_command=True, aliases=["ww", "waifuwar"],
                                usage="subcommand", significant=True)
    async def waifu_war(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @waifu_war.command(brief="Create a new bracket", usage="bracket_name", aliases=["createbracket", "cb"])
    @discord.ext.commands.guild_only()
    @discord.ext.commands.cooldown(1, 600, type=discord.ext.commands.BucketType.user)
    async def create_bracket(self, ctx: discord.ext.commands.Context, *, name: str, owner_id: Optional[int] = None):
        await self.get_conn()
        owner_id = owner_id or ctx.author.id
        try:
            async with self.log_and_run("""INSERT INTO BRACKETS(NAME, GUILD_ID, OWNER_ID) VALUES (?, ?, ?)""",
                                        [name, getattr(ctx.guild, "id", None), owner_id]):
                pass
            async with self.log_and_run("""SELECT ID FROM BRACKETS WHERE ID == (SELECT MAX(ID)  FROM BRACKETS);""") as cursor:
                cursor: aiosqlite.Cursor
                data = await cursor.fetchone()
                bracket_id = data[0]
        except sqlite3.IntegrityError:
            embed = Embed(ctx, title="Bracket Exists", color=discord.Color.red(), description="The bracket already exists.")
            async with self.log_and_run("""SELECT ID FROM BRACKETS WHERE NAME==?""", [name]) as cursor:
                data = await cursor.fetchone()
                bracket_id = data[0]
            fields = [("Existing Bracket ID", str(bracket_id))]
            await send_embeds_fields(ctx, embed, fields)
        else:
            async with self.log_and_run(
                    """CREATE TABLE IF NOT EXISTS BRACKET_%s(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL UNIQUE)""" % bracket_id):
                pass
            embed = Embed(ctx, title="Bracket Created", description="The bracket has been created.", color=discord.Color.green())
            fields = [("ID", str(bracket_id)), ("Name", name)]
            await send_embeds_fields(ctx, embed, fields)
            return bracket_id

    async def id_does_not_exist(self, ctx: discord.ext.commands.Context, bracket_id: int):
        embed = Embed(ctx, title="Bracket Does Not Exist",
                      description="The provided bracket does not exist. Use `{}waifu_war brackets` to view the existing brackets.".format(
                          self.bot.command_prefix), color=discord.Color.red())
        embed.add_field(name="Bracket ID", value=str(bracket_id))
        await ctx.send(embed=embed)

    async def needs_bracket(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int]):
        if bracket_id is None:
            await ctx.send(embed=Embed(ctx, title="Bracket ID needed", description="A bracket ID needs to be specified.", color=discord.Color.red()))
            raise StopCommand

    @waifu_war.command(brief="Get information on a bracket.", usage="bracket_id", aliases=["getbracket", "gb", "b", "get_bracket"], significant=True)
    async def bracket(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.needs_bracket(ctx, bracket_id)
        async with self.log_and_run("""SELECT NAME, STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        name, status = data[0]
        embed = Embed(ctx, title=name)
        embed.add_field(name="Bracket ID", value=str(bracket_id))
        embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
        async with self.log_and_run(
                """SELECT BRACKET_{0}.ID, WAIFUS.NAME, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = WAIFUS.NAME""".format(
                    bracket_id)) as cursor:
            data = await cursor.fetchall()
        lines = []
        for waifu_id, name, anime, image in data:
            lines.append(f"**{waifu_id}**: [{name} (*{anime}*)]({image})")
        await send_embeds_fields(ctx, embed, [("Waifus", "\n".join(lines) or "None")])

    async def no_brackets_exist(self, ctx: discord.ext.commands.Context, state: int):
        embed = Embed(ctx, title="No Brackets", description="No brackets exist for the given state.", color=discord.Color.red())
        embed.add_field(name="State", value=str(Status(state)))
        return await ctx.send(embed=embed)

    @waifu_war.command(brief="Get information on all brackets.", usage="[state]", aliases=["getbrackets", "gbs", "bs", "get_brackets"], )
    async def brackets(self, ctx: discord.ext.commands.Context, state: int = 2):
        await self.get_conn()
        try:
            Status(state)
        except ValueError:
            embed = Embed(ctx, title="Invalid State", description="The provided state was invalid.", color=discord.Color.red())
            embed.add_field(name="State", value=str(state))
            embed.add_field(name="Valid States", value="\n".join(f"{enum_state.name}: **{enum_state.value}**" for enum_state in Status))
            await ctx.send(embed=embed)
        else:
            if state == Status.ALL:
                async with self.log_and_run("SELECT ID, NAME, STATUS, OWNER_ID FROM BRACKETS WHERE GUILD_ID==?",
                                            [getattr(ctx.guild, "id", None)]) as cursor:
                    data = await cursor.fetchall()
                if len(data) == 0:
                    return await self.no_brackets_exist(ctx, 0)
                embed = Embed(ctx, title="Brackets", description="Here are the brackets for the given state.")
                fields = []
                for bracket_id, name, status, owner_id in data:
                    fields.append((f"{name} (**{Status(status).name.split('.')[-1].title()}**)",
                                   f"Bracket ID **{bracket_id}**\nOwned By {self.bot.get_user(ctx.guild, owner_id).mention}"))
                await send_embeds_fields(ctx, embed, fields)
            else:
                async with self.log_and_run("SELECT ID, NAME FROM BRACKETS WHERE STATUS == ? AND GUILD_ID==?",
                                            [state, getattr(ctx.guild, "id", None)]) as cursor:
                    data = await cursor.fetchall()
                if len(data) == 0:
                    return await self.no_brackets_exist(ctx, state)
                else:
                    embed = Embed(ctx, title="Brackets", description="Here are the brackets for the given state.")
                    embed.add_field(name="State", value=str(Status(state)))
                    fields = []
                    for bracket_id, name in data:
                        fields.append((name, f"Bracket ID **{bracket_id}**"))
                    await send_embeds_fields(ctx, embed, fields)

    async def bracket_exists(self, ctx: discord.ext.commands.Context, bracket_id: int):
        async with self.log_and_run("""SELECT NAME, STATUS FROM BRACKETS WHERE ID==? AND GUILD_ID==?""",
                                    [bracket_id, getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            await self.id_does_not_exist(ctx, bracket_id)
            raise StopCommand
        else:
            return data

    @waifu_war.command(brief="Get the different animes in the bracket", usage="bracket_id", aliases=["getanimes", "get_animes", "as"])
    async def animes(self, ctx: discord.ext.commands.Context, bracket_id: int):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.bracket_exists(ctx, bracket_id)
        data = self.bracket_exists(ctx, bracket_id)
        name, status = data[0]
        embed = Embed(ctx, title=name)
        embed.add_field(name="Bracket ID", value=str(bracket_id))
        embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
        try:
            async with self.log_and_run(
                    "SELECT ANIME FROM WAIFUS INNER JOIN BRACKET_{0} ON BRACKET_{0}.NAME = WAIFUS.NAME".format(bracket_id)) as cursor:
                data = await cursor.fetchall()
        except sqlite3.OperationalError:
            logger.warning("", exc_info=True)
            return await self.id_does_not_exist(ctx, bracket_id)
        lines = []
        for anime in sorted({item for item, in data}):
            lines.append(f"*{anime}*")
        await send_embeds_fields(ctx, embed, [("Animes", "\n".join(lines) or "None")])

    @waifu_war.command(brief="Get the a division in the bracket", usage="[bracket_id] division_id",
                       aliases=["getdivision", "get_division", "gd", "d"], significant=True)
    async def division(self, ctx: discord.ext.commands.Context, id1: int, id2: Optional[int] = None, *_, _continue=False, _send=True):
        await self.get_conn()
        if id2 is not None:
            bracket_id = id1
            division_id = id2
        else:
            bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
            await self.needs_bracket(ctx, bracket_id)
            division_id = id1
        try:
            async with self.log_and_run("""SELECT COUNT(*) FROM BRACKET_{0}""".format(bracket_id)) as cursor:
                data = await cursor.fetchone()
        except sqlite3.OperationalError:
            logger.warning("", exc_info=True)
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            divisions = data[0] // 2
            if division_id == (divisions + 1):
                return await ctx.send(
                    embed=Embed(ctx, title="Waifu War is complete!", description="You have completed the waifu war bracket! You can now stop voting.",
                                color=discord.Color.green()))
            elif division_id > divisions:
                embed = Embed(ctx, title="Divsion too high",
                              description="The specified division is higher than the highest possibile division. Use `{}waifu_war divisions {}` to "
                                          "check the divisions.".format(
                                  self.bot.command_prefix, bracket_id), color=discord.Color.red())
                embed.add_field(name="Highest Division", value=str(divisions))
                embed.add_field(name="Requested Division", value=str(division_id))
                return await ctx.send(embed=embed)
            else:
                async with self.log_and_run("""SELECT COUNT(*) FROM VOTES WHERE USER_ID==?""", [ctx.author.id]) as cursor:
                    data = (await cursor.fetchone())[0]
                if data == 0 and not _continue and ctx.author.id not in self.guide_data:
                    embed = Embed(ctx, title="Start Guide",
                                  description="You have never voted using the waifu war system. It is recommended that you start the guide. Click "
                                              "the **:white_check_mark:** to begin. However, if you know what you're doing, "
                                              "click the **:no_entry_sign:** to continue.")
                    fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division_id))]
                    messages = await send_embeds_fields(ctx, embed, fields)
                    msg = messages[0]
                    await msg.add_reaction("✅")
                    await msg.add_reaction("🚫")
                    return
                async with self.log_and_run("""SELECT A.ID,A.NAME, 
                        C.ANIME,C.DESCRIPTION,C.IMAGE,B.ID,B.NAME,D.ANIME, D.DESCRIPTION,D.IMAGE FROM (SELECT A.ID, A.NAME FROM BRACKET_{0} A WHERE 
                        A.ID % 2 == 1) AS A JOIN (SELECT B.ID, B.NAME FROM BRACKET_{0} B WHERE B.ID % 2 == 0) AS B ON (CAST((A.ID - 1) / 2 AS 
                        INTEGER) == CAST((B.ID - 1) / 2 AS INTEGER)) JOIN WAIFUS C ON A.NAME == C.NAME JOIN WAIFUS D ON B.NAME == D.NAME WHERE 
                        CAST((B.ID + 1) / 2 AS INTEGER) == ?""".format(bracket_id), [division_id]) as cursor:
                    data = await cursor.fetchone()
                async with self.log_and_run("""SELECT COUNT(*) FROM VOTES WHERE BRACKET==? AND DIVISION==? AND CHOICE==1""",
                                            [bracket_id, division_id]) as cursor:
                    data_left = (await cursor.fetchone())[0]
                async with self.log_and_run("""SELECT COUNT(*) FROM VOTES WHERE BRACKET==? AND DIVISION==? AND CHOICE==0""",
                                            [bracket_id, division_id]) as cursor:
                    data_right = (await cursor.fetchone())[0]
                embed = Embed(ctx, title=f"Division **{division_id}**")
                l_id, l_name, l_anime, l_description, l_image_link, r_id, r_name, r_anime, r_description, r_image_link = data
                fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division_id)),
                          ("Contenders",
                           f"[{l_name} (*{l_anime}*)]({l_image_link}) (Waifu ID **{l_id}**)\n[{r_name} (*{r_anime}*)]({r_image_link}) (Waifu ID **"
                           f"{r_id}**)"),
                          (f"Votes for {l_name}", str(data_left)), (f"Votes for {r_name}", str(data_right))]
                if not _send:
                    return l_name, l_anime, l_description, l_image_link, int(data_left), r_name, r_anime, r_description, r_image_link, int(data_right)
                messages = await send_embeds_fields(ctx, embed, fields)
                msg = messages[0]
                await msg.add_reaction("⬅️")
                await msg.add_reaction("ℹ️")
                await msg.add_reaction("🚫")
                await msg.add_reaction("🇮")
                await msg.add_reaction("➡️")
                guide_val = self.guide_data.get(ctx.author.id, 0)
                if guide_val == 1:
                    await self.guide_step_2(ctx)
                elif guide_val == 4:
                    await self.guide_step_5(ctx)
                return l_name, int(data_left), r_name, int(data_right)

    @waifu_war.command(brief="Get the different divisions in the bracket", usage="[bracket_id]",
                       aliases=["getdivisions", "get_divisions", "gds", "ds"])
    async def divisions(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.needs_bracket(ctx, bracket_id)
        try:
            async with self.log_and_run("""SELECT 
                    A.NAME,C.ANIME,C.DESCRIPTION,C.IMAGE,B.NAME,D.ANIME, D.DESCRIPTION,D.IMAGE FROM (SELECT A.ID, A.NAME FROM BRACKET_{0} A WHERE 
                    A.ID % 2 == 1) AS A JOIN (SELECT B.ID, B.NAME FROM BRACKET_{0} B WHERE B.ID % 2 == 0) AS B ON (CAST((A.ID - 1) / 2 AS INTEGER) == 
                    CAST((B.ID - 1) / 2 AS INTEGER)) JOIN WAIFUS C ON A.NAME == C.NAME JOIN WAIFUS D ON B.NAME == D.NAME""".format(
                bracket_id)) as cursor:
                data = await cursor.fetchall()
        except sqlite3.OperationalError:
            logger.warning("", exc_info=True)
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            embed = Embed(ctx, title="Bracket Divisions",
                          description="A division is a matchup between two waifus. The waifu with more votes will move on while the waifu with less "
                                      "votes will lose.")
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            lines = []
            for division, item in enumerate(data, start=1):
                l_name, l_anime, l_description, l_image_link, r_name, r_anime, r_description, r_image_link = item
                lines.append(f"Division **{division}**: [{l_name} (*{l_anime}*)]({l_image_link}) ***v.*** [{r_name} (*{r_anime}*)]({r_image_link})")
            await send_embeds_fields(ctx, embed, [("Divisions", "\n".join(lines) or "None")])

    @waifu_war.command(brief="Get the characters of an anime in the bracket", usage="[bracket_id] anime_name",
                       aliases=["getanime", "get_anime", "a", "ga"], )
    async def anime(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None, *, anime_name: str):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is not None:
            try:
                async with self.log_and_run(
                        "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = "
                        "WAIFUS.NAME WHERE ANIME LIKE '%'||?||'%'".format(bracket_id), [anime_name]) as cursor:
                    data = await cursor.fetchall()
            except sqlite3.OperationalError:
                logger.warning("", exc_info=True)
                return await self.id_does_not_exist(ctx, bracket_id)
            else:
                async with self.log_and_run(
                        """SELECT BRACKET_{0}.ID, BRACKET_{0}.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON 
                        BRACKET_{0}.NAME = WAIFUS.NAME INNER JOIN ALIASES on ALIASES.NAME = WAIFUS.ANIME WHERE ALIAS LIKE '%'||?||'%'""".format(
                            bracket_id), [anime_name]) as cursor:
                    data2 = await cursor.fetchall()
                    data.extend(data2)
                seen = []
                for item in data.copy():
                    waifu_id, name, description, anime, image_link = item
                    if waifu_id in seen:
                        data.remove(item)
                    else:
                        seen.append(waifu_id)
            animes = {anime for waifu_id, name, description, anime, image_link in data}
            if len(animes) < 1:
                embed = Embed(ctx, title="Anime Does Not Exist", description="The provided anime does not exist for the bracket.",
                              color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                embed.add_field(name="Anime Name", value=anime_name)
                return await ctx.send(embed=embed)
            elif len(animes) > 1:
                embed = Embed(ctx, title="Duplicate Animes", description="More than one anime matched the provided name.", color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                await send_embeds_fields(ctx, embed, [("Animes", "\n".join(f"*{anime}*" for anime in animes))])
            else:
                ids = [f"**{waifu_id}**: [{name}]({image_link})" for waifu_id, name, description, anime, image_link in data]
                awaifu_id, name, description, anime, image_link = data[0]
                async with self.log_and_run("""SELECT ALIAS FROM ALIASES WHERE NAME = ?""", [anime]) as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title=f"*{anime}*")
                fields = [("Waifu Bracket", str(bracket_id)), ("Aliases", "\n".join(f"*{alias}*" for alias, in data) or "None"),
                          ("Number of Waifus", str(len(ids))), ("Waifus", "\n".join(ids))]
                await send_embeds_fields(ctx, embed, fields)
        else:
            async with self.log_and_run("SELECT ID, NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS  WHERE ANIME LIKE '%'||?||'%'",
                                        [anime_name]) as cursor:
                data = await cursor.fetchall()
            async with self.log_and_run(
                    """SELECT ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS INNER JOIN ALIASES on ALIASES.NAME = WAIFUS.ANIME WHERE ALIAS 
                    LIKE '%'||?||'%'""",
                    [anime_name]) as cursor:
                data2 = await cursor.fetchall()
                data.extend(data2)
            seen = []
            for item in data.copy():
                waifu_id, name, description, anime, image_link = item
                if waifu_id in seen:
                    data.remove(item)
                else:
                    seen.append(waifu_id)
            animes = {anime for waifu_id, name, description, anime, image_link in data}
            if len(animes) < 1:
                embed = Embed(ctx, title="Anime Does Not Exist", description="The provided anime does not exist.",
                              color=discord.Color.red())
                embed.add_field(name="Anime Name", value=anime_name)
                return await ctx.send(embed=embed)
            elif len(animes) > 1:
                embed = Embed(ctx, title="Duplicate Animes", description="More than one anime matched the provided name.", color=discord.Color.red())
                await send_embeds_fields(ctx, embed, [("Animes", "\n".join(f"*{anime}*" for anime in animes))])
            else:
                ids = [f"Global ID **{waifu_id}**: [{name}]({image_link})" for waifu_id, name, description, anime, image_link in data]
                awaifu_id, name, description, anime, image_link = data[0]
                async with self.log_and_run("""SELECT ALIAS FROM ALIASES WHERE NAME = ?""", [anime]) as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title=f"*{anime}*")
                fields = [("Aliases", "\n".join(f"*{alias}*" for alias, in data) or "None"), ("Number of Waifus", str(len(ids))),
                          ("Waifus", "\n".join(ids))]
                await send_embeds_fields(ctx, embed, fields)

    @staticmethod
    def score_word(phrase: str) -> int:
        count = 0
        for char in phrase:
            if char in string.ascii_uppercase:
                count += 1
        return count

    @waifu_war.command(brief="Normalize cases on the Anime field", aliases=["normalizecases", "normalizeanime", "normalize_cases", "na", "nc"],
                       enabled=False)
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def normalize_anime(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        async with self.log_and_run("""SELECT ID, ANIME FROM WAIFUS ORDER BY ID""") as cursor:
            data = await cursor.fetchall()
        count_dict = {}
        for waifu_id, anime in data:
            anime: str
            score = self.score_word(anime)
            if anime in count_dict and self.score_word(count_dict[anime.lower()]) < score:
                count_dict[anime.lower()] = anime
            elif anime not in count_dict:
                count_dict[anime.lower()] = anime
        for anime_name in count_dict.values():
            async with self.log_and_run("""UPDATE WAIFUS SET ANIME=? WHERE ANIME=?""", [anime_name] * 2):
                pass
        await ctx.send(embed=Embed(ctx, title="Anime Names Normalized", description="Anime Names have been normalized.", color=discord.Color.green()))

    @waifu_war.command(brief="Get information on a waifu", usage="bracket_id waifu_id or waifu_name", aliases=["getwaifu", "w", "get_waifu"],
                       significant=True)
    async def waifu(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None, *, id_or_name: Optional[Union[int, str]] = None,
                    _resolve: bool = False, _id: bool = False):
        await self.get_conn()
        if not (bracket_id or id_or_name):
            self.bot.missing_argument("id_or_name")
        if bracket_id is not None and id_or_name is None:
            id_or_name = bracket_id
            bracket_id = None
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        if type(bracket_id) == object:
            bracket_id = None
        if bracket_id is not None:
            if isinstance(id_or_name, str):
                query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                        "WAIFUS.NAME WHERE WAIFUS.NAME LIKE '%'||?||'%'".format(bracket_id)
            else:
                query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                        "WAIFUS.NAME WHERE BRACKET_{0}.ID==?".format(bracket_id)
            try:
                async with self.log_and_run(query, [id_or_name]) as cursor:
                    data = await cursor.fetchall()
            except sqlite3.OperationalError:
                logger.warning("", exc_info=True)
                return await self.id_does_not_exist(ctx, bracket_id)
            if isinstance(id_or_name, str):
                async with self.log_and_run(
                        """SELECT BRACKET_{0}.ID, ALIASES.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN ALIASES on BRACKET_{0}.NAME = 
                        ALIASES.NAME INNER JOIN WAIFUS ON BRACKET_{0}.NAME = WAIFUS.NAME WHERE ALIAS LIKE '%'||?||'%'""".format(bracket_id),
                        [id_or_name]) as cursor:
                    data2 = await cursor.fetchall()
                data.extend(data2)
            seen = []
            for item in data.copy():
                waifu_id, name, description, anime, image_link = item
                if waifu_id in seen:
                    data.remove(item)
                else:
                    seen.append(waifu_id)
            if len(data) < 1:
                embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist for the bracket.",
                              color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                if isinstance(id_or_name, str):
                    embed.add_field(name="Given Waifu Name", value=id_or_name)
                else:
                    embed.add_field(name="Given Bracket Waifu ID", value=str(id_or_name))
                await ctx.send(embed=embed)
                if _resolve:
                    raise StopCommand()
                return
            elif len(data) > 1:
                ids = [f"**{waifu_id}**: [{name} (*{anime}*)]({image_link})" for waifu_id, name, description, anime, image_link in data]
                embed = Embed(ctx, title="Duplicate Named Waifus",
                              description="There are multiple waifus with the same name. Use an ID instead of a name to search for them. The "
                                          "bracket waifu IDs that share the same name have been provided.")
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                await send_embeds_fields(ctx, embed, [("IDs", "\n".join(str(id) for id in ids))])
                if _resolve:
                    raise StopCommand()
                return
            else:
                waifu_id, name, description, anime, image_link = data[0]
                if _resolve:
                    if _id:
                        return waifu_id
                    return name
                async with self.log_and_run("""SELECT ALIAS FROM ALIASES WHERE NAME = ?""", [name]) as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title=name, description=description)
                embed.set_image(url=image_link)
                fields = [("Anime", anime), ("Bracket Waifu ID", str(waifu_id)), ("Waifu Bracket", str(bracket_id)),
                          ("Aliases", "\n".join(alias for alias, in data) or "None")]
                await send_embeds_fields(ctx, embed, fields)
        else:
            if isinstance(id_or_name, str):
                query = "SELECT ID, NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS WHERE NAME LIKE '%'||?||'%'".format(bracket_id)
            else:
                query = "SELECT ID, NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS WHERE ID==?".format(bracket_id)
            async with self.log_and_run(query, [id_or_name]) as cursor:
                data = await cursor.fetchall()
            if isinstance(id_or_name, str):
                async with self.log_and_run(
                        """SELECT ID, ALIASES.NAME, DESCRIPTION, ANIME, IMAGE FROM WAIFUS INNER JOIN ALIASES on ALIASES.NAME = WAIFUS.NAME WHERE 
                        ALIAS LIKE '%'||?||'%'""", [id_or_name]) as cursor:
                    data2 = await cursor.fetchall()
                data.extend(data2)
            seen = []
            for item in data.copy():
                waifu_id, name, description, anime, image_link = item
                if waifu_id in seen:
                    data.remove(item)
                else:
                    seen.append(waifu_id)
            if len(data) < 1:
                embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist globally.",
                              color=discord.Color.red())
                if isinstance(id_or_name, str):
                    embed.add_field(name="Given Waifu Name", value=id_or_name)
                else:
                    embed.add_field(name="Given Waifu ID", value=str(id_or_name))
                await ctx.send(embed=embed)
                if _resolve:
                    raise StopCommand()
                return
            elif len(data) > 1:
                ids = [f"**{waifu_id}**: [{name} (*{anime}*)]({image_link})" for waifu_id, name, description, anime, image_link in data]
                embed = Embed(ctx, title="Duplicate Named Waifus",
                              description="There are multiple waifus with the same name. Use an ID instead of a name to search for them. The global "
                                          "waifu IDs that share the same name have been provided.")
                await send_embeds_fields(ctx, embed, [("IDs", "\n".join(str(id) for id in ids))])
                if _resolve:
                    raise StopCommand()
                return
            else:
                waifu_id, name, description, anime, image_link = data[0]
                if _resolve:
                    if _id:
                        return waifu_id
                    return name
                async with self.log_and_run("""SELECT ALIAS FROM ALIASES WHERE NAME = ?""", [name]) as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title=name, description=description)
                embed.set_image(url=image_link)
                fields = [("Anime", anime), ("Global Waifu ID", str(waifu_id)), ("Aliases", "\n".join(alias for alias, in data) or "None")]
                await send_embeds_fields(ctx, embed, fields)

    @waifu_war.command(brief="Add a waifu to the global waifu table", usage="name image_link [description]", aliases=["addwaifu", "aw"])
    async def add_waifu(self, ctx: discord.ext.commands.Context, name: str, image_link: str, anime: str, *, description: str,
                        _reaction: bool = False):
        await self.get_conn()
        if not image_link.startswith("http"):  # Probably a bad URL
            embed = Embed(ctx, title="Invalid URL", description="The provided URL is invalid.", color=discord.Color.red())
            embed.add_field(name="URL", value=image_link)
            return await ctx.send(embed=embed)
        async with self.log_and_run("""SELECT NAME FROM WAIFUS""") as cursor:
            data = [item.casefold() for item, in await cursor.fetchall()]
        if name.casefold() in data:
            embed = Embed(ctx, title="Waifu Already Exists",
                          description=f"The waifu already exists. Request a modification otherwise with `{self.bot.command_prefix}waifu_war modify`.",
                          color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=name)
            return await ctx.send(embed=embed)
        elif ctx.author.id != self.bot.owner_id:
            embed = Embed(ctx, title=f"Waifu Request", description=description)
            embed.set_image(url=image_link)
            embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                             icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
            embed.add_field(name="Waifu Name", value=name)
            embed.add_field(name="Anime", value=anime)
            embed.add_field(name="Status", value="Open")
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
            msg = await chan.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🚫")
            await msg.add_reaction("🇦")
            await msg.add_reaction("🇩")
            await msg.add_reaction("🇮")
            await msg.add_reaction("🇳")
            embed = Embed(ctx, title="Request Sent",
                          description=f"Your waifu request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                          color=discord.Color.green())
            embed.add_field(name="Request Message Link", value=msg.jump_url)
            return await ctx.send(embed=embed)
        else:
            async with self.log_and_run("""INSERT INTO WAIFUS(NAME, DESCRIPTION, ANIME, IMAGE) VALUES (?, ?, ?, ?)""",
                                        [name, description, anime, image_link]) as cursor:
                await cursor.execute("""SELECT ID FROM WAIFUS WHERE ID = (SELECT MAX(ID) FROM WAIFUS)""")
                data = await cursor.fetchone()
                item_id = data[0]
        if not _reaction:
            await self.waifu(ctx, bracket_id=object(), id_or_name=item_id)

    @waifu_war.command(brief="Add a waifu interactively over the span of multiple messages", aliases=["awi"])
    async def add_waifu_interactive(self, ctx: discord.ext.commands.Context):
        embed = Embed(ctx, title="Name", description="Type the name of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        name = message.content
        embed = Embed(ctx, title="Anime", description="Type the anime of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        anime = message.content
        embed = Embed(ctx, title="Description", description="Type the description of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        description = message.content
        embed = Embed(ctx, title="Image", description="Send the image of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: (message.author == ctx.author and message.channel == ctx.channel) and (
                (message.content or "").startswith("http") or message.attachments), timeout=120)
        if message.content:
            image = message.content
        else:
            attachment: discord.Attachment = message.attachments[0]
            file: discord.File = await attachment.to_file()
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_image_channel_id)
            msg = await chan.send(embed=Embed(ctx, title=name), file=file)
            attachment_2: discord.Attachment = msg.attachments[0]
            image = attachment_2.url
        await self.add_waifu(ctx, name, image, anime, description=description)

    @waifu_war.command(brief="Add an alias interactively over the span of multiple messages", aliases=["aai"])
    async def add_alias_interactive(self, ctx: discord.ext.commands.Context):
        embed = Embed(ctx, title="Name", description="Type the name of the waifu you want to add an alias for.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        name = message.content
        aliases = []
        while True:
            embed = Embed(ctx, title="Alias", description="Type the name of the alias you want to add to the waifu or type `stop` to stop.",
                          color=discord.Color.green())
            await ctx.send(embed=embed)
            message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                              timeout=120)
            if message.content.lower() == "stop":
                break
            aliases.append(message.content)
        await self.add_alias(ctx, name, *aliases)

    @waifu_war.group(invoke_without_command=True, brief="Modify waifu information.", aliases=["mod"])
    async def modify(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @modify.command(name="name", brief="Change the name of a waifu", usage="waifu_name")
    async def modify_name(self, ctx: discord.ext.commands.Context, *, waifu_name: Union[int, str], _reaction: bool = False):
        await self.get_conn()
        old_waifu_name = await self.waifu.fully_run_command(ctx, id_or_name=waifu_name, _resolve=True)
        async with self.log_and_run("""SELECT NAME FROM WAIFUS""") as cursor:
            data = [item.casefold() for item, in await cursor.fetchall()]
        if old_waifu_name.casefold() not in data:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="A waifu with this name does not exist.", color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=old_waifu_name)
            return await ctx.send(embed=embed)
        embed = Embed(ctx, title="Name", description="Type the new name of the waifu.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        new_waifu_name = message.content
        if new_waifu_name.casefold() in data and old_waifu_name.casefold() != new_waifu_name.casefold():
            embed = Embed(ctx, title="Waifu Name Already Exists", description="The new waifu name will conflict with the name of another waifu.",
                          color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=new_waifu_name)
            return await ctx.send(embed=embed)
        if ctx.author.id != self.bot.owner_id:
            embed = Embed(ctx, title="Waifu Rename Request")
            embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                             icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
            embed.add_field(name="Old Name", value=old_waifu_name)
            embed.add_field(name="New Name", value=new_waifu_name)
            embed.add_field(name="Status", value="Open")
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
            msg = await chan.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🚫")
            await msg.add_reaction("🇳")
            embed = Embed(ctx, title="Request Sent",
                          description=f"Your waifu rename request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                          color=discord.Color.green())
            embed.add_field(name="Request Message Link", value=msg.jump_url)
            return await ctx.send(embed=embed)
        else:
            async with ctx.typing():
                async with self.log_and_run("""UPDATE WAIFUS SET NAME=? WHERE NAME==?""", [new_waifu_name, old_waifu_name]):
                    pass
                async with self.log_and_run("""SELECT ID FROM BRACKETS""") as cursor:
                    brackets = await cursor.fetchall()
                for bracket, in brackets:
                    async with self.log_and_run("""UPDATE BRACKET_{} SET NAME=? WHERE NAME==?""".format(bracket), [new_waifu_name, old_waifu_name]):
                        pass
                async with self.log_and_run("""UPDATE ALIASES SET NAME=? WHERE NAME==?""", [new_waifu_name, old_waifu_name]):
                    pass
                if not _reaction:
                    embed = Embed(ctx, title="Rename Successful", description="The waifu has been renamed.", color=discord.Color.green())
                    embed.add_field(name="Old Name", value=old_waifu_name)
                    embed.add_field(name="New Name", value=new_waifu_name)
                    return await ctx.send(embed=embed)

    @modify.command(name="description", brief="Change the description of a waifu", usage="waifu_name")
    async def modify_description(self, ctx: discord.ext.commands.Context, *, waifu_name: Union[int, str], _reaction: bool = False):
        await self.get_conn()
        waifu_name = await self.waifu.fully_run_command(ctx, id_or_name=waifu_name, _resolve=True)
        async with self.log_and_run("""SELECT NAME, DESCRIPTION FROM WAIFUS""") as cursor:
            data = {item.casefold(): desc for item, desc in await cursor.fetchall()}
        if waifu_name.casefold() not in data:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="A waifu with this name does not exist.", color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=waifu_name)
            return await ctx.send(embed=embed)
        embed = Embed(ctx, title="Description", description="Type the description of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        description = message.content
        if ctx.author.id != self.bot.owner_id:
            embed = Embed(ctx, title="Waifu Description Change Request", description="New Description: " + description, color=discord.Color.green())
            embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                             icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
            embed.add_field(name="Waifu Name", value=waifu_name)
            old_desc = data[waifu_name.casefold()]
            if len(old_desc) < 1024:
                old_desc = old_desc[:1021] + "..."
            embed.add_field(name="Old Waifu Description", value=old_desc)
            embed.add_field(name="Status", value="Open")
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
            msg = await chan.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🚫")
            await msg.add_reaction("🇩")
            embed = Embed(ctx, title="Request Sent",
                          description=f"Your waifu description request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                          color=discord.Color.green())
            embed.add_field(name="Request Message Link", value=msg.jump_url)
            return await ctx.send(embed=embed)
        else:
            async with self.log_and_run("""UPDATE WAIFUS SET DESCRIPTION=? WHERE NAME==?""", [description, waifu_name]):
                pass
            if not _reaction:
                embed = Embed(ctx, title="Description Updated", description="The description has been updated.")
                embed.add_field(name="Waifu Name", value=waifu_name)
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed.add_field(name="Description", value=description)
                await ctx.send(embed=embed)

    @modify.command(name="anime", brief="Change the anime of a waifu", usage="waifu_name")
    async def modify_anime(self, ctx: discord.ext.commands.Context, *, waifu_name: Union[int, str], _reaction: bool = False):
        await self.get_conn()
        waifu_name = await self.waifu.fully_run_command(ctx, id_or_name=waifu_name, _resolve=True)
        async with self.log_and_run("""SELECT NAME, ANIME FROM WAIFUS""") as cursor:
            data = {item.casefold(): _anime for item, _anime in await cursor.fetchall()}
        if waifu_name.casefold() not in data:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="A waifu with this name does not exist.", color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=waifu_name)
            return await ctx.send(embed=embed)
        old_anime = data[waifu_name.casefold()]
        embed = Embed(ctx, title="Anime", description="Type the anime of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                          timeout=120)
        anime = message.content
        if ctx.author.id != self.bot.owner_id:
            embed = Embed(ctx, title="Waifu Anime Change Request", color=discord.Color.green())
            embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                             icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
            embed.add_field(name="Waifu Name", value=waifu_name)
            if len(old_anime) < 1024:
                old_anime = old_anime[:1021] + "..."
            embed.add_field(name="Old Anime", value=old_anime)
            embed.add_field(name="New Anime", value=anime)
            embed.add_field(name="Status", value="Open")
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
            msg = await chan.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🚫")
            await msg.add_reaction("🇦")
            embed = Embed(ctx, title="Request Sent",
                          description=f"Your waifu anime change request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                          color=discord.Color.green())
            embed.add_field(name="Request Message Link", value=msg.jump_url)
            return await ctx.send(embed=embed)
        else:
            async with self.log_and_run("""UPDATE WAIFUS SET ANIME=? WHERE NAME==?""", [anime, waifu_name]):
                pass
            if not _reaction:
                embed = Embed(ctx, title="Anime Updated", description="The anime has been updated.")
                embed.add_field(name="Waifu Name", value=waifu_name)
                if len(anime) > 1024:
                    anime = anime[:1021] + "..."
                embed.add_field(name="Old Anime", value=old_anime)
                embed.add_field(name="New Anime", value=anime)
                await ctx.send(embed=embed)

    @modify.command(name="image", brief="Change the image of a waifu", usage="waifu_name")
    async def modify_image(self, ctx: discord.ext.commands.Context, *, waifu_name: Union[int, str], _reaction: bool = False):
        await self.get_conn()
        waifu_name = await self.waifu.fully_run_command(ctx, id_or_name=waifu_name, _resolve=True)
        async with self.log_and_run("""SELECT NAME, IMAGE FROM WAIFUS""") as cursor:
            data = {item.casefold(): _image for item, _image in await cursor.fetchall()}
        old_image = data[waifu_name.casefold()]
        if waifu_name.casefold() not in data:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="A waifu with this name does not exist.", color=discord.Color.red())
            embed.add_field(name="Waifu Name", value=waifu_name)
            return await ctx.send(embed=embed)
        embed = Embed(ctx, title="Image", description="Send the image of the waifu you want to add.", color=discord.Color.green())
        await ctx.send(embed=embed)
        message = await self.bot.wait_for("message", check=lambda message: (message.author == ctx.author and message.channel == ctx.channel) and (
                (message.content or "").startswith("http") or message.attachments), timeout=120)
        if message.content:
            image = message.content
        else:
            attachment: discord.Attachment = message.attachments[0]
            file: discord.File = await attachment.to_file()
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_image_channel_id)
            msg = await chan.send(embed=Embed(ctx, title=waifu_name), file=file)
            attachment_2: discord.Attachment = msg.attachments[0]
            image = attachment_2.url
        if ctx.author.id != self.bot.owner_id:
            embed = Embed(ctx, title="Waifu Image Change Request", color=discord.Color.green())
            embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                             icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
            embed.add_field(name="Waifu Name", value=waifu_name)
            if len(old_image) < 1024:
                old_image = old_image[:1021] + "..."
            embed.add_field(name="Old Image", value=old_image)
            embed.add_field(name="New Image", value=image)
            embed.add_field(name="Status", value="Open")
            chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
            msg = await chan.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🚫")
            await msg.add_reaction("🇮")
            embed = Embed(ctx, title="Request Sent",
                          description=f"Your waifu image change request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                          color=discord.Color.green())
            embed.add_field(name="Request Message Link", value=msg.jump_url)
            return await ctx.send(embed=embed)
        else:
            async with self.log_and_run("""UPDATE WAIFUS SET IMAGE=? WHERE NAME==?""", [image, waifu_name]):
                pass
            if not _reaction:
                embed = Embed(ctx, title="Image Updated", description="The image has been updated.")
                embed.add_field(name="Waifu Name", value=waifu_name)
                if len(image) > 1024:
                    image = image[:1021] + "..."
                embed.add_field(name="Old Image Link", value=old_image)
                embed.add_field(name="New Image Link", value=image)
                embed.set_image(url=image)
                await ctx.send(embed=embed)

    async def not_bracket_owner(self, ctx: discord.ext.commands.Context, bracket_id: int):
        async with self.log_and_run("""SELECT OWNER_ID FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            owner_id, = await cursor.fetchone()
        if owner_id != ctx.author.id:
            embed = Embed(ctx, title="Do Not Own Bracket", description="You do not own this bracket and therefore cannot modify it.",
                          color=discord.Color.red())
            embed.add_field(name="Owner", value=self.bot.get_user(ctx.guild, owner_id).mention)
            await ctx.send(embed=embed)
            raise StopCommand

    @waifu_war.command(brief="Add a waifu to a bracket", usage="bracket_id name",
                       aliases=["addtobracket", "atb", "add_waifu_bracket", "awb", "addwaifubracket"])
    async def add_to_bracket(self, ctx: discord.ext.commands.Context, bracket_id: int, *, name: Union[int, str]):
        await self.get_conn()
        name = await self.waifu.fully_run_command(ctx, id_or_name=name, _resolve=True)
        async with self.log_and_run("""SELECT GUILD_ID, STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            logger.debug("Data: %s", data)
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            (guild_id, status), = data
            if status != Status.OPEN:
                embed = Embed(ctx, title="Bracket Not Open",
                              description="The given Bracket is not open. A Bracket has to be Open in order to add characters to it.",
                              color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
                return await ctx.send(embed=embed)
            if guild_id != getattr(ctx.guild, "id", None):
                embed = Embed(ctx, title="Bracket Not In Guild",
                              description="The given Bracket is not from this Guild, and cannot be modified from this Guild.",
                              color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
                return await ctx.send(embed=embed)
            await self.not_bracket_owner(ctx, bracket_id)
        async with self.log_and_run("""INSERT INTO BRACKET_{0}(NAME) VALUES (?)""".format(bracket_id), [name]) as cursor:
            await cursor.execute("""SELECT ID FROM BRACKET_{0} WHERE ID = (SELECT MAX(ID) FROM BRACKET_{0})""".format(bracket_id))
            data = await cursor.fetchone()
            item_id = data[0]
        await self.waifu(ctx, bracket_id, id_or_name=item_id)

    @waifu_war.command(brief="Pick a random number of waifus to add to a bracket.", usage="bracket_id number")
    async def random_waifus(self, ctx: discord.ext.commands.Context, bracket_id: int, count: int):
        async with self.log_and_run("""SELECT GUILD_ID, STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            logger.debug("Data: %s", data)
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            (guild_id, status), = data
            if status != Status.OPEN:
                embed = Embed(ctx, title="Bracket Not Open",
                              description="The given Bracket is not open. A Bracket has to be Open in order to add characters to it.",
                              color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
                return await ctx.send(embed=embed)
            if guild_id != getattr(ctx.guild, "id", None):
                embed = Embed(ctx, title="Bracket Not In Guild",
                              description="The given Bracket is not from this Guild, and cannot be modified from this Guild.",
                              color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                embed.add_field(name="Status", value=Status(status).name.split(".")[-1].title())
                return await ctx.send(embed=embed)
            await self.not_bracket_owner(ctx, bracket_id)
        async with self.log_and_run("""SELECT NAME FROM BRACKET_{0}""".format(bracket_id)) as cursor:
            existing_names = [name async for name, in cursor]
        async with self.log_and_run("""SELECT NAME FROM WAIFUS""") as cursor:
            names = [name async for name, in cursor]
        names_to_use = list(set(names) - set(existing_names))
        if len(names_to_use) < count:
            embed = Embed(ctx, title="Too Many Waifus", description="There are less waifus to add then the amount which you requested.",
                          color=discord.Color.red())
            embed.add_field(name="Requested", value=str(count))
            embed.add_field(name="Available", value=str(len(names_to_use)))
            return await ctx.send(embed=embed)
        else:
            random.shuffle(names_to_use)
            to_use = names_to_use[:count]
            async with self.log_and_run("""INSERT INTO BRACKET_{0}(NAME) VALUES (?)""".format(bracket_id), [(name,) for name in to_use],
                                        method="executemany"):
                pass
            embed = Embed(ctx, title="Added Waifus", description=f"**{count}** waifus have been added.", color=discord.Color.green())
            fields = [("Names", "\n".join(name for name in to_use))]
            await send_embeds_fields(ctx, embed, fields)
            return await self.bracket.fully_run_command(ctx, bracket_id)

    @waifu_war.command(brief="Lock a bracket", usage="bracket_id", aliases=["lockbracket", "lb"], enabled=True)
    async def lock_bracket(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.needs_bracket(ctx, bracket_id)
        async with self.log_and_run("""SELECT STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            await self.not_bracket_owner(ctx, bracket_id)
            async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status.LOCKED, bracket_id]):
                pass
            embed = Embed(ctx, title="Locked Bracket", description="Bracket has been locked.", color=discord.Color.green())
            embed.add_field(name="Bracket ID", value=str(bracket_id))
            await ctx.send(embed=embed)

    @waifu_war.command(brief="Unlock a bracket", usage="bracket_id [to_status]", aliases=["unlockbracket", "ulb"], enabled=True)
    async def unlock_bracket(self, ctx: discord.ext.commands.Context, bracket_id: int, to_status: int = 1):
        await self.get_conn()
        try:
            Status(to_status)
        except ValueError:
            embed = Embed(ctx, title="Invalid Status", description="The provided status number is invalid.", color=discord.Color.red())
            embed.add_field(name="Status Number", value=str(to_status))
            await ctx.send(embed=embed)
            return await ctx.send_help(self.unlock_bracket)
        async with self.log_and_run("""SELECT STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            await self.not_bracket_owner(ctx, bracket_id)
            existing_status = Status(data[0][0])
            if existing_status != Status.LOCKED:
                embed = Embed(ctx, title="Not Locked", description="The given bracket ID is not locked.", color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                return await ctx.send(embed=embed)
            async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status(to_status), bracket_id]):
                pass
            embed = Embed(ctx, title="Unlocked Bracket", description="Bracket has been locked.", color=discord.Color.green())
            embed.add_field(name="Bracket ID", value=str(bracket_id))
            await ctx.send(embed=embed)

    @waifu_war.command(brief="Close a bracket", usage="bracket_id", aliases=["closebracket"])
    async def close_bracket(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.needs_bracket(ctx, bracket_id)
        async with self.log_and_run("""SELECT STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            await self.not_bracket_owner(ctx, bracket_id)
            async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status.CLOSED, bracket_id]):
                pass
            embed = Embed(ctx, title="Closed Bracket", description="Bracket has been closed.", color=discord.Color.green())
            embed.add_field(name="Bracket ID", value=str(bracket_id))
            await ctx.send(embed=embed)

    @waifu_war.command(brief="Delete a waifu", usage="bracket_id waifu_id_or_name", aliases=["deletewaifu", "dw"])
    async def delete_waifu(self, ctx: discord.ext.commands.Context, bracket_id: int, waifu: Union[int, str]):
        await self.get_conn()
        waifu_id = await self.waifu.fully_run_command(ctx, bracket_id=bracket_id, id_or_name=waifu, _resolve=True, _id=True)
        async with self.log_and_run("""SELECT STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            if data[0][0] != Status.OPEN:
                raise
            await self.not_bracket_owner(ctx, bracket_id)
            async with self.log_and_run("""SELECT * FROM BRACKET_%s WHERE ID==?""" % bracket_id, [waifu_id]) as cursor:
                data = await cursor.fetchall()
            if len(data) != 1:
                embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist for the bracket.",
                              color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                embed.add_field(name="Waifu ID", value=str(waifu_id))
                await ctx.send(embed=embed)
            else:
                async with self.log_and_run("""DELETE FROM BRACKET_%s WHERE ID==?""" % bracket_id, [waifu_id]):
                    pass
                embed = Embed(ctx, title="Deleted Waifu", description="Waifu has been deleted.", color=discord.Color.green())
                embed.add_field(name="Bracket ID", value=str(bracket_id))
                embed.add_field(name="Waifu ID", value=str(waifu_id))
                await ctx.send(embed=embed)

    @waifu_war.command(brief="Duplicate a bracket", usage="bracket_id [name]", aliases=["dup"])
    async def duplicate(self, ctx: discord.ext.commands.Context, /, bracket_id: Optional[int] = None, *, name: Optional[str] = None):
        await self.get_conn()
        bracket_id = bracket_id or await self.get_voting(getattr(ctx.guild, "id", None))
        await self.needs_bracket(ctx, bracket_id)
        async with self.log_and_run("""SELECT NAME FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            original_name = data[0][0]
            name = name or original_name
            new_bracket_id = await self.create_bracket.fully_run_command(ctx, name=name)
            async with self.log_and_run("""INSERT INTO BRACKET_{} SELECT * FROM BRACKET_{}""".format(new_bracket_id, bracket_id)):
                pass
            embed = Embed(ctx, title="Bracket Duplicated", description="The Bracket has been successfully duplicated!", color=discord.Color.green())
            embed.add_field(name="Original Bracket ID", value=str(bracket_id))
            embed.add_field(name="Original Name", value=original_name)
            embed.add_field(name="New Bracket ID", value=str(new_bracket_id))
            embed.add_field(name="New Name", value=name)
            await ctx.send(embed=embed)

    @waifu_war.command(brief="Add an alias to the Waifu system.", usage="character_name character_alias [character_alias] [...]",
                       aliases=["addalias", "aa"])
    async def add_alias(self, ctx: discord.ext.commands.Context, character_name: str, *aliases: str, _reaction: bool = False):
        await self.get_conn()
        if len(aliases) < 1:
            self.bot.missing_argument("alias")
        async with self.log_and_run("""SELECT ALIAS FROM ALIASES""") as cursor:
            existing = [alias.lower() async for alias, in cursor]
        for alias in aliases:
            if alias.lower() in existing:
                embed = Embed(ctx, title="Alias Already Exists", description="The alias you provided already exists or has already been requested.",
                              color=discord.Color.red())
                embed.add_field(name="Name", value=character_name)
                embed.add_field(name="Alias", value=alias)
                await ctx.send(embed=embed)
                continue
            if ctx.author.id != self.bot.owner_id:
                embed = Embed(ctx, title="Possible Alias", description="An alias has been requested to be added.")
                embed.set_author(name=embed.author.name + " • User ID: " + str(ctx.author.id), url=getattr(embed.author, "url", discord.Embed.Empty),
                                 icon_url=getattr(embed.author, "icon_url", discord.Embed.Empty))
                embed.add_field(name="Waifu Name", value=character_name)
                embed.add_field(name="Alias", value=alias)
                embed.add_field(name="Status", value="Open")
                chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_approval_channel_id)
                msg = await chan.send(embed=embed)
                await msg.add_reaction("✅")
                await msg.add_reaction("🚫")
                await msg.add_reaction("🇦")
                await msg.add_reaction("🇳")
                embed = Embed(ctx, title="Request Sent",
                              description=f"Your alias request has been sent to {self.bot.get_user(self.bot.owner_id).mention}.",
                              color=discord.Color.green())
                embed.add_field(name="Request Message Link", value=msg.jump_url)
                await ctx.send(embed=embed)
                existing.append(alias)
                continue
            try:
                async with self.log_and_run("""INSERT INTO ALIASES(NAME, ALIAS) VALUES (?, ?)""", [character_name, alias]):
                    pass
            except sqlite3.IntegrityError:
                embed = Embed(ctx, title="Alias Already Exists", description="The given alias already exists.", color=discord.Color.red())
                async with self.log_and_run("""SELECT NAME FROM ALIASES WHERE ALIAS = ?""", [alias]) as cursor:
                    data = await cursor.fetchone()
                name = data[0]
                embed.add_field(name="Name", value=name)
                embed.add_field(name="Alias", value=alias)
                await ctx.send(embed=embed)
            else:
                if _reaction:
                    continue
                embed = Embed(ctx, title="Alias Added", description="The alias was successfully added.", color=discord.Color.green())
                embed.add_field(name="Name", value=character_name)
                embed.add_field(name="Alias", value=alias)
                await ctx.send(embed=embed)

    @staticmethod
    def get_power_of_two(x: int):
        count = 0
        while x > 2:
            x /= 2
            count += 1
        return count, count + 1

    @waifu_war.command(brief="Start voting on a bracket", usage="bracket_id", aliases=["sv", "startvote"])
    async def start_vote(self, ctx: discord.ext.commands.Context, bracket_id: int):
        await self.get_conn()
        async with self.log_and_run("""SELECT STATUS FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
            data = await cursor.fetchall()
        if len(data) != 1:
            return await self.id_does_not_exist(ctx, bracket_id)
        else:
            val = await self.get_voting(getattr(ctx.guild, "id", None))
            if val is not None:
                embed = Embed(ctx, title="Another Bracket Already In Voting",
                              description="Another bracket is already going through a vote. Wait for that bracket to finish.",
                              color=discord.Color.red())
                embed.add_field(name="Other Waifu Bracket", value=str(val))
                embed.add_field(name="Specified Waifu Bracket", value=str(bracket_id))
                return await ctx.send(embed=embed)
            await self.not_bracket_owner(ctx, bracket_id)
            status = data[0][0]
            if status != Status.OPEN:
                embed = Embed(ctx, title="Cannot Start Voting on Non-Open Bracket",
                              description="A bracket must be open to start voting on it. Use `{}waifu_war duplicate {} name` to obtain a new "
                                          "bracket.".format(self.bot.command_prefix, bracket_id), color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                return await ctx.send(embed=embed)
            else:
                async with self.log_and_run("""SELECT NAME FROM BRACKET_{0}""".format(bracket_id)) as cursor:
                    data = await cursor.fetchall()
                x = len(data)
                if (x & (x - 1)) != 0:
                    bound_low, bound_high = self.get_power_of_two(x)
                    embed = Embed(ctx, title="Not a Power of Two",
                                  description="A bracket must be a power of two before starting voting. Add or delete enough waifus to get the "
                                              "minimum or maximum you need to start.")
                    fields = [("Number of Waifus", str(x)), ("Minimum", str(2 ** bound_low)), ("Maximum", str(2 ** bound_high))]
                    return await send_embeds_fields(ctx, embed, fields)
                else:
                    choices = [name for name, in data]
                    random.shuffle(choices)
                    new_choices = [[name] for name in choices]
                    async with self.log_and_run("""DROP TABLE BRACKET_{0}""".format(bracket_id)):
                        pass
                    async with self.log_and_run(
                            """CREATE TABLE IF NOT EXISTS BRACKET_%s(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL UNIQUE)""" %
                            bracket_id):
                        pass
                    async with self.conn.executemany("""INSERT INTO BRACKET_{0}(NAME) VALUES(?)""".format(bracket_id), new_choices):
                        pass
                    async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status.VOTABLE, bracket_id]):
                        pass
                    embed = Embed(ctx, title="Vote Started", description="Voting has now started", color=discord.Color.green())
                    embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                    await ctx.send(embed=embed)
                    await self.bracket(ctx)

    @waifu_war.command(brief="Vote on a division", usage="waifu_id", alias=["v"], significant=True)
    async def vote(self, ctx: discord.ext.commands.Context, *, id_or_name: Union[int, str]):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            async with self.conn.execute("""SELECT GUILD_ID FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
                data = await cursor.fetchone()
            if data is None or data[0] != getattr(ctx.guild, "id", None):
                embed = Embed(ctx, title="Can Only Vote on Brackets in the Guild",
                              description="This bracket was not made in the current Guild. To ensure that brackets are fair, you cannot vote on "
                                          "this bracket from any guild except where it was created.",
                              color=discord.Color.red())
                embed.add_field(name="Bracket ID", value=bracket_id)
                embed.add_field(name="Current Guild ID", value=str(getattr(ctx.guild, "id", None)))
                embed.add_field(name="Bracket Guild ID", value=str(data[0]))
                return await ctx.send(embed=embed)
        if isinstance(id_or_name, str):
            query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                    "WAIFUS.NAME WHERE WAIFUS.NAME LIKE '%'||?||'%'".format(bracket_id)
        else:
            query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                    "WAIFUS.NAME WHERE BRACKET_{0}.ID==?".format(bracket_id)
        try:
            async with self.log_and_run(query, [id_or_name]) as cursor:
                data = await cursor.fetchall()
        except sqlite3.OperationalError:
            logger.warning("", exc_info=True)
            return await self.id_does_not_exist(ctx, bracket_id)
        if isinstance(id_or_name, str):
            async with self.log_and_run(
                    """SELECT BRACKET_{0}.ID, ALIASES.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN ALIASES on BRACKET_{0}.NAME = 
                    ALIASES.NAME INNER JOIN WAIFUS ON BRACKET_{0}.NAME = WAIFUS.NAME WHERE ALIAS LIKE '%'||?||'%'""".format(bracket_id),
                    [id_or_name]) as cursor:
                data2 = await cursor.fetchall()
            data.extend(data2)
        seen = []
        for item in data.copy():
            waifu_id, name, description, anime, image_link = item
            if waifu_id in seen:
                data.remove(item)
            else:
                seen.append(waifu_id)
        if len(data) < 1:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist for the bracket.",
                          color=discord.Color.red())
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            if isinstance(id_or_name, str):
                embed.add_field(name="Waifu Name", value=id_or_name)
            else:
                embed.add_field(name="Bracket Waifu ID", value=str(id_or_name))
            return await ctx.send(embed=embed)
        elif len(data) > 1:
            ids = [f"**{waifu_id}**: [{name} (*{anime}*)]({image_link})" for waifu_id, name, description, anime, image_link in data]
            embed = Embed(ctx, title="Duplicate Named Waifus",
                          description="There are multiple waifus with the same name. Use an ID instead of a name to vote. The "
                                      "bracket waifu IDs that share the same name have been provided.")
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            await send_embeds_fields(ctx, embed, [("IDs", "\n".join(str(id) for id in ids))])
        else:
            waifu_id, name, description, anime, image_link = data[0]
            division = (waifu_id + 1) // 2
            try:
                async with self.log_and_run("""INSERT INTO VOTES(USER_ID, BRACKET, DIVISION, CHOICE) VALUES(?, ?, ?, ?)""",
                                            [ctx.author.id, bracket_id, division, bool(waifu_id % 2)]):
                    pass
            except sqlite3.IntegrityError:
                logger.warning("", exc_info=True)
                async with self.log_and_run("""SELECT CHOICE FROM VOTES WHERE USER_ID==? AND BRACKET==? AND DIVISION==?""",
                                            [ctx.author.id, bracket_id, division]) as cursor:
                    previous_choice = division * 2 - int((await cursor.fetchone())[0])
                embed = Embed(ctx, title="Already Voted", description="You have already voted for this division. Specify another waifu ID.",
                              color=discord.Color.red())
                fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division)), ("Intended Waifu ID", str(waifu_id)),
                          ("Existing Choice", str(previous_choice))]
                messages = await send_embeds_fields(ctx, embed, fields)
                msg = messages[0]
                await msg.add_reaction("🚫")
            else:
                embed = Embed(ctx, title="Voted", description="You have successfully voted in the waifu war!", color=discord.Color.green())
                fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division)), ("Waifu ID", str(waifu_id)), ("Waifu Name", name),
                          ("Waifu Anime", anime), ("Waifu Description", description)]
                embed.set_image(url=image_link)
                messages = await send_embeds_fields(ctx, embed, fields)
                msg = messages[0]
                await msg.add_reaction("✅")
                await msg.add_reaction("🚫")
                if self.guide_data.get(ctx.author.id, 0) == 2:
                    await self.guide_step_3(ctx)

    @waifu_war.command(brief="Undo your vote", usage="waifu_id_or_name",
                       alias=["uv", "undo_vote", "undovote", "undo", "revert", "revert_vote", "rv", "revertvote", "unvote"], significant=True)
    async def un_vote(self, ctx: discord.ext.commands.Context, *, id_or_name: Union[int, str]):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        if isinstance(id_or_name, str):
            query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                    "WAIFUS.NAME WHERE WAIFUS.NAME LIKE '%'||?||'%'".format(bracket_id)
        else:
            query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                    "WAIFUS.NAME WHERE BRACKET_{0}.ID==?".format(bracket_id)
        try:
            async with self.log_and_run(query, [id_or_name]) as cursor:
                data = await cursor.fetchall()
        except sqlite3.OperationalError:
            logger.warning("", exc_info=True)
            return await self.id_does_not_exist(ctx, bracket_id)
        if isinstance(id_or_name, str):
            async with self.log_and_run(
                    """SELECT BRACKET_{0}.ID, ALIASES.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN ALIASES on BRACKET_{0}.NAME = 
                    ALIASES.NAME INNER JOIN WAIFUS ON BRACKET_{0}.NAME = WAIFUS.NAME WHERE ALIAS LIKE '%'||?||'%'""".format(bracket_id),
                    [id_or_name]) as cursor:
                data2 = await cursor.fetchall()
            data.extend(data2)
        seen = []
        for item in data.copy():
            waifu_id, name, description, anime, image_link = item
            if waifu_id in seen:
                data.remove(item)
            else:
                seen.append(waifu_id)
        if len(data) < 1:
            embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist for the bracket.",
                          color=discord.Color.red())
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            if isinstance(id_or_name, str):
                embed.add_field(name="Waifu Name", value=id_or_name)
            else:
                embed.add_field(name="Bracket Waifu ID", value=str(id_or_name))
            return await ctx.send(embed=embed)
        elif len(data) > 1:
            ids = [f"**{waifu_id}**: [{name} (*{anime}*)]({image_link})" for waifu_id, name, description, anime, image_link in data]
            embed = Embed(ctx, title="Duplicate Named Waifus",
                          description="There are multiple waifus with the same name. Use an ID instead of a name to unvote. The "
                                      "bracket waifu IDs that share the same name have been provided.")
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            await send_embeds_fields(ctx, embed, [("IDs", "\n".join(str(id) for id in ids))])
        else:
            waifu_id, name, description, anime, image_link = data[0]
            division = (waifu_id + 1) // 2
            async with self.log_and_run("""DELETE FROM VOTES WHERE USER_ID==? AND BRACKET==? AND DIVISION==? AND CHOICE==?""",
                                        [ctx.author.id, bracket_id, division, bool(waifu_id % 2)]):
                pass
            embed = Embed(ctx, title="Vote Removed", description="Your vote has been removed.", color=discord.Color.green())
            fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division)), ("Waifu ID", str(waifu_id)), ("Waifu Name", name)]
            messages = await send_embeds_fields(ctx, embed, fields)
            msg = messages[0]
            await msg.add_reaction("✅")
            if self.guide_data.get(ctx.author.id, 0) == 3:
                await self.guide_step_4(ctx)

    @waifu_war.command(brief="Get the votes of a user or the users that voted on a waifu", usage="user / waifu_id_or_name", aliases=["gv", "getvote"])
    async def get_vote(self, ctx: discord.ext.commands.Context, *, id_or_name: Union[discord.Member, int, str]):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        if isinstance(id_or_name, discord.Member):
            async with self.log_and_run(
                    """SELECT DIVISION, BRACKET_{0}.ID, WAIFUS.NAME, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = 
                    WAIFUS.NAME INNER JOIN (SELECT * FROM VOTES WHERE USER_ID==? AND BRACKET==?) ON BRACKET_{0}.ID = ((DIVISION * 2)- 
                    CHOICE)""".format(
                        bracket_id), [id_or_name.id, bracket_id]) as cursor:
                data = await cursor.fetchall()
            embed = Embed(ctx, title="User Votes")
            embed.add_field(name="User", value=id_or_name.mention)
            embed.add_field(name="Waifu Bracket", value=str(bracket_id))
            lines = []
            for divison, waifu_id, name, anime, image in data:
                lines.append(f"Division **{divison}** / Waifu ID **{waifu_id}**: [{name} (*{anime}*)]({image})")
            await send_embeds_fields(ctx, embed, [("Waifus", "\n".join(lines) or "None")])
        else:
            if isinstance(id_or_name, str):
                query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                        "WAIFUS.NAME WHERE WAIFUS.NAME LIKE '%'||?||'%'".format(bracket_id)
            else:
                query = "SELECT BRACKET_{0}.ID, WAIFUS.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN WAIFUS ON BRACKET_{0}.NAME = " \
                        "WAIFUS.NAME WHERE BRACKET_{0}.ID==?".format(bracket_id)
            try:
                async with self.log_and_run(query, [id_or_name]) as cursor:
                    data = await cursor.fetchall()
            except sqlite3.OperationalError:
                logger.warning("", exc_info=True)
                return await self.id_does_not_exist(ctx, bracket_id)
            if isinstance(id_or_name, str):
                async with self.log_and_run(
                        """SELECT BRACKET_{0}.ID, ALIASES.NAME, DESCRIPTION, ANIME, IMAGE FROM BRACKET_{0} INNER JOIN ALIASES on BRACKET_{0}.NAME = 
                        ALIASES.NAME INNER JOIN WAIFUS ON BRACKET_{0}.NAME = WAIFUS.NAME WHERE ALIAS LIKE '%'||?||'%'""".format(bracket_id),
                        [id_or_name]) as cursor:
                    data2 = await cursor.fetchall()
                data.extend(data2)
            seen = []
            for item in data.copy():
                waifu_id, name, description, anime, image_link = item
                if waifu_id in seen:
                    data.remove(item)
                else:
                    seen.append(waifu_id)
            if len(data) < 1:
                embed = Embed(ctx, title="Waifu Does Not Exist", description="The provided waifu does not exist for the bracket.",
                              color=discord.Color.red())
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                if isinstance(id_or_name, str):
                    embed.add_field(name="Waifu Name", value=id_or_name)
                else:
                    embed.add_field(name="Bracket Waifu ID", value=str(id_or_name))
                return await ctx.send(embed=embed)
            elif len(data) > 1:
                ids = [f"**{waifu_id}**: [{name} (*{anime}*)]({image_link})" for waifu_id, name, description, anime, image_link in data]
                embed = Embed(ctx, title="Duplicate Named Waifus",
                              description="There are multiple waifus with the same name. Use an ID instead of a name to view votes. The "
                                          "bracket waifu IDs that share the same name have been provided.")
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                await send_embeds_fields(ctx, embed, [("IDs", "\n".join(str(id) for id in ids))])
            else:
                waifu_id, name, description, anime, image_link = data[0]
                division = (waifu_id + 1) // 2
                choice = waifu_id % 2
                async with self.log_and_run("""SELECT USER_ID FROM VOTES WHERE BRACKET==? AND DIVISION==? AND CHOICE==?""",
                                            [bracket_id, division, choice]) as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title="Votes", description="These are the people who voted for a specific character.")
                fields = [("Waifu Bracket", str(bracket_id)), ("Bracket Division", str(division)), ("Waifu ID", str(waifu_id)), ("Waifu Name", name),
                          ("Voters", "\n".join(self.bot.get_user(user_id).mention for user_id, in data) or "None")]
                return await send_embeds_fields(ctx, embed, fields)

    @waifu_war.command(brief="Get the last division you voted for.", aliases=["lastdivision", "ld"], significant=True)
    async def last_division(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            async with self.log_and_run("""SELECT MAX(DIVISION) FROM VOTES WHERE USER_ID==?""", [ctx.author.id]) as cursor:
                data = (await cursor.fetchone())[0]
            if data is None:
                msg = await ctx.send(embed=Embed(ctx, title="Never Participated",
                                                 description="You have never participated in the waifu war. Click the emoji below to get started on "
                                                             "the guide.",
                                                 color=discord.Color.red()))
                await msg.add_reaction("✅")
            else:
                embed = Embed(ctx, title="Previous Division")
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                embed.add_field(name="Waifu Division", value=str(data))
                msg = await ctx.send(embed=embed)
                await msg.add_reaction("✅")

    @waifu_war.command(brief="Start the next bracket", usage="[additional]", aliases=["start_next", "startnext", "sn", "finishbracket", "fb"])
    async def finish_bracket(self, ctx: discord.ext.commands.Context, *, additional: str = None):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            await self.not_bracket_owner(ctx, bracket_id)
            async with self.log_and_run("""SELECT MAX(ID) FROM BRACKET_{0}""".format(bracket_id)) as cursor:
                data = (await cursor.fetchone())[0]
            max_division = data // 2
            async with self.log_and_run("""SELECT NAME FROM BRACKETS WHERE ID==?""", [bracket_id]) as cursor:
                name = (await cursor.fetchone())[0]
            name = name.partition("(")[0].strip()
            if max_division == 1:
                channel = self.bot.get_channel_data(ctx.guild, "announcements") or ctx
                l_name, l_anime, l_description, l_image_link, l_votes, r_name, r_anime, r_description, r_image_link, r_votes = await self.division(
                    ctx, 1, _send=False)
                embed = Embed(ctx, title=f"Winner for *{name}*")
                if l_votes > r_votes:
                    name, anime, description, image_link, votes = l_name, l_anime, l_description, l_image_link, l_votes
                    embed.add_field(name="Status", value="Clear Winner")
                elif l_votes > r_votes:
                    name, anime, description, image_link, votes = r_name, r_anime, r_description, r_image_link, r_votes
                    embed.add_field(name="Status", value="Clear Winner")
                elif l_votes == r_votes:  # We use random number generation.
                    waifu_id = 2 - random.randint(0, 1)
                    embed.add_field(name="Status", value="Tie")
                    embed.description = "The two winning sides have the same amount of votes. A random number generation sequence has been used to " \
                                        "determine the winner."
                    if waifu_id % 2 == 0:  # Right
                        name, anime, description, image_link, votes = l_name, l_anime, l_description, l_image_link, l_votes
                    else:
                        name, anime, description, image_link, votes = r_name, r_anime, r_description, r_image_link, r_votes
                else:
                    raise ValueError("Values do not make sense", l_name, l_votes, r_name, r_votes)
                fields = [("Waifu Name", name), ("Waifu Anime", anime), ("Waifu Description", description), ("Votes", votes)]
                embed.set_image(url=image_link)
                await send_embeds_fields(channel, embed, fields)
            else:
                if additional is None:
                    self.bot.missing_argument("additional")
                new_bracket_id = int(await self.create_bracket.fully_run_command(ctx, name=name + f" ({additional})"))
                for i in range(1, max_division + 1):
                    l_name, l_votes, r_name, r_votes = await self.division(ctx, bracket_id, i)
                    if l_votes > r_votes:
                        waifu_id = (i * 2) - 1
                        await self.waifu(ctx, bracket_id=bracket_id, id_or_name=waifu_id)
                        winner = l_name
                    elif l_votes < r_votes:
                        waifu_id = (i * 2)
                        await self.waifu(ctx, bracket_id=bracket_id, id_or_name=waifu_id)
                        winner = r_name
                    elif l_votes == r_votes:  # We use random number generation.
                        waifu_id = (i * 2) - (random.randint(0, 1))
                        await ctx.send(embed=Embed(ctx, title="Tie",
                                                   description=f"The waifus **{l_name}** and **{r_name}** are tired, so a random number was used to "
                                                               f"determine the winner."))
                        await self.waifu(ctx, bracket_id=bracket_id, id_or_name=waifu_id)
                        if waifu_id % 2 == 0:  # Right
                            winner = r_name
                        else:
                            winner = l_name
                    else:
                        raise ValueError("Values do not make sense", l_name, l_votes, r_name, r_votes)
                    async with self.log_and_run("""INSERT INTO BRACKET_{0}(NAME) VALUES (?)""".format(new_bracket_id), [winner]):
                        pass
                embed = Embed(ctx, title="Finalizing", description="The brackets are being finalized.", color=discord.Color.green())
                embed.add_field(name="Old Bracket ID", value=str(bracket_id))
                embed.add_field(name="New Bracket ID", value=str(new_bracket_id))
                await ctx.send(embed=embed)
                async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status.VOTABLE, new_bracket_id]):
                    pass
            async with self.log_and_run("""UPDATE BRACKETS SET STATUS=? WHERE ID==?""", [Status.CLOSED, bracket_id]):
                pass

    @waifu_war.command(brief="Start the guide that shows how to use the bot.", aliases=["start", "g", "s"])
    async def guide(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            embed = Embed(ctx, title="Guide",
                          description="Welcome to the interactive Waifu War guide. This will show you how the various reactions work, "
                                      "allowing you to use the Waifu War system to it's fullest potential. Click the check mark below to start.")
            embed.add_field(name="Note",
                            value="If you have previously used the Waifu War system, the guide *will* delete the entry for the first division.")
            msg = await ctx.send(embed=embed)
            await msg.add_reaction("✅")

    @waifu_war.command(brief="See which divisions a person did not vote for.", usage="user", aliases=["misseddivisions", "md"], significant=True)
    async def missed_division(self, ctx: discord.ext.commands.Context, user: discord.Member = None):
        if user is None:
            user = ctx.author
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            async with self.log_and_run("""SELECT MAX(ID) FROM BRACKET_{0}""".format(bracket_id)) as cursor:
                data = (await cursor.fetchone())[0]
            max_division = data // 2
            async with self.log_and_run("""SELECT DIVISION FROM VOTES WHERE USER_ID==? AND BRACKET==?""", [user.id, bracket_id]) as cursor:
                data = await cursor.fetchall()
            missed = set(range(1, max_division + 1)) - {division for division, in data}
            if len(missed) > 0:
                async with self.log_and_run(
                        """SELECT A.ID,A.NAME, C.ANIME,C.DESCRIPTION,C.IMAGE,B.ID,B.NAME,D.ANIME, D.DESCRIPTION,D.IMAGE FROM (SELECT A.ID, 
                        A.NAME FROM BRACKET_{0} A WHERE A.ID % 2 == 1) AS A JOIN (SELECT B.ID, B.NAME FROM BRACKET_{0} B WHERE B.ID % 2 == 0) AS B 
                        ON (CAST((A.ID - 1) / 2 AS INTEGER) == CAST((B.ID - 1) / 2 AS INTEGER)) JOIN WAIFUS C ON A.NAME == C.NAME JOIN WAIFUS D ON 
                        B.NAME == D.NAME WHERE ((CAST((B.ID + 1) / 2 AS INTEGER)) IN {1})""".format(bracket_id,
                                                                                                    str(ConformingIterator(missed))).replace(",)",
                                                                                                                                             ")")) \
                        as cursor:
                    data = await cursor.fetchall()
                embed = Embed(ctx, title="Missed Divisions", description="The given user has not voted in all divisions.", color=discord.Color.red())
                embed.add_field(name="User", value=user.mention)
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                lines = []
                for division, item in zip(sorted(missed), data):
                    l_id, l_name, l_anime, l_description, l_image_link, r_id, r_name, r_anime, r_description, r_image_link = item
                    lines.append(
                        f"Division **{division}**: [{l_name} (*{l_anime}*) (Waifu ID **{l_id}**)]({l_image_link}) ***v.*** [{r_name} (*{r_anime}*) "
                        f"(Waifu ID **{r_id}**)]({r_image_link})")
                await send_embeds_fields(ctx, embed, [("Divisions", "\n".join(lines) or "None")])
            else:
                embed = Embed(ctx, title="No Missed Divisions", description="The given user has voted in all divisions.", color=discord.Color.green())
                embed.add_field(name="User", value=user.mention)
                embed.add_field(name="Waifu Bracket", value=str(bracket_id))
                await ctx.send(embed=embed)

    @waifu_war.command(brief="Get a convenient Embed that lets people start voting.", not_channel_locked=True)
    async def embed(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        chan = self.bot.get_channel_data(getattr(ctx.guild, "id", None), "bot-spam")
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        if bracket_id is None:
            return await ctx.send(embed=Embed(ctx, title="No Voting Bracket Yet",
                                              description="No brackets are marked as Votable. Wait for a bracket to be marked as votable.",
                                              color=discord.Color.red()))
        else:
            msg = await ctx.send(embed=Embed(ctx, title="Start Voting",
                                             description=f"In order to vote, type `%ww d 1` in the {chan.mention} channel. Or, click the check mark "
                                                         f"below this item, and then go to {chan.mention}."))
            await msg.add_reaction("✅")

    @waifu_war.command(brief="See all waifus in the global list of waifus.",
                       aliases=["ws", "all_waifu", "all_waifus", "aws", "allwaifu", "allwaifus", "globalwaifus", "gws", "g_ws", "global_waifu",
                                "globalwaifu"])
    async def global_waifus(self, ctx: discord.ext.commands.Context):
        embed = Embed(ctx, title="Global Waifu List")
        async with self.log_and_run("""SELECT ID, NAME, ANIME, IMAGE FROM WAIFUS""") as cursor:
            data = await cursor.fetchall()
        lines = []
        for waifu_id, name, anime, image in data:
            lines.append(f"**{waifu_id}**: [{name} (*{anime}*)]({image})")
        await send_embeds_fields(ctx, embed, [("Waifus", "\n".join(lines) or "None")])

    @waifu_war.command(brief="See all animes in the global list of waifus.", aliases=["globalanimes", "gas", "g_as"])
    async def global_animes(self, ctx: discord.ext.commands.Context):
        embed = Embed(ctx, title="Global Animes")
        async with self.log_and_run("SELECT ANIME FROM WAIFUS") as cursor:
            data = await cursor.fetchall()
        lines = []
        for anime in sorted({item for item, in data}):
            lines.append(f"*{anime}*")
        await send_embeds_fields(ctx, embed, [("Animes", "\n".join(lines) or "None")])

    async def guide_step_1(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        bracket_id = await self.get_voting(getattr(ctx.guild, "id", None))
        async with self.log_and_run("""DELETE FROM VOTES WHERE USER_ID==? AND BRACKET==? AND DIVISION==1""", [ctx.author.id, bracket_id]):
            pass
        self.guide_data[ctx.author.id] = 1
        embed = Embed(ctx, title="Step 1: Summoning a Division",
                      description="To get the information for a division, you need to type `%ww d <number>` in order to access information. To "
                                  "bring up the first division, try typing `%ww d 1`.")
        embed.add_field(name="Note", value="For the purposes of the guide, clicking the check mark below will do the same thing as typing `%ww d 1`.")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")

    async def guide_step_2(self, ctx: discord.ext.commands.Context):
        await self.get_conn()
        self.guide_data[ctx.author.id] = 2
        embed = Embed(ctx, title="Step 2: Using a Division",
                      description="The division data will contain 5 emojis. Read how each emoji works. Note that you can click a button more than "
                                  "once, and have the same action repeat. When you're done reading, please vote on a waifu to continue. If you "
                                  "would rather not vote in this division, use the *skip* button (mentioned at the bottom) and find a division "
                                  "where you would like to vote.")
        embed.add_field(name="⬅️",
                        value="This button will cause you to vote for the left waifu. The left waifu is the waifu with the **odd** Waifu ID, "
                              "the first contender, or the waifu whose votes are listed to the left.")
        embed.add_field(name="➡️",
                        value="This button will cause you to vote for the right waifu. The right waifu is the waifu with the **even** Waifu ID, "
                              "the second contender, or the waifu whose votes are listed to the right.")
        embed.add_field(name="ℹ", value="The left information button. Gets the waifu Embed of the left waifu.")
        embed.add_field(name="🇮", value="The right information button. Gets the waifu Embed of the right waifu.")
        embed.add_field(name="🚫",
                        value="The division skip button. Allows you to get the information for the next division without voting for the given "
                              "division. Note, that if you click this button, you can still go back and vote on the previous division.")
        await ctx.send(embed=embed)

    async def guide_step_3(self, ctx: discord.ext.commands.Context):
        self.guide_data[ctx.author.id] = 3
        embed = Embed(ctx, title="Step 3: Using a Vote Result",
                      description="The vote result will contain two emojis. Read how each emoji works. Note that you can click a button more than "
                                  "once, and have the same action repeat. For the purposes of this guide, please click the **🚫** emoji.")
        embed.add_field(name="✅", value="The continue button. Brings up the next division, where you can get info and vote again.")
        embed.add_field(name="🚫",
                        value="The undo vote button. If you accidentally voted for the wrong character, click this button to undo your vote.")
        await ctx.send(embed=embed)

    async def guide_step_4(self, ctx: discord.ext.commands.Context):
        self.guide_data[ctx.author.id] = 4
        embed = Embed(ctx, title="Step 4: Using an Undo Vote Result",
                      description="The unvote result will contain one emoji. Read how it works and then click it to continue the guide. You're "
                                  "almost done -- one more step to go!")
        embed.add_field(name="✅",
                        value="The continue button. Brings up the division of the waifu that you removed your vote for, where you can get info and "
                              "vote again.")
        await ctx.send(embed=embed)

    async def guide_step_5(self, ctx: discord.ext.commands.Context):
        await ctx.send(embed=Embed(ctx, title="Final Step: Resuming the War",
                                   description="If for whatever reason, you are unable to complete the entire Waifu War in a single session, "
                                               "you can type `%ww ld` to bring up the last division you voted for. This Embed will contain a single "
                                               "check mark, which will open up the next division. Now go out there and vote for your waifu!"))
        del self.guide_data[ctx.author.id]

    async def on_reaction(self, msg: discord.Message, emoji: Union[discord.PartialEmoji, discord.Emoji], user: discord.Member):
        if user.id == self.bot.user.id or user.bot or msg.author.id != self.bot.user.id or not msg.embeds or not msg.embeds[0].title:
            return
        embed: discord.Embed = msg.embeds[0]
        ctx: CustomContext = await self.bot.get_context(msg, cls=CustomContext)
        ctx.author = user
        if embed.title == "Voted":
            if "✅" in str(emoji):
                bracket_id = int(embed.fields[0].value)
                division_id = int(embed.fields[1].value)
                return await self.division.fully_run_command(ctx, bracket_id, division_id + 1)
            elif "🚫" in str(emoji):
                waifu_id = int(embed.fields[2].value)
                return await self.un_vote.fully_run_command(ctx, id_or_name=waifu_id)
        elif embed.title.startswith("Division "):
            bracket_id = int(embed.fields[0].value)
            division_id = int(embed.fields[1].value)
            right_id = division_id * 2
            left_id = right_id - 1
            if "⬅️" in str(emoji):
                return await self.vote.fully_run_command(ctx, id_or_name=left_id)
            elif "➡️" in str(emoji):
                return await self.vote.fully_run_command(ctx, id_or_name=right_id)
            elif "ℹ" in str(emoji):
                return await self.waifu.fully_run_command(ctx, bracket_id, id_or_name=left_id)
            elif "🇮" in str(emoji):
                return await self.waifu.fully_run_command(ctx, bracket_id, id_or_name=right_id)
            elif "🚫" in str(emoji):
                return await self.division.fully_run_command(ctx, bracket_id, division_id + 1)
        elif embed.title == "Vote Removed":
            if "✅" in str(emoji):
                bracket_id = int(embed.fields[0].value)
                division_id = int(embed.fields[1].value)
                return await self.division.fully_run_command(ctx, bracket_id, division_id)
        elif embed.title == "Already Voted":
            if "🚫" in str(emoji):
                waifu_id = int(embed.fields[3].value)
                return await self.un_vote.fully_run_command(ctx, id_or_name=waifu_id)
        elif embed.title == "Never Participated":
            if "✅" in str(emoji):
                return await self.guide.fully_run_command(ctx)
        elif embed.title == "Previous Division":
            if "✅" in str(emoji):
                bracket_id = int(embed.fields[0].value)
                division_id = int(embed.fields[1].value)
                return await self.division.fully_run_command(ctx, bracket_id, division_id + 1)
        elif embed.title == "Guide":
            if "✅" in str(emoji):
                return await self.guide_step_1(ctx)
        elif embed.title == "Step 1: Summoning a Division":
            if "✅" in str(emoji):
                return await self.division.fully_run_command(ctx, 1)
        elif embed.title == "Start Guide":
            if "✅" in str(emoji):
                return await self.guide.fully_run_command(ctx)
            elif "🚫" in str(emoji):
                bracket_id = int(embed.fields[0].value)
                division_id = int(embed.fields[1].value)
                return await self.division.fully_run_command(ctx, bracket_id, division_id, _continue=True)
        elif embed.title == "Start Voting":
            if "✅" in str(emoji):
                chan = self.bot.get_channel_data(ctx.guild, "bot-spam")
                ctx.channel = chan
                return await self.division.fully_run_command(ctx, 1)
        elif embed.title.startswith("Waifu Request"):
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                name = embed.fields[0].value
                anime = embed.fields[1].value
                image_url = embed.image.url
                description = embed.description
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.add_waifu.fully_run_command(ctx, name, image_url, anime, description=description, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu request has been accepted.", color=discord.Color.green())
                embed2.add_field(name="Waifu Name", value=name)
                embed2.add_field(name="Anime", value=anime)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    name = embed.fields[0].value
                    anime = embed.fields[1].value
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed2 = Embed(ctx, title="Rejected", description="Your waifu request has been rejected.", color=discord.Color.red())
                    embed2.add_field(name="Waifu Name", value=name)
                    embed2.add_field(name="Anime", value=anime)
                    embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed2.set_footer(
                        text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed2)
                    except discord.Forbidden:
                        return
            elif "🇦" in str(emoji):
                embed2 = Embed(ctx, title="Anime", description="Type the anime of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                anime = message.content
                name = embed.fields[0].value
                f1 = embed.fields[1]
                old = f1.value
                embed.set_field_at(1, name=f1.name, value=anime, inline=f1.inline)
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Anime Changed", description="The anime for your waifu request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                embed3.add_field(name="Old Anime", value=old)
                embed3.add_field(name="New Anime", value=anime)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return
            elif "🇩" in str(emoji):
                embed2 = Embed(ctx, title="Description", description="Type the description of the waifu you want to add.",
                               color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                description = message.content
                name = embed.fields[0].value
                old = embed.description
                embed.description = description
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Description Changed", description="The description for your waifu request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                if len(old) > 1024:
                    old = old[:1021] + "..."
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed3.add_field(name="Old Description", value=old)
                embed3.add_field(name="New Description", value=description)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return
            elif "🇮" in str(emoji):
                name = embed.fields[0].value
                embed2 = Embed(ctx, title="Image", description="Send the image of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: (message.author == ctx.author and message.channel == ctx.channel) and (
                                                          (message.content or "").startswith("http") or message.attachments), timeout=120)
                if message.content:
                    image = message.content
                else:
                    attachment: discord.Attachment = message.attachments[0]
                    file: discord.File = await attachment.to_file()
                    chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_image_channel_id)
                    msg = await chan.send(embed=Embed(ctx, title=name), file=file)
                    attachment_2: discord.Attachment = msg.attachments[0]
                    image = attachment_2.url
                old = embed.image.url
                embed.set_image(url=image)
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Image Changed", description="The image for your waifu request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                embed3.add_field(name="Old Image Link", value=old)
                embed3.add_field(name="New Image Link", value=image)
                embed3.set_image(url=image)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return
            elif "🇳" in str(emoji):
                embed2 = Embed(ctx, title="Name", description="Type the name of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                name = message.content
                await self.get_conn()
                async with self.log_and_run("""SELECT NAME FROM WAIFUS""") as cursor:
                    data = [item.casefold() for item, in await cursor.fetchall()]
                if name.casefold() in data:
                    embed2 = Embed(ctx, title="Waifu Name in Use",
                                   description=f"A waifu with that name already exists. Change the other waifu's name with `"
                                               f"{self.bot.command_prefix}waifu_war modify name`.",
                                   color=discord.Color.red())
                    embed2.add_field(name="Waifu Name", value=name)
                    return await ctx.send(embed=embed2)
                else:
                    f0 = embed.fields[0]
                    old = f0.value
                    embed.set_field_at(0, name=f0.name, value=name, inline=f0.inline)
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed3 = Embed(ctx, title="Name Changed", description="The name for your waifu request has been changed.")
                    embed3.add_field(name="Old Name", value=old)
                    embed3.add_field(name="New Name", value=name)
                    embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed3.set_footer(
                        text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed3)
                    except discord.Forbidden:
                        return
        elif embed.title.startswith("Possible Alias"):
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                name = embed.fields[0].value
                alias = embed.fields[1].value
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.add_alias.fully_run_command(ctx, name, alias, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu alias request has been accepted.", color=discord.Color.green())
                embed2.add_field(name="Waifu Name", value=name)
                embed2.add_field(name="Waifu Alias", value=alias)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                    name = embed.fields[0].value
                    alias = embed.fields[1].value
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed2 = Embed(ctx, title="Rejected", description="Your waifu alias request has been rejected.", color=discord.Color.red())
                    embed2.add_field(name="Waifu Name", value=name)
                    embed2.add_field(name="Waifu Alias", value=alias)
                    embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed2.set_footer(
                        text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed2)
                    except discord.Forbidden:
                        return
                elif "🇦" in str(emoji):
                    embed2 = Embed(ctx, title="Alias", description="Type the name of the alias you want to add to the waifu.",
                                   color=discord.Color.green())
                    await ctx.send(embed=embed2)
                    message = await self.bot.wait_for("message",
                                                      check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                      timeout=120)
                    alias = message.content
                    await self.get_conn()
                    async with self.log_and_run("""SELECT ALIAS, NAME FROM ALIASES""") as cursor:
                        data = {alias.casefold(): name.casefold() async for alias, name in cursor}
                    if alias.casefold() in data:
                        embed3 = Embed(ctx, title="Alias Already Exists",
                                       description="The alias you provided already exists.",
                                       color=discord.Color.red())
                        embed3.add_field(name="Waifu/Anime Name", value=data[alias.casefold()])
                        embed3.add_field(name="Alias", value=alias)
                        await ctx.send(embed=embed)
                    else:
                        name = embed.fields[0].value
                        f1 = embed.fields[1]
                        old = f1.value
                        embed.set_field_at(1, name=f1.name, value=alias, inline=f1.inline)
                        await msg.edit(embed=embed)
                        username, sep, user_id = embed.author.name.partition(" • User ID: ")
                        assert sep and user_id, "The User ID was not found in the author name."
                        user = self.bot.get_user(int(user_id))
                        if user is None:  # not in a bot Guild anymore
                            return
                        embed3 = Embed(ctx, title="Alias Changed", description="The alias for your request has been changed.")
                        embed3.add_field(name="Waifu Name", value=name)
                        embed3.add_field(name="Old Alias", value=old)
                        embed3.add_field(name="New Alias", value=alias)
                        embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                        embed3.set_footer(
                            text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                        try:
                            await user.send(embed=embed3)
                        except discord.Forbidden:
                            return
                elif "🇳" in str(emoji):
                    embed = Embed(ctx, title="Name", description="Type the name of the waifu you want to add an alias for.",
                                  color=discord.Color.green())
                    await ctx.send(embed=embed)
                    message = await self.bot.wait_for("message",
                                                      check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                      timeout=120)
                    name = message.content
                    f0 = embed.fields[0]
                    old = f0.value
                    embed.set_field_at(0, name=f0.name, value=name, inline=f0.inline)
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed3 = Embed(ctx, title="Name Changed", description="The name for your alias request has been changed.")
                    embed3.add_field(name="Old Name", value=old)
                    embed3.add_field(name="New Name", value=name)
                    embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed3.set_footer(
                        text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed3)
                    except discord.Forbidden:
                        return
        elif embed.title == "Waifu Rename Request":
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                old = embed.fields[0].value
                new = embed.fields[1].value
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.modify_name.fully_run_command(ctx, old, new_waifu_name=new, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu rename request has been accepted.", color=discord.Color.green())
                embed2.add_field(name="Old Waifu Name", value=old)
                embed2.add_field(name="New Waifu Name", value=new)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                    old = embed.fields[0].value
                    new = embed.fields[1].value
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed2 = Embed(ctx, title="Rejected", description="Your waifu rename request has been rejected.", color=discord.Color.red())
                    embed2.add_field(name="Old Waifu Name", value=old)
                    embed2.add_field(name="New Waifu Name", value=new)
                    embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed2.set_footer(
                        text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed2)
                    except discord.Forbidden:
                        return
            elif "🇳" in str(emoji):
                embed2 = Embed(ctx, title="Name", description="Type the name of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                name = message.content
                await self.get_conn()
                async with self.log_and_run("""SELECT NAME FROM WAIFUS""") as cursor:
                    data = [item.casefold() for item, in await cursor.fetchall()]
                if name.casefold() in data:
                    embed2 = Embed(ctx, title="Waifu Name in Use",
                                   description=f"A waifu with that name already exists. Change the other waifu's name with `"
                                               f"{self.bot.command_prefix}waifu_war modify name`.",
                                   color=discord.Color.red())
                    embed2.add_field(name="Waifu Name", value=name)
                    return await ctx.send(embed=embed2)
                else:
                    f0 = embed.fields[0]
                    old = f0.value
                    embed.set_field_at(0, name=f0.name, value=name, inline=f0.inline)
                    await msg.edit(embed=embed)
                    username, sep, user_id = embed.author.name.partition(" • User ID: ")
                    assert sep and user_id, "The User ID was not found in the author name."
                    user = self.bot.get_user(int(user_id))
                    if user is None:  # not in a bot Guild anymore
                        return
                    embed3 = Embed(ctx, title="Name Changed", description="The name for your waifu rename request has been changed.")
                    embed3.add_field(name="Old Name", value=old)
                    embed3.add_field(name="New Name", value=name)
                    embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                    embed3.set_footer(
                        text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                    try:
                        await user.send(embed=embed3)
                    except discord.Forbidden:
                        return
        elif embed.title == "Waifu Description Change Request":
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                name = embed.fields[0].value
                description = embed.description.lstrip("New Description: ")
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.modify_description.fully_run_command(ctx, name, description=description, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu description change request has been accepted.",
                               color=discord.Color.green())
                embed2.add_field(name="Waifu Name", value=name)
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed2.add_field(name="New Description", value=description)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                name = embed.fields[0].value
                description = embed.description.lstrip("New Description: ")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Rejected", description="Your waifu description change request has been rejected.",
                               color=discord.Color.red())
                embed2.add_field(name="Waifu Name", value=name)
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed2.add_field(name="New Description", value=description)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🇩" in str(emoji):
                embed2 = Embed(ctx, title="Description", description="Type the description of the waifu you want to add.",
                               color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                description = message.content
                name = embed.fields[0].value
                old = embed.description.lstrip("New Description: ")
                embed.description = "New Description: " + description
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Description Changed",
                               description="The description for your waifu description change request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                if len(old) > 1024:
                    old = old[:1021] + "..."
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed3.add_field(name="Old Description", value=old)
                embed3.add_field(name="New Description", value=description)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return
        elif embed.title == "Waifu Anime Change Request":
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                name = embed.fields[0].value
                anime = embed.fields[1].value
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.modify_anime.fully_run_command(ctx, name, description=anime, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu anime change request has been accepted.", color=discord.Color.green())
                embed2.add_field(name="Waifu Name", value=name)
                if len(anime) > 1024:
                    anime = anime[:1021] + "..."
                embed2.add_field(name="New Anime", value=anime)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                name = embed.fields[0].value
                anime = embed.fields[1].value
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Rejected", description="Your waifu anime change request has been rejected.", color=discord.Color.red())
                embed2.add_field(name="Waifu Name", value=name)
                if len(anime) > 1024:
                    anime = anime[:1021] + "..."
                embed2.add_field(name="New Anime", value=anime)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🇦" in str(emoji):
                embed2 = Embed(ctx, title="Anime", description="Type the anime of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: message.author == ctx.author and message.channel == ctx.channel,
                                                  timeout=120)
                anime = message.content
                name = embed.fields[0].value
                f2 = embed.fields[2]
                old = f2.value
                embed.set_field_at(2, name=f2.name, value=anime, inline=f2.inline)
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Anime Changed", description="The anime for your waifu anime change request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                embed3.add_field(name="Old Anime", value=old)
                embed3.add_field(name="New Anime", value=anime)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return
        elif embed.title == "Waifu Image Change Request":
            if user.id != self.bot.owner_id:
                return
            if "✅" in str(emoji):
                if embed.fields[2].value.lower() != "open":
                    return
                name = embed.fields[0].value
                image = embed.image.url
                ctx.author = self.bot.get_user(self.bot.owner_id)
                await self.modify_image.fully_run_command(ctx, name, description=image, _reaction=True)
                embed.set_field_at(2, name=embed.fields[2].name, value="Accepted")
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Accepted", description="Your waifu image change request has been accepted.", color=discord.Color.green())
                embed2.add_field(name="Waifu Name", value=name)
                if len(image) > 1024:
                    image = image[:1021] + "..."
                embed2.add_field(name="New Image Link", value=image)
                embed2.set_image(url=image)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🚫" in str(emoji):
                if embed.fields[2].value.lower() == "open":
                    embed.set_field_at(2, name=embed.fields[2].name, value="Closed")
                name = embed.fields[0].value
                image = embed.fields[1].value
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed2 = Embed(ctx, title="Rejected", description="Your waifu image change request has been rejected.", color=discord.Color.red())
                embed2.add_field(name="Waifu Name", value=name)
                if len(image) > 1024:
                    image = image[:1021] + "..."
                embed2.add_field(name="New Image Link", value=image)
                embed2.set_image(url=image)
                embed2.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed2.set_footer(
                    text=embed2.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed2)
                except discord.Forbidden:
                    return
            elif "🇮" in str(emoji):
                name = embed.fields[0].value
                embed2 = Embed(ctx, title="Image", description="Send the image of the waifu you want to add.", color=discord.Color.green())
                await ctx.send(embed=embed2)
                message = await self.bot.wait_for("message",
                                                  check=lambda message: (message.author == ctx.author and message.channel == ctx.channel) and (
                                                          (message.content or "").startswith("http") or message.attachments), timeout=120)
                if message.content:
                    image = message.content
                else:
                    attachment: discord.Attachment = message.attachments[0]
                    file: discord.File = await attachment.to_file()
                    chan: discord.TextChannel = self.bot.get_guild(bot_support_server_id).get_channel(bot_support_waifu_image_channel_id)
                    msg = await chan.send(embed=Embed(ctx, title=name), file=file)
                    attachment_2: discord.Attachment = msg.attachments[0]
                    image = attachment_2.url
                old = embed.image.url
                embed.set_image(url=image)
                await msg.edit(embed=embed)
                username, sep, user_id = embed.author.name.partition(" • User ID: ")
                assert sep and user_id, "The User ID was not found in the author name."
                user = self.bot.get_user(int(user_id))
                if user is None:  # not in a bot Guild anymore
                    return
                embed3 = Embed(ctx, title="Image Changed", description="The image for your waifu image change request has been changed.")
                embed3.add_field(name="Waifu Name", value=name)
                embed3.add_field(name="Old Image Link", value=old)
                embed3.add_field(name="New Image Link", value=image)
                embed3.set_image(url=image)
                embed3.add_field(name="Data Embed", value=ctx.message.jump_url)
                embed3.set_footer(
                    text=embed3.footer.text + f" • To view the Data Embed, join the support server with {self.bot.command_prefix}support.")
                try:
                    await user.send(embed=embed3)
                except discord.Forbidden:
                    return


def setup(bot: "PokestarBot"):
    cog = Waifu(bot)
    bot.add_cog(cog)
    if hasattr(bot, "_guide_data"):
       cog.guide_data = bot._guide_data
       del bot._guide_data
    logger.info("Loaded the Waifu extension.")
    pass


def teardown(bot: "PokestarBot"):
    cog: Waifu = bot.cogs["Waifu"]
    bot._guide_data = cog.guide_data
    asyncio.gather(cog.conn.close())
    logger.warning("Unloading the Waifu extension.")
    pass
