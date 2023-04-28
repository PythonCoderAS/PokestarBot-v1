import asyncio
import html
import logging
import re
import sqlite3
import traceback
from typing import Optional, TYPE_CHECKING, Union

import bbcode
import discord.ext.commands
import discord.ext.tasks
import pytz

from . import PokestarBotCog
from ..const import bot_version, guyamoe, mangadex, nyaasi
from ..utils import CustomContext, Embed, get_filter_level, loop_command_deco, post_issue, send_embeds_fields
from ..utils.data.guyamoe import GuyamoeManga
from ..utils.data.mangadex import MangadexChapterList, MangadexManga
from ..utils.data.nyaasi import BaseTitleParser, NyaaCategoryTypes, NyaaTorrent, NyaaTorrentList, author_parser_mapping, search_string_builder

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)
NY = pytz.timezone("America/New_York")


class Updates(PokestarBotCog):
    GUYAMOE_URL = guyamoe
    MANGADEX_URL = mangadex
    NYAASI_URL = nyaasi

    @property
    def conn(self):
        return self.bot.conn

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.parser = self.set_up_parser()
        self.checked_for = []
        self.check_for_updates.start()
        check = self.bot.has_channel("anime-and-manga-updates")
        self.bot.add_check_recursive(self.updates, check)
        self.bot.remove_check_recursive(self.loop, check)

    def cog_unload(self):
        self.check_for_updates.stop()

    @staticmethod
    def render_url(name, value, options, parent, context):
        if options and "url" in options:
            href = options["url"]
        else:
            href = value
        return "[{text}]({href})".format(href=href, text=html.unescape(value))

    def set_up_parser(self):
        parser = bbcode.Parser(newline="\n", install_defaults=False, escape_html=False, url_template="[{text}]({href})", replace_cosmetic=False)
        parser.add_simple_formatter("b", "**%(value)s**", render_embedded=True)
        parser.add_simple_formatter("i", "*%(value)s*", render_embedded=True)
        parser.add_simple_formatter("u", "__%(value)s__", render_embedded=True)
        parser.add_simple_formatter("hr", "\n\n", standalone=True, render_embedded=False)
        parser.add_simple_formatter("spoiler", "||%(value)s||")
        parser.add_simple_formatter("*", "", standalone=True)
        parser.add_simple_formatter("img", "")
        parser.add_simple_formatter("quote", "```\n%(value)s\n```")
        parser.add_simple_formatter("code", "`%(value)s`")
        parser.add_formatter("url", self.render_url, replace_links=False, replace_cosmetic=False)
        return parser

    async def pre_create(self):
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS GUYAMOE(ID INTEGER PRIMARY KEY, SLUG TEXT, NAME TEXT NOT NULL, USER_ID UNSIGNED BIGINT NOT NULL, 
                COMPLETED BOOLEAN NOT NULL DEFAULT FALSE, GUILD_ID BIGINT NOT NULL, UNIQUE (SLUG, NAME, USER_ID, GUILD_ID))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS MANGADEX(ID INTEGER PRIMARY KEY, MANGA_ID INTEGER NOT NULL, NAME TEXT NOT NULL, USER_ID UNSIGNED 
                BIGINT NOT NULL, COMPLETED BOOLEAN NOT NULL DEFAULT FALSE, GUILD_ID BIGINT NOT NULL, UNIQUE (MANGA_ID, NAME, USER_ID, GUILD_ID))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS NYAASI(ID INTEGER PRIMARY KEY, NAME TEXT NOT NULL, USER_ID UNSIGNED BIGINT NOT NULL, 
                COMPLETED BOOLEAN NOT NULL DEFAULT FALSE, GUILD_ID BIGINT NOT NULL, UNIQUE(NAME, USER_ID, GUILD_ID))"""):
            pass
        async with self.conn.execute(
                """CREATE TABLE IF NOT EXISTS SEEN(ID INTEGER PRIMARY KEY, SERVICE TEXT NOT NULL, ITEM TEXT NOT NULL, CHAPTER TEXT NOT NULL, 
                UNIQUE (SERVICE, ITEM, CHAPTER))"""):
            pass
        async with self.conn.execute("""CREATE TABLE IF NOT EXISTS NYAASI_SEEN(ID INTEGER PRIMARY KEY)"""):
            pass

    async def get_conn(self):
        await self.pre_create()
        return self.conn

    async def guyamoe_info(self, ctx: discord.ext.commands.Context, slug: str, _info_only: bool = False):
        url = f"https://guya.moe/api/series/{slug}/"
        async with self.bot.session.get(url) as request:
            request.raise_for_status()
            json = await request.json()
        manga = GuyamoeManga.from_api(json)
        next_release = manga.next_release_timestamp.astimezone(NY).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        embed = Embed(ctx, title=manga.title, description=manga.description)
        embed.set_image(url=manga.cover_url)
        if not _info_only:
            embed.add_field(name="For User", value=ctx.author.mention)
            embed.add_field(name="Service", value="Guya.moe")
        embed.add_field(name="Link", value=f"https://guya.moe/read/manga/{slug}")
        embed.add_field(name="Author", value=manga.author)
        embed.add_field(name="Artist", value=manga.artist)
        embed.add_field(name="Latest Chapter", value=manga.chapters.latest.chapter_str)
        embed.add_field(name="Next Chapter Published In", value=next_release)
        msg = await ctx.send(embed=embed)
        if _info_only:
            return
        await msg.add_reaction("✅")
        try:
            async with self.conn.execute("""INSERT INTO GUYAMOE(SLUG, NAME, USER_ID, GUILD_ID) VALUES (?, ?, ?, ?)""",
                                         [slug, manga.title, ctx.author.id, getattr(ctx.guild, "id", None)]):
                pass
        except sqlite3.IntegrityError:
            logger.warning("", exc_info=True)
            embed = Embed(ctx, title="Manga Exists", description="The manga has been already added.", color=discord.Color.red())
            embed.add_field(name="Service", value="Guya.moe")
            embed.add_field(name="Slug", value=str(slug))
            return await ctx.send(embed=embed)
        async with self.conn.executemany("""INSERT OR IGNORE INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES ('Guyamoe', ?, ?)""",
                                         [(slug, float(chap.num)) for chap in manga.chapters]):
            pass

    @staticmethod
    def make_under_limit(string: str, limit=2048):
        if len(string) > limit:
            string = string[:limit - 3] + "..."
        return string

    async def mangadex_info(self, ctx: discord.ext.commands.Context, manga_id: int, _info_only: bool = False):
        url = f"https://mangadex.org/api/v2/manga/{manga_id}"
        async with self.bot.session.get(url) as request, self.bot.session.get(url + "/chapters") as request2:
            request.raise_for_status()
            request2.raise_for_status()
            json = await request.json()
            json2 = await request2.json()
        manga = MangadexManga.from_api_v2(json)
        manga.add_chapters_data_v2(json2)
        manga.chapters = manga.chapters.filter_lang().filter_duplicates()
        embed = Embed(ctx, title=manga.title, description=self.make_under_limit(self.parser.format(manga.description)))
        embed.set_image(url=manga.cover_url)
        if not _info_only:
            embed.add_field(name="For User", value=ctx.author.mention)
            embed.add_field(name="Service", value="MangaDex")
        embed.add_field(name="Link", value=f"https://mangadex.org/title/{manga_id}")
        embed.add_field(name="Status", value=manga.status.name)
        embed.add_field(name="Author", value=str(manga.author_str))
        embed.add_field(name="Artist", value=str(manga.artist_str))
        embed.add_field(name="Tags", value=", ".join([tag.name for tag in manga.tags]))
        embed.add_field(name="R18", value=str(manga.hentai))
        embed.add_field(name="Rating", value=str(manga.bayesian_rating))
        embed.add_field(name="Latest Chapter", value=str(getattr(manga.chapters.latest, "chapter_str", None)))
        msg = await ctx.send(embed=embed)
        if _info_only:
            return
        await msg.add_reaction("✅")
        try:
            async with self.conn.execute("""INSERT INTO MANGADEX(MANGA_ID, NAME, USER_ID, GUILD_ID) VALUES (?, ?, ?, ?)""",
                                         [manga_id, manga.title, ctx.author.id, getattr(ctx.guild, "id", None)]):
                pass
        except sqlite3.IntegrityError:
            logger.warning("", exc_info=True)
            embed = Embed(ctx, title="Manga Exists", description="The manga has been already added.", color=discord.Color.red())
            embed.add_field(name="Service", value="MangaDex")
            embed.add_field(name="Manga ID", value=str(manga_id))
            return await ctx.send(embed=embed)
        async with self.conn.executemany("""INSERT OR IGNORE INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES ('MangaDex', ?, ?)""",
                                         [(str(manga_id), chap.chapter_str) for chap in manga.chapters]):
            pass

    async def nyaasi_info(self, ctx: discord.ext.commands.Context, torrent_id: int, _get_name: bool = False, _info_only: bool = False):
        url = f"https://nyaa.si/view/{torrent_id}"
        async with self.bot.session.get(url) as request:
            request.raise_for_status()
            text = await request.text()
        torrent = NyaaTorrent.from_web_page(torrent_id, text)
        parsed_title = torrent.parse_title()
        if parsed_title is None:
            keylist = list(author_parser_mapping.keys())
            user_str = ", ".join(keylist[:-1]) + "or " + keylist[-1]
            raise discord.ext.commands.BadArgument(
                f"Torrent ID {torrent_id} is not a torrent owned by {user_str}. Torrents from other users are not supported.")
        if isinstance(parsed_title, BaseTitleParser):
            anime_name = parsed_title.name
            user = torrent.user
            if _get_name:
                return user, anime_name
        elif _get_name:
            return
        elif parsed_title is None:
            keylist = list(author_parser_mapping.keys())
            user_str = ", ".join(keylist[:-1]) + "or " + keylist[-1]
            error_str = f"Torrent ID `{torrent_id}` is not a torrent owned by {user_str}. Torrents from other users are not supported."
            return await ctx.send(embed=Embed(ctx, title="Invalid Torrent", description=error_str, color=discord.Color.red()))
        else:
            if len(parsed_title) == 1:
                message = f"Torrent ID {torrent_id} is a torrent owned by {parsed_title[0][0]} that has an invalid title."
                title = f"Error Determining Title of Torrent {torrent_id}"
            else:
                message = f"Torrent ID {torrent_id} is a torrent where ownership cannot be determined, due to multiple ownership calculators failing."
                title = f"Error Determining Ownership of Torrent {torrent_id}"
            message += "An issue has been logged and will be resolved by the bot author."
            issue_str = f"# Details:\n* Torrent #: {torrent_id}\n* Link: {ctx.message.jump_url}\n\n# Tracebacks:\n"
            for user, exception in parsed_title:
                issue_str += f"* Parser: {author_parser_mapping[user]} (for user [{user}](https://nyaa.si/user/{user})\n)"
                issue_str += "```python\n" + "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)) + "\n```"
            issue_num = await post_issue(self.bot.session, title, issue_str)
            embed = Embed(ctx, title=title, description=message, color=discord.Color.red())
            embed.add_field(name="Issue", value=f"[#{issue_num}](https://github.com/PythonCoderAS/PokestarBot/issues/{issue_num})")
            return await ctx.send(embed=embed)
        rss_link = search_string_builder(query=anime_name, user=user, category=NyaaCategoryTypes.Anime_ENG)
        async with self.bot.session.get(rss_link) as request:
            request.raise_for_status()
            text = await request.text()
        torrents = NyaaTorrentList.from_rss_feed(text)
        torrents.parse_titles(display_warnings=get_filter_level(logger))
        latest_episode = torrents.max_episode
        embed = Embed(ctx, title=anime_name)
        if not _info_only:
            embed.add_field(name="For User", value=ctx.author.mention)
            embed.add_field(name="Service", value="Nyaa.si")
            embed.add_field(name="Initial Torrent Link (for adding)", value=url)
        embed.add_field(name="Torrent Author", value=user)
        embed.add_field(name="Latest Episode", value=str(latest_episode))
        msg = await ctx.send(embed=embed)
        if _info_only:
            return
        await msg.add_reaction("✅")
        try:
            async with self.conn.execute("INSERT INTO NYAASI(NAME, USER_ID, GUILD_ID) VALUES (?, ?, ?)",
                                         [anime_name, ctx.author.id, getattr(ctx.guild, "id", None)]):
                pass
        except sqlite3.IntegrityError:
            logger.debug("Tried to insert duplicate info (name: %s)", anime_name, exc_info=True)
            embed = Embed(ctx, title="Anime Exists", description="The anime has been already added.", color=discord.Color.red())
            embed.add_field(name="Service", value="Nyaa.si")
            embed.add_field(name="Anime Name", value=anime_name)
            return await ctx.send(embed=embed)
        async with self.conn.executemany("""INSERT OR IGNORE INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES ('Nyaasi', ?, ?)""",
                                         [(anime_name, str(episode)) for episode in episodes]):
            pass

    @discord.ext.commands.group(brief="Manage the manga updates system.", invoke_without_command=True, usage="subcommand", aliases=["update"])
    async def updates(self, ctx: discord.ext.commands.Context):
        await self.bot.generic_help(ctx)

    @updates.command(brief="Add a manga to the updates", usage="url [url] [...]")
    async def add(self, ctx: discord.ext.commands.Context, *urls: str):
        await self.get_conn()
        if len(urls) == 0:
            embed = Embed(ctx, title="No URLs Specified",
                          description="You need to specify a valid URL. The different valid types of URLs are specified.", color=discord.Color.red())
            embed.add_field(name="Guya.moe", value="https://guya.moe/read/manga/<manga-name>")
            embed.add_field(name="MangaDex", value="https://mangadex.org/title/<manga-id>")
            embed.add_field(name="Nyaa.si", value="https://nyaa.si/view/<torrent-id>")
            return await ctx.send(embed=embed)
        for url in urls:
            if match := self.GUYAMOE_URL.match(url):
                slug = match.group(1)
                await self.guyamoe_info(ctx, slug)
            elif match := self.MANGADEX_URL.match(url):
                manga_id = int(match.group(1))
                await self.mangadex_info(ctx, manga_id)
            elif match := self.NYAASI_URL.match(url):
                torrent_id = int(match.group(1))
                await self.nyaasi_info(ctx, torrent_id)
            else:
                embed = Embed(ctx, title="Invalid URL",
                              description="The given URL is not recognized by the bot. Look at the supported services that are attached on this "
                                          "Embed.",
                              color=discord.Color.red())
                embed.add_field(name="Guya.moe", value="https://guya.moe/read/manga/<manga-name>")
                embed.add_field(name="MangaDex", value="https://mangadex.org/title/<manga-id>")
                embed.add_field(name="Nyaa.si", value="https://nyaa.si/view/<torrent-id>")
                await ctx.send(embed=embed)

    @updates.command(brief="Remove a manga from the updates", usage="url [url] [...]")
    async def remove(self, ctx: discord.ext.commands.Context, *urls: str):
        await self.get_conn()
        if len(urls) == 0:
            embed = Embed(ctx, title="No URLs Specified",
                          description="You need to specify a valid URL. The different valid types of URLs are specified.", color=discord.Color.red())
            embed.add_field(name="Guya.moe", value="https://guya.moe/read/manga/<manga-name>")
            embed.add_field(name="MangaDex", value="https://mangadex.org/title/<manga-id>")
            embed.add_field(name="Nyaa.si", value="https://nyaa.si/view/<torrent-id>")
            return await ctx.send(embed=embed)
        for url in urls:
            if match := self.GUYAMOE_URL.match(url):
                slug = match.group(1)
                async with self.conn.execute("""DELETE FROM GUYAMOE WHERE SLUG==? AND USER_ID==? AND GUILD_ID==?""",
                                             [slug, ctx.author.id, getattr(ctx.guild, "id", None)]):
                    pass
                # async with self.conn.execute("""DELETE FROM SEEN WHERE SERVICE=='Guyamoe' AND ITEM==?""", [slug]):
                # pass
                embed = Embed(ctx, color=discord.Color.green(), title="Manga Removed")
                embed.add_field(name="Service", value="Guya.moe")
                embed.add_field(name="Slug", value=slug)
                await ctx.send(embed=embed)
            elif match := self.MANGADEX_URL.match(url):
                manga_id = int(match.group(1))
                async with self.conn.execute("""DELETE FROM MANGADEX WHERE MANGA_ID==? AND USER_ID==? AND GUILD_ID==?""",
                                             [manga_id, ctx.author.id, getattr(ctx.guild, "id", None)]):
                    pass
                embed = Embed(ctx, color=discord.Color.green(), title="Manga Removed")
                embed.add_field(name="Service", value="MangaDex")
                embed.add_field(name="Manga ID", value=str(manga_id))
                await ctx.send(embed=embed)
            elif match := self.NYAASI_URL.match(url):
                torrent_id = int(match.group(1))
                user, name = await self.nyaasi_info(ctx, torrent_id, _get_name=True)
                async with self.conn.execute("""DELETE FROM NYAASI WHERE NAME==? AND USER_ID==? AND GUILD_ID==?""",
                                             [name, ctx.author.id, getattr(ctx.guild, "id", None)]):
                    pass
                embed = Embed(ctx, color=discord.Color.green(), title="Manga Removed")
                embed.add_field(name="Service", value="Nyaa.si")
                embed.add_field(name="Torrent Author", value=user)
                embed.add_field(name="Anime Name", value=name)
                await ctx.send(embed=embed)
            else:
                embed = Embed(ctx, title="Invalid URL",
                              description="The given URL is not recognized by the bot. Look at the supported services that are attached on this "
                                          "Embed.",
                              color=discord.Color.red())
                embed.add_field(name="Guya.moe", value="https://guya.moe/read/manga/<manga-name>")
                embed.add_field(name="MangaDex", value="https://mangadex.org/title/<manga-id>")
                embed.add_field(name="Nyaa.si", value="https://nyaa.si/view/<torrent-id>")
                await ctx.send(embed=embed)

    @updates.command(brief="List the current mangas that will give notifications", usage="[user]")
    async def list(self, ctx: discord.ext.commands.Context, user: Optional[discord.Member] = None):
        await self.get_conn()
        user_data = {}
        slug_data = {}
        embed = Embed(ctx, title="Mangas in Update List")
        fields = []
        async with self.conn.execute("""SELECT SLUG, NAME, USER_ID FROM GUYAMOE WHERE GUILD_ID==?""", [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        for slug, name, user_id in data:
            member = self.bot.get_user(ctx.guild, user_id)
            slug_data.setdefault(slug, name)
            members = user_data.setdefault(slug, [])
            members.append(member.mention)
        for slug in sorted(set(slug_data.keys())):
            if not user or user.mention in user_data[slug]:
                fields.append((slug_data[slug] + " [Guya.moe]", "\n".join((f"Link: https://guya.moe/read/manga/{slug}", ", ".join(user_data[slug])))))
        user_data = {}
        slug_data = {}
        async with self.conn.execute("""SELECT MANGA_ID, NAME, USER_ID FROM MANGADEX WHERE GUILD_ID==?""",
                                     [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        for slug, name, user_id in data:
            member: discord.Member = ctx.guild.get_member(user_id)
            slug_data.setdefault(slug, name)
            members = user_data.setdefault(slug, [])
            members.append(member.mention)
        for slug in sorted(set(slug_data.keys())):
            if not user or user.mention in user_data[slug]:
                fields.append((slug_data[slug] + " [MangaDex]", "\n".join((f"Link: https://mangadex.org/title/{slug}", ", ".join(user_data[slug])))))
        async with self.conn.execute("""SELECT NAME, USER_ID FROM NYAASI WHERE GUILD_ID==?""",
                                     [getattr(ctx.guild, "id", None)]) as cursor:
            data = await cursor.fetchall()
        user_data = {}
        for name, user_id in data:
            member: discord.Member = ctx.guild.get_member(user_id)
            members = user_data.setdefault(name, [])
            members.append(member.mention)
        for name in sorted(user_data.keys()):
            if not user or user.mention in user_data[name]:
                fields.append((f"{name} [Nyaa.si]", ", ".join(user_data[name])))
        await send_embeds_fields(ctx, embed, fields)

    async def guyamoe_update(self, slug: str, name: str):
        url = f"https://guya.moe/api/series/{slug}/"
        async with self.bot.session.get(url) as request:
            request.raise_for_status()
            json = await request.json()
        manga = GuyamoeManga.from_api(json)
        chaps = {str(float(key.num)) for key in manga.chapters}
        async with self.conn.execute("""SELECT CHAPTER FROM SEEN WHERE SERVICE==? AND ITEM==?""", ["Guyamoe", slug]) as cursor:
            data = await cursor.fetchall()
        seen_chaps = {chap for chap, in data}
        new_chaps = chaps - seen_chaps
        if len(new_chaps) > 0:
            logger.debug(str(new_chaps))
        async with self.conn.execute("""SELECT USER_ID, GUILD_ID FROM GUYAMOE WHERE SLUG==?""", [slug]) as cursor:
            data = await cursor.fetchall()
        for chap in sorted(new_chaps):
            num_chap = float(chap)
            int_chap = int(num_chap)
            if int_chap == num_chap:
                num_chap = int_chap
            logger.info("New Chapter: %s chapter %s", name, num_chap)
            link = f"https://guya.moe/read/manga/{slug}/{str(num_chap).replace('.', '-')}"
            embed = discord.Embed(color=discord.Color.green(), title="New Chapter")
            embed.set_footer(text=f"PokestarBot Version {bot_version}")
            embed.add_field(name="Service", value="Guya.moe")
            embed.add_field(name="Manga", value=name)
            embed.add_field(name="Chapter", value=str(num_chap))
            embed.add_field(name="Link", value=link)
            for user_id, guild_id in data:
                dest = self.bot.get_channel_data(guild_id, "anime-and-manga-updates")
                if dest is None:
                    continue
                user = self.bot.get_user(dest.guild, user_id)
                await dest.send(user.mention, embed=embed)
        async with self.conn.executemany("""INSERT INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES('Guyamoe', ?, ?)""",
                                         [(slug, chap) for chap in new_chaps]):
            pass

    async def mangadex_update(self, manga_id: int, name: str):
        url = f"https://mangadex.org/api/v2/manga/{manga_id}/chapters"
        async with self.bot.session.get(url) as request:
            request.raise_for_status()
            json = await request.json()
        chapters = MangadexChapterList.from_chapter_list_v2(json).filter_lang().filter_duplicates()
        async with self.conn.execute("""SELECT CHAPTER FROM SEEN WHERE SERVICE==? AND ITEM==?""", ["MangaDex", str(manga_id)]) as cursor:
            data = await cursor.fetchall()
        chap_map = {chap.chapter_str: chap.id for chap in chapters}
        seen_chaps = {chap for chap, in data}
        new_chaps = set(chap_map.keys()) - seen_chaps
        if len(new_chaps) > 0:
            logger.debug(str(new_chaps))
        async with self.conn.execute("""SELECT USER_ID, GUILD_ID FROM MANGADEX WHERE MANGA_ID==?""", [manga_id]) as cursor:
            data = await cursor.fetchall()
        for chap in sorted(new_chaps):
            logger.info("New Chapter: %s chapter %s", name, chap)
            chap_id = chap_map[chap]
            link = f"https://mangadex.org/chapter/{chap_id}/"
            embed = discord.Embed(color=discord.Color.green(), title="New Chapter")
            embed.set_footer(text=f"PokestarBot Version {bot_version}")
            embed.add_field(name="Service", value="MangaDex")
            embed.add_field(name="Manga", value=name)
            embed.add_field(name="Chapter", value=chap)
            embed.add_field(name="Link", value=link)
            for user_id, guild_id in data:
                dest = self.bot.get_channel_data(guild_id, "anime-and-manga-updates")
                if dest is None:
                    continue
                user = self.bot.get_user(dest.guild, user_id)
                await dest.send(user.mention, embed=embed)
        async with self.conn.executemany("""INSERT INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES('MangaDex', ?, ?)""",
                                         [(str(manga_id), chap) for chap in new_chaps]):
            pass

    async def nyaasi_update(self, anime_name: str):
        rss_link = search_string_builder(query=anime_name, category=NyaaCategoryTypes.Anime_ENG)
        async with self.bot.session.get(rss_link) as request:
            request.raise_for_status()
            text = await request.text()
        async with self.conn.execute("""SELECT ID FROM NYAASI_SEEN""") as cursor:
            ids = [id async for id, in cursor]
        torrents = NyaaTorrentList.from_rss_feed(text).filter_ids(*ids)
        torrents.parse_titles(display_warnings=get_filter_level(logger))
        filtered = torrents.filter_resolution(1080)
        async with self.conn.executemany("""INSERT INTO NYAASI_SEEN(ID) VALUES (?)""", [[torrent.id] for torrent in torrents]):
            pass
        async with self.conn.execute("""SELECT CHAPTER FROM SEEN WHERE SERVICE==? AND ITEM==?""", ["Nyaasi", anime_name]) as cursor:
            data = await cursor.fetchall()
        seen_eps = {int(ep) for ep, in data}
        new_eps = filtered.episodes - seen_eps
        if len(new_eps) > 0:
            logger.debug(str(new_eps))
        async with self.conn.execute("""SELECT USER_ID, GUILD_ID FROM NYAASI WHERE NAME==?""", [anime_name]) as cursor:
            data = await cursor.fetchall()
        for ep in sorted(new_eps):
            logger.info("New Episode: %s episode %s", anime_name, ep)
            ep_torrent: NyaaTorrent = filtered.episode_mapping[ep]
            embed = discord.Embed(color=discord.Color.green(), title="New Episode")
            embed.set_footer(text=f"PokestarBot Version {bot_version}")
            embed.add_field(name="Service", value="Nyaa.si")
            embed.add_field(name="Torrent Author", value=ep_torrent.user)
            embed.add_field(name="Anime", value=anime_name)
            embed.add_field(name="Episode #", value=str(ep))
            embed.add_field(name="Link", value=ep_torrent.download_link)
            embed.add_field(name="Search Page",
                            value=search_string_builder(query=anime_name, user=ep_torrent.user, category=NyaaCategoryTypes.Anime_ENG, rss=False))
            for user_id, guild_id in data:
                dest = self.bot.get_channel_data(guild_id, "anime-and-manga-updates")
                if dest is None:
                    continue
                user = self.bot.get_user(dest.guild, user_id)
                await dest.send(user.mention, embed=embed)
        async with self.conn.executemany("""INSERT OR IGNORE INTO SEEN(SERVICE, ITEM, CHAPTER) VALUES ('Nyaasi', ?, ?)""",
                                         [(anime_name, str(episode)) for episode in filtered.episodes]):
            pass

    @discord.ext.commands.command(brief="Get information on a manga on Guya.moe", usage="url [url] [...]", aliases=["guya.moe"],
                                  not_channel_locked=True)
    async def guyamoe(self, ctx: discord.ext.commands.Context, *urls: str, _on_message: bool = False):
        if len(urls) == 0:
            self.bot.missing_argument("url")
        for url in urls:
            if match := self.GUYAMOE_URL.match(url):
                if _on_message:
                    if re.search(r"/[0-9]+/?$", url):
                        continue
                slug = match.group(1)
                await self.guyamoe_info(ctx, slug, _info_only=True)
            else:
                embed = Embed(ctx, title="Invalid URL", description="The provided URL is invalid.", color=discord.Color.red())
                embed.add_field(name="Provided URL", value=url)
                embed.add_field(name="Valid URL", value="https://guya.moe/read/manga/<manga-name>")
                await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Get information on a manga on MangaDex", usage="url [url] [...]", not_channel_locked=True)
    async def mangadex(self, ctx: discord.ext.commands.Context, *urls: str):
        if len(urls) == 0:
            self.bot.missing_argument("url")
        for url in urls:
            if match := self.MANGADEX_URL.match(url):
                manga_id = int(match.group(1))
                await self.mangadex_info(ctx, manga_id, _info_only=True)
            else:
                embed = Embed(ctx, title="Invalid URL", description="The provided URL is invalid.", color=discord.Color.red())
                embed.add_field(name="Provided URL", value=url)
                embed.add_field(name="Valid URL", value="https://mangadex.org/title/<manga-id>")
                await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Get information on an anime provided by HorribleSubs on nyaa.si", usage="url [url] [...]",
                                  aliases=["nyaa.si"], not_channel_locked=True)
    async def nyaasi(self, ctx: discord.ext.commands.Context, *urls: str):
        if len(urls) == 0:
            self.bot.missing_argument("url")
        for url in urls:
            if match := self.NYAASI_URL.match(url):
                torrent_id = int(match.group(1))
                await self.nyaasi_info(ctx, torrent_id, _info_only=True)
            else:
                embed = Embed(ctx, title="Invalid URL", description="The provided URL is invalid.", color=discord.Color.red())
                embed.add_field(name="Provided URL", value=url)
                embed.add_field(name="Valid URL", value="https://nyaa.si/view/<torrent-id>")
                await ctx.send(embed=embed)

    @discord.ext.tasks.loop(minutes=5)
    async def check_for_updates(self):
        await self.get_conn()
        await self.bot.load_session()
        async with self.conn.execute("""SELECT DISTINCT SLUG, NAME FROM GUYAMOE WHERE COMPLETED==?""", [False]) as cursor:
            guyamoe = await cursor.fetchall()
        for slug, name in guyamoe:
            if "GUYAMOE" + slug in self.checked_for:
                continue
            try:
                await self.guyamoe_update(slug, name)
            except:
                raise
            else:
                self.checked_for.append("GUYAMOE" + slug)
        async with self.conn.execute("""SELECT DISTINCT MANGA_ID, NAME FROM MANGADEX WHERE COMPLETED==?""", [False]) as cursor:
            mangadex = await cursor.fetchall()
        for manga_id, name in mangadex:
            if "MANGADEX" + str(manga_id) in self.checked_for:
                continue
            try:
                await self.mangadex_update(manga_id, name)
            except:
                raise
            else:
                self.checked_for.append("MANGADEX" + str(manga_id))
        async with self.conn.execute("""SELECT DISTINCT NAME FROM NYAASI WHERE COMPLETED==?""", [False]) as cursor:
            nyaasi = await cursor.fetchall()
        for anime_name, in nyaasi:
            if "NYAASI" + anime_name in self.checked_for:
                continue
            try:
                await self.nyaasi_update(anime_name)
            except:
                raise
            else:
                self.checked_for.append("NYAASI" + anime_name)
        self.checked_for = []

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    @check_for_updates.error
    async def on_check_for_updates_error(self, exception: BaseException):
        await self.bot.on_error("check_for_updates")

    @loop_command_deco(check_for_updates)
    @updates.group(brief="Get the update loop statistics", aliases=["updateloop", "update_loop"], invoke_without_command=True)
    async def loop(self, ctx: discord.ext.commands.Context):
        await self.bot.loop_stats(ctx, self.check_for_updates, "Check For Updates")

    async def on_reaction(self, msg: discord.Message, emoji: Union[discord.PartialEmoji, discord.Emoji], user: discord.Member):
        if user.id == self.bot.user.id or user.bot or msg.author.id != self.bot.user.id or not msg.embeds or not msg.embeds[0].title:
            return
        embed: discord.Embed = msg.embeds[0]
        ctx: CustomContext = await self.bot.get_context(msg, cls=CustomContext)
        ctx.author = user
        if len(embed.fields) > 1:
            val = embed.fields[1].value
            if val == "Guya.moe":
                if embed.title == "Manga Removed":
                    if "✅" in str(emoji):
                        pass
                    elif "🚫" in str(emoji):
                        pass
                else:
                    if "✅" in str(emoji):
                        link = embed.fields[2].value
                        await self.add.fully_run_command(ctx, link)
                    elif "🚫" in str(emoji):
                        pass
            elif val == "MangaDex":
                if embed.title == "Manga Removed":
                    if "✅" in str(emoji):
                        pass
                    elif "🚫" in str(emoji):
                        pass
                else:
                    if "✅" in str(emoji):
                        link = embed.fields[2].value
                        await self.add.fully_run_command(ctx, link)
                    elif "🚫" in str(emoji):
                        pass
            elif val == "Nyaa.si":
                if embed.title == "Manga Removed":
                    if "✅" in str(emoji):
                        pass
                    elif "🚫" in str(emoji):
                        pass
                else:
                    if "✅" in str(emoji):
                        link = embed.fields[3].value
                        await self.add.fully_run_command(ctx, link)
                    elif "🚫" in str(emoji):
                        pass

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot and message.content and not message.content.startswith(self.bot.command_prefix):
            if getattr(message, "guild", None):
                if not message.channel.permissions_for(message.guild.get_member(self.bot.user.id)).send_messages:
                    return
            if self.bot.get_option(getattr(getattr(message, "guild", None), "id", None), "mangadex", allow_dm=True):
                mdex = self.MANGADEX_URL.findall(message.content)
            else:
                mdex = []
            if self.bot.get_option(getattr(getattr(message, "guild", None), "id", None), "guyamoe", allow_dm=True):
                guya = self.GUYAMOE_URL.findall(message.content)
            else:
                guya = []
            if self.bot.get_option(getattr(getattr(message, "guild", None), "id", None), "nyaasi", allow_dm=True):
                nyaa = self.NYAASI_URL.findall(message.content)
            else:
                nyaa = []
            if mdex or guya or nyaa:
                ctx = self.bot.get_context(message)
                for item in mdex:
                    try:
                        await self.mangadex(ctx, item)
                    except Exception:
                        pass
                for item in guya:
                    try:
                        await self.guyamoe(ctx, item)
                    except Exception:
                        pass
                for item in nyaa:
                    try:
                        await self.nyaasi(ctx, item)
                    except Exception:
                        pass
            else:
                return


def setup(bot: "PokestarBot"):
    bot.add_cog(Updates(bot))
    logger.info("Loaded the Updates extension.")


def teardown(bot: "PokestarBot"):
    cog: Updates = bot.cogs["Updates"]
    asyncio.gather(cog.conn.close())
    logger.warning("Unloading the Updates extension.")
