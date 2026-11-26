# ==============================================================================
# search.py - YouTube Search Manager
# ==============================================================================
# This file handles querying metadata from YouTube.
# Features:
# - Searches and reads playlists with py-yt-search (YouTube's search page),
#   which does not hit the player API and so doesn't trip the
#   "Sign in to confirm you're not a bot" check
# - Falls back to yt-dlp only when py-yt-search can't answer
# - Maintains a short-lived search cache for rapid lookups
# ==============================================================================

import re
import asyncio
from dataclasses import replace

import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch

from HasiiMusic import logger
from HasiiMusic.helpers import Track, utils
from .network import ytdlp_network_opts

# Video ID inside any YouTube link form we accept
_VIDEO_ID_RE = re.compile(
    r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})"
)
_BARE_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")


def _thumb(data: dict) -> str:
    thumbs = data.get("thumbnails") or []
    return (thumbs[-1].get("url") or "").split("?")[0] if thumbs else ""


def _track_from_pyyt(data: dict, m_id: int) -> Track:
    # py-yt-search returns duration=None for live streams
    duration = data.get("duration")
    is_live = duration is None
    try:
        duration_sec = 0 if is_live else utils.to_seconds(duration)
    except (ValueError, AttributeError):
        duration_sec = 0
    return Track(
        id=data.get("id"),
        channel_name=(data.get("channel") or {}).get("name", ""),
        duration="LIVE" if is_live else duration,
        duration_sec=duration_sec,
        message_id=m_id,
        title=(data.get("title") or "")[:25],
        thumbnail=_thumb(data),
        url=data.get("link") or f"https://www.youtube.com/watch?v={data.get('id')}",
        view_count=(data.get("viewCount") or {}).get("short") or "",
        is_live=is_live,
    )


def _track_from_ytdlp(data: dict, m_id: int, fallback_url: str) -> Track:
    duration_sec = data.get("duration")
    is_live = data.get("is_live", False)
    if duration_sec is None and is_live:
        duration = "LIVE"
        duration_sec = 0
    else:
        duration = utils.format_duration(int(duration_sec)) if duration_sec else "0:00"
    return Track(
        id=data.get("id"),
        channel_name=data.get("uploader") or data.get("channel", ""),
        duration=duration,
        duration_sec=int(duration_sec) if duration_sec else 0,
        message_id=m_id,
        title=(data.get("title") or "")[:25],
        thumbnail=data.get("thumbnail") or _thumb(data),
        url=data.get("webpage_url") or data.get("url") or fallback_url,
        view_count=str(data.get("view_count", "") or ""),
        is_live=is_live,
    )


