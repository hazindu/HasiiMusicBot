# ==============================================================================
# cookies.py - YouTube Cookies Manager
# ==============================================================================
# This file manages the downloading and loading of YouTube cookies.
# Features:
# - Downloads cookies from an external raw URL
# - Caches and randomizes cookies for requests
# ==============================================================================

import os
import random
from urllib.parse import urlparse

import aiohttp
from HasiiMusic import logger

class CookieManager:
    def __init__(self):
        self.cookies = []  # List of available cookie files
        self.checked = False  # Whether cookies directory has been checked
        self.warned = False  # Whether missing cookies warning has been shown

    def get_cookies(self):
        if not self.checked:
            if os.path.exists("HasiiMusic/cookies"):
                for file in os.listdir("HasiiMusic/cookies"):
                    if file.endswith(".txt"):
                        self.cookies.append(file)
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return f"HasiiMusic/cookies/{random.choice(self.cookies)}"

    @staticmethod
    def raw_url(url: str) -> str:
        # Convert a paste link into the URL that serves its raw content
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().removeprefix("www.")
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            return url

        if host in ("batbin.me", "pastebin.com"):
            # batbin.me/<id> or batbin.me/raw/<id>
            return f"https://{host}/raw/{parts[-1]}"
        if host == "paste.ee":
            # paste.ee/p/<id> or paste.ee/r/<id>
            return f"https://paste.ee/r/{parts[-1]}"
        if host == "rentry.co":
            # rentry.co/<id> or rentry.co/<id>/raw
            return f"https://rentry.co/{parts[0]}/raw"
        return url

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("🍪 Saving cookies from urls...")
        saved_count = 0
        os.makedirs("HasiiMusic/cookies", exist_ok=True)
        for url in urls:
            try:
                path = f"HasiiMusic/cookies/cookie{random.randint(10000, 99999)}.txt"
                link = self.raw_url(url)
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status != 200:
                            logger.error(f"❌ Cookie download failed: HTTP {resp.status} from {url}")
                            continue
                        content = await resp.read()
                        if not content or len(content) < 50:
                            logger.error(f"❌ Cookie file empty or invalid from {url}")
                            continue
                        with open(path, "wb") as fw:
                            fw.write(content)
                        if os.path.exists(path) and os.path.getsize(path) > 0:
                            saved_count += 1
                            # Update cookie list
                            cookie_filename = os.path.basename(path)
                            if cookie_filename not in self.cookies:
                                self.cookies.append(cookie_filename)
                            logger.info(f"✅ Saved: {cookie_filename} ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"❌ Cookie download error from {url}: {e}")
        
        # Refresh cookie list
        self.checked = True
        
        if saved_count > 0:
            logger.info(f"✅ Cookies saved. ({saved_count} file(s))")
        else:
            logger.error("❌ No cookies saved! Check COOKIE_URL in .env. YouTube downloads will fail!")
