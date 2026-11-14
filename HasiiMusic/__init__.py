# ==============================================================================
# ˹ʜᴀꜱɪɪ ᴍᴜꜱɪᴄ˼ Core Initialization
# ==============================================================================
# Sets up logging, config, and instantiates the main singleton objects (db, bot, etc.)
# ==============================================================================

import asyncio
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import List
from pyrogram.errors import ChannelInvalid

# Configure logging
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logging.getLogger("spotipy").setLevel(logging.CRITICAL)
logging.getLogger("spotipy.client").setLevel(logging.CRITICAL)

logger = logging.getLogger("HasiiMusic")


def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    exc = context.get("exception")
    if isinstance(exc, ChannelInvalid):
        logger.warning("Ignoring CHANNEL_INVALID update (channel probably removed).")
        return
    loop.default_exception_handler(context)


def configure_asyncio_exception_handler() -> None:
    asyncio.get_running_loop().set_exception_handler(_asyncio_exception_handler)

# Version
__version__ = "3.0.1"

# Load configuration
from config import Config

config = Config()
config.check()

# Global task list for background tasks
tasks: List = []
boot: float = time.time()

# Initialize bot client
from HasiiMusic.core.bot import Bot
app = Bot()

# Ensure required directories exist
from HasiiMusic.core.dir import ensure_dirs
ensure_dirs()

# Initialize userbot/assistant clients
from HasiiMusic.core.userbot import Userbot
userbot = Userbot()

# Initialize database connection
from HasiiMusic.core.mongo import MongoDB
db = MongoDB()

# Initialize language system
from HasiiMusic.core.lang import Language
lang = Language()

# Initialize Telegram, YouTube, and Spotify utilities
from HasiiMusic.core.telegram import Telegram
from HasiiMusic.core.youtube import YouTube
from HasiiMusic.core.spotify import Spotify
tg = Telegram()
yt = YouTube()
spotify = Spotify()

# Initialize preload manager for background track downloading
from HasiiMusic.core.preload import PreloadManager
preload = PreloadManager()

# Initialize queue manager
from HasiiMusic.helpers import Queue
queue = Queue()

# Initialize call handler
from HasiiMusic.core.calls import TgCall
tune = TgCall()


async def stop() -> None:
    logger.info("🛑 Stopping bot...")
    
    # Cancel all background tasks
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # Expected when cancelling tasks - suppress the error
            pass
        except Exception:
            pass
    
    # Close all connections
    await app.exit()
    await userbot.exit()
    await db.close()
    
    logger.info("✅ Bot stopped successfully.\n")
