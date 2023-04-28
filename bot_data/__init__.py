import datetime
import logging.handlers
import os
import tarfile

import psutil
import pytz

from .const import bot_version
from .utils import CommandFormatter, UserChannelFormatter

NY = pytz.timezone("America/New_York")

logger = logging.getLogger(__name__)
command_logger = logging.getLogger("bot_command_log")

base = os.path.abspath(os.path.join(__file__, "..", "..", "logs"))
os.makedirs(base, exist_ok=True)

if not os.getenv("NO_DELETE_LOGFILES", ""):
    backup_path = os.path.join(base, "logs-" + datetime.datetime.now().astimezone(NY).strftime("%Y-%m-%d-%H-%M-%S"))
    tf = tarfile.open(backup_path + ".tar.bz2", mode="w:bz2")
    for file in (os.path.join(base, logfile) for logfile in ("bot.log", "commands.log")):
        if os.path.exists(file):
            tf.add(file)
            os.remove(file)
    if os.path.exists(os.path.join(base, "log.log")):
        tf.add(os.path.join(base, "log.log"))
        os.remove(os.path.join(base, "log.log"))
        open(os.path.join(base, "log.log"), "w").close()

level = os.getenv("LOG_LEVEL", "INFO")
log_level = getattr(logging, level)
logger.setLevel(log_level)
command_logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(os.path.join(base, "bot.log"), encoding="utf-8", maxBytes=10 * (1024 ** 2))
handler2 = logging.FileHandler(os.path.join(base, "commands.log"), encoding="utf-8")
formatter = UserChannelFormatter()
formatter2 = CommandFormatter()
handler.setFormatter(formatter)
handler.setLevel(log_level)
handler2.setFormatter(formatter2)
handler2.setLevel(log_level)
logger.addHandler(handler)
command_logger.addHandler(handler2)
if not os.getenv("NO_DELETE_LOGFILES", ""):
    proc = psutil.Process().parent()
    if proc is None:
        logger.warning("Could not determine parent process.")
    else:
        with proc.oneshot():
            logger.info("Logging system started by %s (PID %s)", proc.name(), proc.pid)
    logger.info("Logging at level %s", level)
logging.captureWarnings(True)

aiosqlite_logger = logging.getLogger("aiosqlite")
aiosqlite_logger.handlers = []
aiosqlite_logger.addHandler(logging.NullHandler())

discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)
discord_logger.addHandler(handler)
