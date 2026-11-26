# ==============================================================================
# config.py - Configuration
# ==============================================================================
# Pulls in all environment variables and sets defaults.
# Don't commit your .env file!
# ==============================================================================

from os import getenv
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):

        # TELEGRAM API CREDENTIALS
        self.API_ID: int = int(getenv("API_ID", "0"))
        self.API_HASH: str = getenv("API_HASH", "")

        # BOT CONFIGURATION
        self.BOT_TOKEN: str = getenv("BOT_TOKEN", "")
        self.LOGGER_ID: int = int(getenv("LOGGER_ID", "0"))
        self.OWNER_ID: int = int(getenv("OWNER_ID", "0"))

        # DATABASE CONFIGURATION
        self.MONGO_URL: str = getenv("MONGO_DB_URI", "")

        # MUSIC BOT LIMITS
        self.DURATION_LIMIT: int = int(getenv("DURATION_LIMIT", "300")) * 60
        self.QUEUE_LIMIT: int = int(getenv("QUEUE_LIMIT", "30"))
        self.PLAYLIST_LIMIT: int = int(getenv("PLAYLIST_LIMIT", "20"))
        # Max total songs to autoload from a playlist (default: 60)
        self.PLAYLIST_MAX: int = int(getenv("PLAYLIST_MAX", "60"))

        # ============ SPOTIFY API (Optional) ============
        # Spotify API credentials from https://developer.spotify.com/dashboard
        self.SPOTIFY_CLIENT_ID: str = getenv("SPOTIFY_CLIENT_ID") or getenv("SPOTIPY_CLIENT_ID", "")
        self.SPOTIFY_CLIENT_SECRET: str = getenv("SPOTIFY_CLIENT_SECRET") or getenv("SPOTIPY_CLIENT_SECRET", "")

        # ASSISTANT SESSIONS
        # required at least one
        self.SESSION1: str = getenv("STRING_SESSION", "")
        self.SESSION2: str = getenv("STRING_SESSION2", "")
        self.SESSION3: str = getenv("STRING_SESSION3", "")

        # SUPPORT LINKS
        self.SUPPORT_CHANNEL: str = getenv(
            "SUPPORT_CHANNEL", "https://t.me/hasiimusic")
        self.SUPPORT_CHAT: str = getenv("SUPPORT_CHAT", "https://t.me/TheInfinityAI")

        # EXCLUDED CHATS
        self.EXCLUDED_CHATS: List[int] = self._parse_excluded_chats()

        # FEATURE FLAGS
        self.QUEUE_END_MESSAGE: bool = self._str_to_bool(getenv("QUEUE_END_MESSAGE", "False"))
        self.AUTO_LEAVE: bool = self._str_to_bool(getenv("AUTO_LEAVE", "False"))
        self.THUMB_GEN: bool = self._str_to_bool(getenv("THUMB_GEN", "True"))

        self.VIDEO_MAX_HEIGHT: int = self._parse_video_height()

        # YOUTUBE COOKIES
        self.COOKIES_URL: List[str] = self._parse_cookies()

        # YOUTUBE ANTI-BOT
        # Proxy for all yt-dlp traffic, e.g. socks5://warp:1080 (Cloudflare WARP)
        self.YT_PROXY: str = getenv("YT_PROXY", "").strip()
        # bgutil PO token provider server, e.g. http://bgutil-provider:4416
        self.POT_PROVIDER_URL: str = getenv("POT_PROVIDER_URL", "").strip()

        # IMAGE URLS
        self.DEFAULT_THUMB: str = getenv(
            "DEFAULT_THUMB",
            "https://files.catbox.moe/kgrs8f.png"  # Default thumbnail
        )
        self.PING_IMG: str = getenv(
            "PING_IMG", "https://files.catbox.moe/djilyq.png")    # Ping command image
        self.START_IMG: str = getenv(
            "START_IMG", "https://files.catbox.moe/7jihmf.png")  # Start command image
        self.RADIO_IMG: str = getenv(
            "RADIO_IMG", "https://files.catbox.moe/t03fzk.png")    # Radio command image

        # MODERATION
        self.EXCLUDED_USERNAMES: List[str] = getenv("EXCLUDED_USERNAMES", "").split()

    def _parse_video_height(self) -> int:
        """Clamp configured video height to a safe range."""
        default_height = 480
        raw_value = getenv("VIDEO_MAX_HEIGHT", str(default_height))
        try:
            height = int(raw_value)
        except (TypeError, ValueError):
            return default_height

        # Allow disabling the cap by setting to 0 or negative (interpreted as unlimited)
        if height <= 0:
            return 0

        # Clamp between 360p and 1080p
        return max(360, min(height, 1080))

    def _parse_excluded_chats(self) -> List[int]:
        excluded = getenv("EXCLUDED_CHATS", "")
        if not excluded:
            return []

        chat_ids = []
        for chat_id in excluded.split(","):
            chat_id = chat_id.strip()
            if chat_id.lstrip('-').isdigit():
                chat_ids.append(int(chat_id))
        return chat_ids

    def _parse_cookies(self) -> List[str]:
        cookie_str = getenv("COOKIE_URL", "")
        if not cookie_str:
            return []

        valid_sources = ["batbin.me", "pastebin.com", "paste.ee", "rentry.co"]
        return [
            url.strip()
            for url in cookie_str.split()
            if url.strip() and any(source in url for source in valid_sources)
        ]

    @staticmethod
    def _str_to_bool(value: str) -> bool:
        return value.lower() in ("true", "1", "yes", "y", "on")

    def check(self) -> None:
        required_vars = {
            "API_ID": self.API_ID,
            "API_HASH": self.API_HASH,
            "BOT_TOKEN": self.BOT_TOKEN,
            "MONGO_DB_URI": self.MONGO_URL,
            "LOGGER_ID": self.LOGGER_ID,
            "OWNER_ID": self.OWNER_ID,
            "STRING_SESSION": self.SESSION1,
        }

        missing = [
            name for name, value in required_vars.items()
            if not value or (isinstance(value, int) and value == 0)
        ]

        if missing:
            raise SystemExit(
                f"❌ Missing required environment variables: {', '.join(missing)}\n"
                f"Please check your .env file and ensure all required variables are set."
            )
