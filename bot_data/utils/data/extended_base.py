from typing import Optional, TYPE_CHECKING

import aiosqlite

from .base import BaseDataClass

if TYPE_CHECKING:
    from ...bot import PokestarBot


class SQLBaseDataClass(BaseDataClass):
    __slots__ = ("_connection",)

    connection: Optional[aiosqlite.Connection]

    @property
    def connection(self):
        if self._connection:
            return self._connection
        else:
            raise AttributeError("Connection attribute not defined yet.")

    conn = connection





class BotBaseDataClass(SQLBaseDataClass):
    bot: Optional["PokestarBot"] = None

    @classmethod
    def set_bot(cls, bot: "PokestarBot"):
        cls.bot = bot

    @property
    def _connection(self):
        return self.bot.conn

    def __init__(self, **data):
        if self.bot is None:
            raise ValueError("Bot attribute has to be set.")
        super().__init__(**data)



