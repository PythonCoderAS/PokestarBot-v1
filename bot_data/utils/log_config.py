import inspect
import logging
from typing import Union

import discord.ext.commands

from .data.nyaasi import NyaaTitleParseWarningLevel
from .get_message import get_context_variables

logger = logging.getLogger(__name__)


class UserChannelFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("[%(asctime)s] {%(module)s::%(funcName)s} {%(user)s::%(channel)s::%(command)s::%(messageid)s} (%(levelname)s): %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        user, channel, command, message, _ = get_context_variables(break_on_message=False)
        record.user = user
        record.channel = channel
        record.command = command
        record.messageid = message.id if message else None
        return super().format(record)


class CommandFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("[%(asctime)s] {%(user)s::%(url)s} [%(command)s]: %(argument)s")

    def format(self, record: logging.LogRecord) -> str:
        assert hasattr(record, "ctx"), "Record needs to have `ctx` to properly log."
        ctx: discord.ext.commands.Context = record.ctx
        record.url = ctx.message.jump_url
        record.user = ctx.author
        record.command = ctx.command
        record.argument = (ctx.message.content or "").lstrip(ctx.bot.command_prefix).lstrip(record.command.qualified_name).lstrip() or "No Arguments"
        return super().format(record)


class ShutdownStatusFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> Union[bool, int]:
        """Filters out the bot shutdown messages, which are not unexpected behavior."""
        if record.message in ["Started bot shutdown.", "Killing the bot with signal SIGINT."]:
            return False
        return super().filter(record)


def get_filter_level(logger: logging.Logger):
    if logger.level == logging.DEBUG:
        return NyaaTitleParseWarningLevel.ALL
    else:
        return NyaaTitleParseWarningLevel.EXCEPTION
