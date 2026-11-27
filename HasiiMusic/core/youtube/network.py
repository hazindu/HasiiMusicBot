# ==============================================================================
# network.py - Shared yt-dlp network options
# ==============================================================================
# Every yt-dlp call merges these options so YouTube traffic goes through
# the configured proxy (e.g. Cloudflare WARP) and uses the bgutil PO token
# provider. Both are optional and controlled from .env:
#   YT_PROXY=socks5://127.0.0.1:1080
#   POT_PROVIDER_URL=http://127.0.0.1:4416
# ==============================================================================

import re
import time
from urllib.parse import urlsplit

import aiohttp

from HasiiMusic import config, logger


def mask_proxy(url: str) -> str:
    # Hide proxy credentials before logging (logs can be sent with /logs)
    parts = urlsplit(url)
    if parts.password:
        return url.replace(parts.password, "****")
    return url


class _YtdlpLogger:
    # yt-dlp otherwise stays quiet. Warnings that explain YouTube blocks
    # (PO token, cookies, proxy, JS challenge) are passed to the bot log,
    # each distinct message at most once every 10 minutes.
    _KEYWORDS = ("po token", "[pot", "bgutil", "cookies", "proxy", "javascript", "js runtime", "challenge")
    _VIDEO_PREFIX = re.compile(r"\[youtube\] [A-Za-z0-9_-]{11}: ")
    _REPEAT_SECONDS = 600

    def __init__(self):
        self._seen: dict[str, float] = {}

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def error(self, msg):
        # Errors are raised as exceptions and logged by the caller
        pass

    def warning(self, msg):
        low = msg.lower()
        if not any(k in low for k in self._KEYWORDS):
            return
        key = self._VIDEO_PREFIX.sub("", msg)
        now = time.monotonic()
        if now - self._seen.get(key, -self._REPEAT_SECONDS) < self._REPEAT_SECONDS:
            return
        if len(self._seen) > 200:
            self._seen.clear()
        self._seen[key] = now
        logger.warning(f"yt-dlp: {msg}")


_YTDLP_LOGGER = _YtdlpLogger()


def ytdlp_network_opts() -> dict:
    # Let yt-dlp fetch YouTube's JS challenge solver (run with deno) from
    # yt-dlp's GitHub if the installed yt-dlp-ejs package is missing/outdated.
    opts: dict = {"remote_components": ["ejs:github"], "logger": _YTDLP_LOGGER}
    if config.YT_PROXY:
        opts["proxy"] = config.YT_PROXY
    if config.POT_PROVIDER_URL:
        # Read by the bgutil-ytdlp-pot-provider plugin. Without this the
        # plugin still tries its default http://127.0.0.1:4416.
        opts["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [config.POT_PROVIDER_URL]},
        }
    return opts


async def check_pot_provider() -> None:
    # Startup check: ask the PO token server for a real token through the
    # same proxy yt-dlp uses. The server makes its own requests through that
    # proxy, so it must be able to reach the proxy address too.
    if not config.POT_PROVIDER_URL:
        return
    base = config.POT_PROVIDER_URL.rstrip("/")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base}/ping", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ PO token provider returned HTTP {resp.status} on /ping")
                    return
            async with session.post(
                f"{base}/get_pot",
                json={"proxy": config.YT_PROXY or None},
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                status = resp.status
                data = await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"⚠️ PO token provider not reachable at {base}: {type(e).__name__}: {e}")
        return

    if status == 200 and isinstance(data, dict) and data.get("poToken"):
        logger.info("🛡️ PO token provider working (test token generated).")
    else:
        error = str(data.get("error") if isinstance(data, dict) else data).rstrip(".")
        logger.warning(
            f"⚠️ PO token provider can't generate tokens (HTTP {status}): {error}. "
            "If it runs in Docker and YT_PROXY points at 127.0.0.1, start it with --net=host."
        )
