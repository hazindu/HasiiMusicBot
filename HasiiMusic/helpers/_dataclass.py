# ==============================================================================
# _dataclass.py - Models
# ==============================================================================
# Simple data structures to pass around Media and Track info safely.
# ==============================================================================

from dataclasses import dataclass


@dataclass
class Media:
    id: str
    duration: str
    duration_sec: int
    file_path: str
    message_id: int
    title: str
    url: str
    time: int = 0
    user: str = None
    is_live: bool = False
    video: bool = False
    playlist_name: str = None
    playlist_url: str = None
    playlist_type: str = None
    playlist_index: int = 0
    requester_id: int | None = None


@dataclass
class Track:
    id: str
    channel_name: str
    duration: str
    duration_sec: int
    title: str
    url: str
    file_path: str = None
    message_id: int = 0
    time: int = 0
    thumbnail: str = None
    user: str = None
    view_count: str = None
    is_live: bool = False
    video: bool = False
    playlist_name: str = None
    playlist_url: str = None
    playlist_type: str = None
    playlist_index: int = 0
    requester_id: int | None = None