class Searcher:
    def __init__(self, cookies_manager):
        self._cookies = cookies_manager
        self.search_cache = {}  # {"query_video": (result, timestamp)}

    def valid(self, url: str) -> bool:
        from .utils import YouTubeUtils
        return YouTubeUtils().valid(url)

    @staticmethod
    def video_id(query: str) -> str | None:
        # Video ID from a YouTube link, or the query itself if it is a bare ID
        if m := _VIDEO_ID_RE.search(query):
            return m.group(1)
        if _BARE_ID_RE.fullmatch(query):
            return query
        return None

    # --- py-yt-search (no player API calls) ---
    @staticmethod
    async def _pyyt_results(query: str, limit: int) -> list[dict]:
        try:
            results = await VideosSearch(query, limit=limit).next()
            return [r for r in (results or {}).get("result", []) if r.get("id")]
        except Exception as e:
            logger.debug(f"py-yt-search failed for '{query}': {e}")
            return []

    @staticmethod
    async def _oembed_track(vid: str, m_id: int) -> Track | None:
        # Public oEmbed endpoint: title/channel/thumbnail without the bot
        # check, but no duration (so seeking and the length limit are off)
        url = f"https://www.youtube.com/watch?v={vid}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.youtube.com/oembed",
                    params={"url": url, "format": "json"},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.debug(f"oEmbed lookup failed for {vid}: {e}")
            return None
        return Track(
            id=vid,
            channel_name=data.get("author_name", ""),
            duration="0:00",
            duration_sec=0,
            message_id=m_id,
            title=(data.get("title") or "")[:25],
            thumbnail=data.get("thumbnail_url") or "",
            url=url,
            view_count="",
            is_live=False,
        )

    async def search_many(self, query: str, limit: int = 15) -> list[dict]:
        # Raw search results for inline queries
        return await self._pyyt_results(query, limit)

    # --- yt-dlp fallback ---
    def _ytdlp_opts(self, flat) -> dict:
        cookie = self._cookies.get_cookies() if self._cookies.checked else None
        return {
            "quiet": True,
            "noplaylist": True,
            "extract_flat": flat,
            "cookiefile": cookie,
            **ytdlp_network_opts(),
        }

    async def _ytdlp_info(self, target: str, flat) -> dict | None:
        def _extract():
            with yt_dlp.YoutubeDL(self._ytdlp_opts(flat)) as ydl:
                return ydl.extract_info(target, download=False)
        return await asyncio.to_thread(_extract)

    async def search(self, query: str, m_id: int, music: bool = False) -> Track | None:
        cache_key = query
        current_time = asyncio.get_running_loop().time()

        if cache_key in self.search_cache:
            cached_result, cache_timestamp = self.search_cache[cache_key]
            if current_time - cache_timestamp < 600:  # 10 minutes
                fresh = replace(cached_result)
                fresh.message_id = m_id
                fresh.file_path = None
                fresh.user = None
                fresh.time = 0
                fresh.video = False
                return fresh

        is_link = self.valid(query)
        vid = self.video_id(query) if is_link or _BARE_ID_RE.fullmatch(query) else None

        if music and not is_link and not vid and not query.lower().endswith("audio"):
            query = f"{query} Official Audio"

        try:
            track = None
            if vid:
                # Look the ID up through search; only accept an exact ID match
                for data in await self._pyyt_results(vid, 5):
                    if data.get("id") == vid:
                        track = _track_from_pyyt(data, m_id)
                        break
                # oEmbed can't tell live streams apart, so leave /live/ links to yt-dlp
                if track is None and "/live/" not in query:
                    track = await self._oembed_track(vid, m_id)
                if track is None:
                    data = await self._ytdlp_info(f"https://www.youtube.com/watch?v={vid}", "in_playlist")
                    if data:
                        track = _track_from_ytdlp(data, m_id, f"https://www.youtube.com/watch?v={vid}")
            elif is_link:
                # Other supported links (e.g. direct streams) go straight to yt-dlp
                data = await self._ytdlp_info(query, "in_playlist")
                if data:
                    track = _track_from_ytdlp(data, m_id, query)
            else:
                results = await self._pyyt_results(query, 1)
                if results:
                    track = _track_from_pyyt(results[0], m_id)
                else:
                    data = await self._ytdlp_info(f"ytsearch1:{query}", True)
                    entries = (data or {}).get("entries") or []
                    if entries:
                        e = entries[0]
                        track = _track_from_ytdlp(
                            e, m_id, e.get("url") or f"https://youtube.com/watch?v={e.get('id')}"
                        )

            if track is None or not track.id:
                return None

            self.search_cache[cache_key] = (track, current_time)
            if len(self.search_cache) > 100:
                oldest_key = min(self.search_cache.keys(),
                                 key=lambda k: self.search_cache[k][1])
                del self.search_cache[oldest_key]

            return replace(track)

        except Exception as e:
            logger.warning(f"⚠️ YouTube search failed for '{query}': {e}")
            return None

    async def playlist(self, limit: int, user: str, url: str) -> list[Track]:
        tracks: list[Track] = []

        # py-yt-search first (returns up to 100 videos, no player API calls)
        try:
            plist = await Playlist.get(url)
            for data in (plist or {}).get("videos", [])[:limit]:
                if not data or not data.get("id"):
                    continue
                track = _track_from_pyyt(data, 0)
                track.url = (track.url or "").split("&list=")[0]
                track.user = user
                track.view_count = ""
                tracks.append(track)
        except Exception as e:
            logger.debug(f"py-yt-search playlist failed for '{url}': {e}")

        if tracks:
            return tracks

        # yt-dlp fallback
        try:
            def _extract_playlist():
                opts = self._ytdlp_opts("in_playlist")
                opts.pop("noplaylist")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)

            plist = await asyncio.to_thread(_extract_playlist)
            for data in ((plist or {}).get("entries") or [])[:limit]:
                if not data:
                    continue
                try:
                    track = _track_from_ytdlp(
                        data, 0, f"https://youtube.com/watch?v={data.get('id')}"
                    )
                    track.title = (data.get("title") or "Unknown")[:25]
                    track.url = data.get("url") or data.get("webpage_url") or track.url
                    track.user = user
                    track.view_count = ""
                    tracks.append(track)
                except Exception:
                    continue
            return tracks
        except Exception as e:
            logger.warning(f"⚠️ YouTube playlist extraction failed for '{url}': {e}")
            return []
