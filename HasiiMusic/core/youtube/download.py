# ==============================================================================
# download.py - YouTube Downloader Engine
# ==============================================================================
# This file orchestrates the downloading of audio and video from YouTube.
# Features:
# - Limits concurrency using semaphores
# - Prevents duplicate concurrent downloads using locks
# - Executes yt-dlp to download streams and files
# - Resolves Spotify fallbacks lazily
# ==============================================================================

import re
import glob
import time
import asyncio
from pathlib import Path
from typing import Optional
import yt_dlp
from HasiiMusic import config, logger

class Downloader:
    def __init__(self, cookies_manager, storage_manager, searcher):
        self._cookies = cookies_manager
        self._storage = storage_manager
        self._searcher = searcher
        self._download_locks: dict = {}
        self._download_tasks: set = set()  # keep references to running download tasks
        self._download_semaphore = asyncio.Semaphore(5)
        self._max_video_height = getattr(config, "VIDEO_MAX_HEIGHT", 1080)
        
    def _get_download_lock(self, video_id: str) -> asyncio.Lock:
        if video_id not in self._download_locks:
            self._download_locks[video_id] = asyncio.Lock()
        return self._download_locks[video_id]

    async def download(self, video_id: str, is_live: bool = False, video: bool = False) -> Optional[str]:
        # Lazily resolve query or Spotify link to a YouTube video ID if needed
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            try:
                from HasiiMusic import spotify
                if spotify.valid(video_id):
                    resolved = await spotify.search(video_id, 0)
                else:
                    resolved = await self._searcher.search(video_id, 0)
                if resolved and resolved.id:
                    video_id = resolved.id
                    is_live = getattr(resolved, "is_live", is_live)
                else:
                    logger.warning(f"Could not resolve '{video_id}' for download")
                    return None
            except Exception as e:
                logger.warning(f"Failed to lazily resolve '{video_id}': {e}")
                return None

        url = "https://www.youtube.com/watch?v=" + video_id

        # Extract live stream URL
        if is_live:
            cookie = self._cookies.get_cookies()
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie,
                "format": "bestaudio/best",
                "noplaylist": True,
                "socket_timeout": 20,
                "extractor_retries": 5,
                "sleep_interval_requests": 1,
            }

            def _extract_url():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(url, download=False)
                        if not info:
                            return None

                        direct = info.get("url")
                        if direct:
                            return direct

                        # Find URL in formats
                        for fmt in info.get("formats", []):
                            if fmt.get("acodec") != "none" and fmt.get("url"):
                                return fmt["url"]

                        return info.get("manifest_url")
                    except yt_dlp.utils.ExtractorError as ex:
                        error_msg = str(ex)
                        if "not available" in error_msg.lower():
                            logger.error(
                                "Video format not available or region-blocked.")
                        else:
                            logger.error(
                                "Live stream URL extraction failed: %s", ex)
                        return None
                    except Exception as ex:
                        logger.error(
                            "Unexpected error during live stream extraction: %s", ex)
                        return None

            try:
                stream_url = await asyncio.wait_for(asyncio.to_thread(_extract_url), timeout=35)
            except asyncio.TimeoutError:
                logger.error("Live stream URL extraction timed out for %s", video_id)
                return None

            return stream_url

        # Let yt-dlp choose the best format
        filename_pattern = f"downloads/{video_id}"

        def _check_cache() -> Optional[str]:
            """Check downloads/ for a valid existing file. Deletes invalid stubs on the way."""
            existing_files = [
                f for f in glob.glob(f"{filename_pattern}.*")
                if not f.endswith((".part", ".ytdl", ".temp"))
            ]
            if video:
                video_candidates = [
                    f for f in existing_files
                    if Path(f).suffix.lower() in {".mp4", ".mkv", ".mov"}
                ]
                for f in video_candidates:
                    if self._storage.is_valid_file(f):
                        return f
                    self._storage.delete_stub(f)
            else:
                audio_candidates = [
                    f for f in existing_files
                    if Path(f).suffix.lower() in {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}
                ]
                for f in audio_candidates:
                    if self._storage.is_valid_file(f):
                        return f
                    self._storage.delete_stub(f)
                # Fallback to mp4 for audio
                container_fallbacks = [
                    f for f in existing_files
                    if Path(f).suffix.lower() in {".mp4", ".mkv", ".mov"}
                ]
                for f in container_fallbacks:
                    if self._storage.is_valid_file(f):
                        return f
                    self._storage.delete_stub(f)
            return None

        # Fast path: check cache without acquiring any lock
        cached = _check_cache()
        if cached:
            return cached

        # Create downloads dir
        downloads_dir = Path("downloads")
        if not downloads_dir.exists():
            try:
                downloads_dir.mkdir(parents=True, exist_ok=True)
                logger.info("📁 Created downloads directory")
            except Exception as e:
                logger.error(f"❌ Cannot create downloads directory: {e}")
                return None

        # Acquire per-video-ID lock to prevent duplicate concurrent downloads of the same video.
        async def _locked_download() -> Optional[str]:
            async with self._get_download_lock(video_id):
                cached = _check_cache()
                if cached:
                    return cached

                # **PERFORMANCE FIX**: Use semaphore to limit concurrent downloads
                async with self._download_semaphore:
                    cookie = self._cookies.get_cookies()
                    base_opts = {
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "quiet": True,
                        "noplaylist": True,
                        "geo_bypass": True,
                        "no_warnings": True,
                        "overwrites": False,
                        "nocheckcertificate": True,
                        "continuedl": True,
                        "noprogress": True,
                        "concurrent_fragment_downloads": 4,
                        "http_chunk_size": 524288,  # 512KB chunks
                        "socket_timeout": 30,
                        "retries": 2,
                        "fragment_retries": 2,
                        "extractor_retries": 5,
                        "sleep_interval_requests": 1,
                    }

                    if video:
                        height_filter = ""
                        if self._max_video_height and self._max_video_height > 0:
                            height_filter = f"[height<={self._max_video_height}]"
                        format_chain = (
                            f"bestvideo[ext=mp4]{height_filter}+bestaudio[ext=m4a]/"
                            f"bestvideo{height_filter}+bestaudio/"
                            "bestvideo+bestaudio/best"
                        )
                        ydl_opts = {
                            **base_opts,
                            "format": format_chain,
                            "merge_output_format": "mp4",
                            "postprocessors": [
                                {
                                    "key": "FFmpegVideoConvertor",
                                    "preferedformat": "mp4",
                                }
                            ],
                        }
                    else:
                        ydl_opts = {
                            **base_opts,
                            "format": "bestaudio/best",
                            "postprocessors": [],
                        }

                    ydl_opts_cookie = {
                        **ydl_opts,
                        "cookiefile": cookie,
                    }

                    def _download(ydl_runtime_opts):
                        ydl_instance = None
                        try:
                            ydl_instance = yt_dlp.YoutubeDL(ydl_runtime_opts)
                            info = ydl_instance.extract_info(url, download=True)
                            if not info:
                                logger.error(f"❌ Failed to extract info for {video_id}")
                                return None

                            time.sleep(0.5)
                            located = self._storage.locate_download_file(video_id, video=video)
                            if located:
                                return located
                            found = [Path(f).name for f in glob.glob(f"downloads/{video_id}*")]
                            logger.error(
                                f"❌ Download completed but file not found for: {video_id} "
                                f"(files present: {found or 'none'})"
                            )
                            return None
                        except yt_dlp.utils.ExtractorError as ex:
                            error_msg = str(ex)
                            if "not available" in error_msg.lower():
                                logger.error(
                                    "❌ Video not available: May be region-blocked or private.")
                            elif "age" in error_msg.lower():
                                logger.error(
                                    "❌ Age-restricted video: Cookies required.")
                            else:
                                logger.error("❌ YouTube extraction failed: %s", ex)
                            return None
                        except yt_dlp.utils.DownloadError as ex:
                            error_msg = str(ex)
                            recovered = self._storage.locate_download_file(video_id, video=video)
                            if "unable to rename file" in error_msg.lower() and recovered:
                                logger.warning(
                                    f"⚠️ Renaming failed for {video_id}, using recovered file {Path(recovered).name}"
                                )
                                return recovered
                            if "416" in error_msg or "Requested range not satisfiable" in error_msg:
                                logger.warning(f"⚠️ Range error for {video_id}, skipping")
                            else:
                                logger.warning(f"⚠️ Download error for {video_id}: {ex}")
                                if recovered:
                                    logger.warning(
                                        f"⚠️ Using recovered file for {video_id} despite download error"
                                    )
                                    return recovered
                            return None
                        except Exception as ex:
                            logger.warning(f"⚠️ Unexpected download error for {video_id}: {ex}")
                            return None
                        finally:
                            if ydl_instance:
                                try:
                                    ydl_instance.close()
                                except Exception:
                                    pass

                    return await asyncio.to_thread(_download, ydl_opts_cookie)

        # Run the locked download as its own task and shield it from the caller.
        # If the caller is cancelled (e.g. /stop cancels a preload), the yt-dlp thread
        # keeps running, so the lock must stay held until it really finishes.
        # Otherwise a second download of the same video starts and both write the
        # same .part file ("No such file or directory: ....part").
        task = asyncio.create_task(_locked_download())
        self._download_tasks.add(task)
        task.add_done_callback(self._download_tasks.discard)
        return await asyncio.shield(task)
