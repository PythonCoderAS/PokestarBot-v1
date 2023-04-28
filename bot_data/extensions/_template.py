import logging
from typing import TYPE_CHECKING

import discord.ext.commands
from ..utils import HubContext

from . import PokestarBotCog

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class CogName(PokestarBotCog):

    @discord.ext.commands.command(brief="Simple command")
    async def simple_command(self, ctx: HubContext):
        pass


def setup(bot: "PokestarBot"):
    bot.add_cog(CogName(bot))
    logger.info("Loaded the CogName extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the CogName extension.")
