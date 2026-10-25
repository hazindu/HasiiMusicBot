# ==============================================================================
# utils.py - YouTube Utilities
# ==============================================================================
# This file contains stateless utilities for YouTube integration.
# Features:
# - Matches YouTube URLs via regex
# - Validates YouTube links
# - Extracts YouTube links from Telegram messages
# ==============================================================================

import re
from typing import Union
from pyrogram import enums, types

class YouTubeUtils:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="  # Base YouTube URL
        # Match YouTube URLs
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        # Match direct stream URLs: m3u8, mpd, or plain http media streams
        self.stream_regex = re.compile(
            r"https?://[^\s]+\.(?:m3u8|mpd|ts)(\?[^\s]*)?"
            r"|https?://[^\s]*/(?:stream|live|hls|dash)[^\s]*",
            re.IGNORECASE
        )

    def is_direct_stream(self, url: str) -> bool:
        """Check if the URL is a direct m3u8/HLS/DASH stream link."""
        # YouTube links (e.g. youtube.com/live/ID) must go through yt-dlp
        if re.match(self.regex, url):
            return False
        return bool(re.match(self.stream_regex, url))

    def valid(self, url: str) -> bool:
        # Accept YouTube URLs and direct stream URLs (m3u8, mpd, etc.)
        return bool(re.match(self.regex, url)) or self.is_direct_stream(url)

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        link = None
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""

            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[entity.offset: entity.offset +
                                    entity.length]
                        break

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None
