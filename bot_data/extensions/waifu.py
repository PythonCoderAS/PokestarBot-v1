import asyncio
import logging
from typing import Iterable, List, Optional, TYPE_CHECKING, Union

import discord.ext.commands

from . import PokestarBotCog
from ..converters import BracketStatusConverter, WaifuIDConverter
from ..utils import Embed, TimedCache, generate_embeds_fields
from ..utils.data import EmbedData
from ..utils.data.waifu import Bracket, BracketContainer, BracketStatus, Waifu as WaifuObj
from ..utils.data.waifu.global_bracket import generate_global_data

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class WaifuNew(PokestarBotCog):

    @property
    def conn(self):
        return self.bot.conn

    @property
    def setup_done(self) -> asyncio.Event:
        return self.bot.setup_done

    @property
    def bracket_cache(self) -> Optional[BracketContainer]:
        return self.bot.bracket_cache

    @bracket_cache.setter
    def bracket_cache(self, value: BracketContainer):
        self.bot.bracket_cache = value

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.embed_data_cache: TimedCache[int, EmbedData] = TimedCache()

    @staticmethod
    def get_color(item: object):
        return discord.Color.green() if item else discord.Color.red()

    async def pre_create(self):
        if not self.setup_done.is_set():
            async with self.conn.execute("""CREATE TABLE IF NOT EXISTS BRACKETS(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL, 
            STATUS TINYINT DEFAULT 1, GUILD_ID BIGINT NOT NULL, OWNER_ID BIGINT NOT NULL)"""):
                pass
            async with self.conn.execute(
                    """CREATE TABLE IF NOT EXISTS ALIASES(ALIAS TEXT PRIMARY KEY UNIQUE, NAME TEXT NOT NULL, unique(ALIAS, NAME))"""):
                pass
            async with self.conn.execute(
                    """CREATE TABLE IF NOT EXISTS WAIFUS(ID INTEGER PRIMARY KEY AUTOINCREMENT, NAME TEXT NOT NULL UNIQUE COLLATE NOCASE, 
                    DESCRIPTION TEXT NOT NULL, ANIME TEXT NOT NULL COLLATE NOCASE, IMAGE TEXT NOT NULL)"""):
                pass
            async with self.conn.execute(
                    """CREATE TABLE IF NOT EXISTS BRACKET_DATA(ID INTEGER PRIMARY KEY, RANK INTEGER NOT NULL,
                    BRACKET_ID INTEGER NOT NULL REFERENCES BRACKETS(ID) ON UPDATE CASCADE ON DELETE CASCADE,
                    GID INTEGER NOT NULL REFERENCES WAIFUS(ID) ON UPDATE CASCADE ON DELETE CASCADE, UNIQUE (BRACKET_ID, GID))"""):
                pass
            async with self.conn.execute("""CREATE TABLE IF NOT EXISTS VOTES(ID INTEGER PRIMARY KEY, USER_ID BIGINT NOT NULL,
                    BRACKET_ID INTEGER NOT NULL REFERENCES BRACKETS(ID) ON UPDATE CASCADE ON DELETE CASCADE,
                    GID INTEGER REFERENCES WAIFUS(ID) ON UPDATE CASCADE ON DELETE CASCADE, UNIQUE (USER_ID, BRACKET_ID, GID))"""):
                pass

    @discord.ext.commands.group(brief="Main group for the Waifu Wars command", invoke_without_command=True, aliases=["ww", "waifuwar"],
                                usage="subcommand", significant=True)
    async def waifu_war(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    async def get_bracket_from_none(self, guild: discord.Guild, bracket_id: Optional[Union[str, int]] = None, raise_on_none: bool = False) -> Bracket:
        guild_brackets = self.bracket_cache.filter_guild(guild)
        if bracket_id is not None:
            if isinstance(bracket_id, str):
                bracket_id, _ = await Bracket.GLOBAL.resolve_bracket_id_from_name(bracket_id, guild=guild)
            return guild_brackets.get_bracket(bracket_id)
        if len(guild_brackets) == 1:
            return next(iter(guild_brackets.values()))
        else:
            votable = guild_brackets.get_voting(guild)
            if votable is None:
                if raise_on_none:
                    self.bot.missing_argument("bracket_id")
                else:
                    return Bracket.GLOBAL
            else:
                return votable

    @waifu_war.group(brief="Get information on a bracket.", usage="[bracket_id]", aliases=["getbracket", "gb", "b", "get_bracket"], significant=True,
                     invoke_without_command=True)
    async def bracket(self, ctx: discord.ext.commands.Context, *, bracket_id: Optional[Union[int, str]] = None):
        bracket = await self.get_bracket_from_none(ctx.guild, bracket_id=bracket_id)
        length = len(bracket)
        description = f"This bracket contains {length} waifus. There are {length // 2} divisions. The bracket is **" \
                      f"{bracket.status.name.title()}**. It is owned by {bracket.creator.mention}."
        if bracket.votable:
            description += " The bracket has met the requirements to start voting."
        embed = Embed(ctx, title=f"Bracket {bracket.id}: " + bracket.name, description=description)
        if bracket:
            fields = [
                "\n".join(waifu.representation(show_rank=True, show_votes=bracket.status == BracketStatus.VOTABLE) for id, waifu in sorted(bracket))]
            embed_data = await generate_embeds_fields(embed, fields)
        else:
            embed_data = [embed]
        return self.cache_data(ctx, embed_data)

    async def cache_data(self, ctx: discord.abc.Messageable, embed_data: Iterable[discord.Embed]):
        max = len(embed_data)
        for num, embed in enumerate(embed_data, start=1):
            embed.set_footer(text=f"Page {num} of {max} • " + embed.footer.text)
        bracket_cache = EmbedData(embed_data)
        msg = await ctx.send(embed=bracket_cache.current_page)
        await msg.add_reaction("⬅")
        await msg.add_reaction("◀")
        await msg.add_reaction("▶")
        await msg.add_reaction("➡")
        self.embed_data_cache[msg.id] = bracket_cache

    @bracket.command(brief="View the list of brackets for the Guild.", usage="[status]")
    async def list(self, ctx: discord.ext.commands.Context, *, status: BracketStatusConverter = BracketStatus.DEFAULT):
        brackets = self.bracket_cache.filter_guild(ctx.guild).filter_status(status)
        embed = Embed(ctx, title=f"Brackets for {ctx.guild.name}", description=f"This guild contains **{len(brackets)}** brackets.",
                      color=self.get_color(brackets))
        embed.add_field(name="Status Code", value=status.value)
        embed.add_field(name="Status Name", value=status.name)
        if brackets:
            field_str = ""
            for bracket in brackets.values():
                field_str += bracket.representation() + "\n"
            embed_data = await generate_embeds_fields(embed, [field_str], inline_fields=False)
        else:
            embed_data = [embed]
        await self.cache_data(ctx, embed_data)

    @bracket.command(brief="Create a bracket.", usage="name")
    @discord.ext.commands.cooldown(1, 300, type=discord.ext.commands.BucketType.user)
    async def create(self, ctx: discord.ext.commands.Context, *, name: str):
        bracket = await self.bracket_cache.create_and_add(name, ctx.author, ctx.guild)
        return await self.bracket(ctx, bracket_id=bracket.id)

    @bracket.command(brief="Browse the waifus of a bracket.", usage="[bracket_id]")
    async def browse(self, ctx: discord.ext.commands.Context, *, bracket_id: Optional[Union[int, str]] = None):
        logger.debug("Bracket_id: %s, type: %s, isnumeric: %s", bracket_id, type(bracket_id), str(bracket_id).isnumeric())
        bracket = await self.get_bracket_from_none(ctx.guild, bracket_id=bracket_id)
        embed_data = []
        for id, waifu in bracket:
            embed_data.extend(await self.waifu_embed(ctx, waifu))
        for embed in embed_data:
            embed.title = "Waifu Browser: " + embed.title
        await self.cache_data(ctx, embed_data)

    @waifu_war.group(brief="Get the waifus in a bracket with the given anime", usage="[bracket_id] name", invoke_without_command=True)
    async def anime(self, ctx: discord.ext.commands.Context, bracket_id: Optional[int] = None, *, anime_name: str):
        bracket = await self.get_bracket_from_none(ctx.guild, bracket_id=bracket_id)
        anime_name, filtered = await bracket.filter_anime(anime_name)
        if bracket_id == 0:
            bracket_name = "the global waifu database"
        else:
            bracket_name = f"Bracket #{bracket_id}"
        description = f"{len(filtered)} waifus contain the anime `{anime_name}` in {bracket_name}."
        embed = Embed(ctx, title="Anime Filter Results", description=description, color=self.get_color(filtered))
        if filtered:
            fields = ["\n".join(
                waifu.representation(show_rank=True, show_votes=bracket_id != 0 and bracket.status == BracketStatus.VOTABLE) for id, waifu in
                sorted(filtered))]
            embed_data = await generate_embeds_fields(embed, fields)
        else:
            embed_data = [embed]
        await self.cache_data(ctx, embed_data)

    @anime.command(name="list", brief="List all animes in the bracket", usage="[bracket_id]")
    async def anime_list(self, ctx: discord.ext.commands.Context, *, bracket_id: Optional[int] = None):
        bracket = await self.get_bracket_from_none(ctx.guild, bracket_id=bracket_id)
        data = set(name for name, in bracket.attributes("anime").values())
        if bracket_id == 0:
            bracket_name = "the global waifu database"
        else:
            bracket_name = f"Bracket #**{bracket_id}**"
        description = f"{len(data)} animes exist in {bracket_name}."
        embed = Embed(ctx, title="Anime Breakdown", description=description, color=self.get_color(data))
        if data:
            field_str = ""
            for item in data:
                filtered = bracket.filter_attributes(anime=item)
                field_str += f"**{item}**: " + ", ".join(waifu.name for id, waifu in filtered) + f" ({len(filtered)} waifus"
                if bracket.status == BracketStatus.VOTABLE:
                    field_str += f", {filtered.total_votes} total votes)"
                else:
                    field_str += ")"
                field_str += "\n"
            embed_data = await generate_embeds_fields(embed, fields=[field_str.rstrip()])
        else:
            embed_data = [embed]
        await self.cache_data(ctx, embed_data)

    @waifu_war.command(brief="Rebuild the bracket cache")
    @discord.ext.commands.is_owner()
    async def rebuild(self, ctx: discord.ext.commands.Context):
        for _, waifu in Bracket.GLOBAL:
            waifu: WaifuObj
            waifu._global_connections = []
        self.bracket_cache = await BracketContainer.from_conn(self.conn)
        return ctx.send(embed=Embed(ctx, title="Cache Rebuilt", description="The cache has been successfully rebuilt.", color=discord.Color.green()))

    @staticmethod
    async def waifu_embed(ctx: discord.ext.commands.Context, waifu: WaifuObj):
        embed = Embed(ctx, title=f"{waifu.unique_id}: {waifu.name}", description=waifu.description)
        embed.set_image(url=waifu.image_link)
        fields = [("Anime", waifu.anime), ("Aliases", ", ".join(f"`{alias}`" for alias in waifu.aliases) or "**No Aliases**")]
        if waifu.bracket.votable:
            fields.append(("Votes", len(waifu.votes)))
        if waifu.is_global:
            fields.append(("Brackets Used In", str(len(waifu._global_connections))))
            fields.append(("Votes Earned In All Brackets", str(waifu._global_connections.total_votes)))
        return await generate_embeds_fields(embed, fields)

    @property
    def send_all(self):
        return self.bot.send_all

    @waifu_war.command(brief="Get the data on a waifu")
    async def waifu(self, ctx: discord.ext.commands.Context, *, waifu_id: Union[WaifuIDConverter, int, str]):
        if isinstance(waifu_id, (int, str)):
            if isinstance(waifu_id, str) and waifu_id.lower().startswith("g-") and waifu_id[2:]:
                waifu_id = waifu_id[2:]
                bracket = Bracket.GLOBAL
            else:
                bracket = await self.get_bracket_from_none(ctx.guild)
            if bracket is None:
                if isinstance(waifu_id, int):
                    raise discord.ext.commands.BadArgument(
                        f"Please use the Bracket-GID syntax, such as `1-{waifu_id}`, or prefix a `G-` to the waifu ID in order to get the Global "
                        f"Waifu, such as `G-{waifu_id}`.")
                elif isinstance(waifu_id, str):
                    raise discord.ext.commands.BadArgument(
                        f"Please use the Bracket-Search syntax, such as `1-{waifu_id}, or prefix a `G-` to the search in order to get a Global "
                        f"Waifu, such as `G-{waifu_id}`.")
            elif isinstance(waifu_id, int):
                waifu_id = bracket.get_waifu(waifu_id)
            elif isinstance(waifu_id, str):
                waifu_id = await bracket.resolve_waifu_from_name(waifu_id)
        waifu_id: WaifuObj
        return await self.send_all(ctx, await self.waifu_embed(ctx, waifu_id))

    @discord.ext.commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.on_ready_wait:
            await self.pre_create()
            await generate_global_data()
            self.bracket_cache = await BracketContainer.from_conn(self.conn)
            self.setup_done.set()

    async def on_reaction_for_cache_embeds(self, cache: TimedCache[int, EmbedData], msg: discord.Message,
                                           emoji: Union[discord.PartialEmoji, discord.Emoji]):
        try:
            item = cache.get(msg.id)
            if item is None:
                return
            existing_page = item.num
            if "⬅" in str(emoji):
                new_embed = await item.at_page(1)
            elif "◀" in str(emoji):
                new_embed = await item.previous()
            elif "▶" in str(emoji):
                new_embed = await item.next()
            elif "➡" in str(emoji):
                new_embed = await item.at_page(item.pages)
            else:
                logger.debug("Could not identify emoji, returning.")
                return
            new_page = item.num
            if existing_page != new_page:
                return await msg.edit(embed=new_embed)
        except discord.ext.commands.CommandError as exc:
            logger.debug("Caught error!")
            ctx = await self.bot.get_context(msg)
            return await self.bot.on_command_error(ctx, exc)

    async def on_reaction(self, msg: discord.Message, emoji: Union[discord.PartialEmoji, discord.Emoji], user: discord.Member):
        if msg.author != self.bot.user or not msg.embeds:
            return
        embed = msg.embeds[0]
        if any(embed.title.startswith(item) for item in ["Bracket ", "Anime Filter Results", "Anime Breakdown", "Brackets for", "Waifu Browser:"]):
            return await self.on_reaction_for_cache_embeds(self.embed_data_cache, msg, emoji)


def setup(bot: "PokestarBot"):
    # bot.add_cog(WaifuNew(bot))
    # logger.info("Loaded the Waifu extension.")
    pass


def teardown(_bot: "PokestarBot"):
    # logger.warning("Unloading the Waifu extension.")
    pass
