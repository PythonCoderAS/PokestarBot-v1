import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


def setup(bot: "PokestarBot"):
    bot.load_extension('jishaku')
    logger.info("Loaded the jishaku extension.")


def teardown(_bot: "PokestarBot"):
    bot.unload_extension('jishaku')
    logger.warning("Unloading the jishaku extension.")
