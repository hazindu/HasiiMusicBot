# ==============================================================================
# storage.py - YouTube Storage Manager
# ==============================================================================
# This file manages the filesystem cache for downloaded audio/video.
# Features:
# - Validates cached files against 0-byte stubs
# - Locates existing downloads by video ID
# - Cleans up corrupted stubs
# ==============================================================================

import os
import glob
from pathlib import Path
from typing import Optional
from HasiiMusic import logger

class StorageManager:
    def __init__(self, min_valid_bytes: int = 4096):
        self.MIN_VALID_BYTES = min_valid_bytes

    def is_valid_file(self, path: str) -> bool:
        """Return True only if path exists, is a real file, and has enough content.
        Guards against 0-byte stubs and partial writes that cause unexpected EOF in ntgcalls.
        """
        try:
            return os.path.isfile(path) and os.path.getsize(path) >= self.MIN_VALID_BYTES
        except OSError:
            return False

    def delete_stub(self, path: str) -> None:
        """Delete an invalid/corrupt file stub so a fresh download is triggered next time."""
        try:
            os.remove(path)
            logger.warning(f"🗑️ Deleted invalid cached file (too small or corrupt): {path}")
        except OSError:
            pass

    def locate_download_file(self, video_id: str, video: bool = False) -> Optional[str]:
        pattern = f"downloads/{video_id}*"
        candidates = sorted([
            path for path in glob.glob(pattern)
            if not path.endswith((".part", ".ytdl", ".info.json", ".temp"))
        ])

        video_exts = {".mp4", ".mkv", ".mov"}
        audio_exts = {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}

        if video:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in video_exts:
                    if self.is_valid_file(path):
                        return path
                    self.delete_stub(path)
        else:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in audio_exts:
                    if self.is_valid_file(path):
                        return path
                    self.delete_stub(path)
            # "bestaudio/best" falls back to a combined mp4 when no audio-only
            # format is available; it still plays fine as audio
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in video_exts and self.is_valid_file(path):
                    return path

        # No valid file found
        return None
