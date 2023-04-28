import logging
from typing import TYPE_CHECKING

import discord.ext.commands

from . import PokestarBotCog
from ..const import MAL_ANIME_FIELDS, MAL_API_PATH, MAL_HEADERS
from ..converters import MALAnimeConverter
from ..creds import mal_client_id, mal_client_secret, mal_refresh_token
from ..utils import HubContext

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class MAL(PokestarBotCog):

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.access_token = None

    async def auth_again(self, ctx: HubContext):
        url = ""
        data = {"client_id": mal_client_id, "client_secret": mal_client_secret, "grant_type": "refresh_token", "refresh_token": mal_refresh_token}
        ctx.hub.add_breadcrumb(category="HTTP", message=f"Making request to {url!r}", data=data)
        async with self.bot.session.post(url, data=data) as request:
            request.raise_for_status()
            self.access_token = (await request.json())["access_token"]

    async def do_request(self, ctx: HubContext, path: str, params: dict = None, data: dict = None):
        if self.access_token is None:
            await self.auth_again(ctx)
        url = MAL_API_PATH + path
        ctx.hub.add_breadcrumb(category="HTTP", message=f"Making request to {url!r}", data={**data, "params": params})
        async with self.bot.session.get(url, headers=MAL_HEADERS + {"Authorization": f"Bearer {self.access_token}"}, params=params,
                                        data=data) as request:
            if request.status == 401:
                self.access_token = None
                return await self.do_request(path, params, data)
            request.raise_for_status()
            json = await request.json()
        return json

    async def get_anime(self, ctx: HubContext, anime_id: int):
        return await self.do_request(ctx, f"/anime/{anime_id}", params={"fields": ",".join(MAL_ANIME_FIELDS)})

    @discord.ext.commands.command(brief="Get information on a MAL anime", usage="anime_id_or_url [anime_id_or_url] [...]")
    async def anime(self, ctx: HubContext, *anime_id_or_urls: MALAnimeConverter):
        if len(anime_id_or_urls) == 0:
            self.bot.missing_argument("anime_id_or_url")
        for anime_id in anime_id_or_urls:
            anime_id: int
            data = await self.get_anime(ctx, anime_id)
            title = data["title"]
            description = data["synopsis"]
            image = data["main_picture"]["large"]
            alternatives = data["alternative_titles"]["synonyms"] + [data["alternative_titles"]["en"], data["alternative_titles"]["ja"]]
            start = data["start_date"] or "Unknown"
            end = data["end_date"] or ("Currently Airing" if start != "Unknown" else "Unknown")
            dates = f"Start: {start} • Ends: {end}"
            rating = data["mean"]
            rank = data["rank"]
            popularity = data["popularity"]
            ranking_str = f"Rank: {rank} • Popularity: {popularity}"
            list_users = data["num_list_users"]
            scoring_users = data["num_scoring_users"]
            users = f"Anime Added to {list_users} Lists • {scoring_users} Scoring"
            nsfw = data["nsfw"].lower() != "white"
            status = data["status"]
            episodes = data["num_episodes"]
            duration = str(data["average_episode_duration"] // 60) + " minutes"


def setup(bot: "PokestarBot"):
    bot.add_cog(MAL(bot))
    logger.info("Loaded the MAL extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the MAL extension.")
