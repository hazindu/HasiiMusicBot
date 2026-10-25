# ==============================================================================
# iquery.py - Inline Queries
# ==============================================================================
# Lets users type @botname in any chat to search YouTube and share tracks.
# ==============================================================================

import asyncio
import yt_dlp
from pyrogram import types

from HasiiMusic import app, config, yt
from HasiiMusic.helpers import buttons, utils


@app.on_inline_query(~app.bl_users)
async def inline_query_handler(_, query: types.InlineQuery):
    text = query.query.strip().lower()
    if not text:
        return

    try:
        def _extract():
            cookie = yt.get_cookies() if yt.checked else None
            ydl_opts = {
                "quiet": True,
                "extract_flat": True,
                "cookiefile": cookie
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch15:{text}", download=False)

        results = await asyncio.to_thread(_extract)
        if not results or "entries" not in results:
            return

        answers = []
        for video in results["entries"]:
            if not video:
                continue
                
            title = video.get("title", "Unknown Title").title()
            
            duration_sec = video.get("duration")
            is_live = video.get("is_live", False)
            if duration_sec is None and is_live:
                duration = "LIVE"
            else:
                duration = utils.format_duration(int(duration_sec)) if duration_sec else "0:00"
                
            views = str(video.get("view_count", "N/A"))
            thumbnail = video.get("thumbnails", [{}])[-1].get("url", "").split("?")[0] if video.get("thumbnails") else ""
            channel = video.get("uploader", "Unknown Channel")
            channellink = video.get("uploader_url", "https://youtube.com")
            link = video.get("url") or video.get("webpage_url") or f"https://youtube.com/watch?v={video.get('id')}"
            published = "N/A" # yt-dlp flat extract might not have this

            description = f"{views} views | {duration} | {channel}"
            caption = (
                f"<b>Title:</b> <a href='{link}'>{title[:250]}</a>\n\n"
                f"<b>Duration:</b> {duration}\n"
                f"<b>Views:</b> <code>{views}</code>\n"
                f"<b>Channel:</b> <a href='{channellink}'>{channel}</a>\n"
                f"<u><i>Fetched by {app.name}</i></u>"
            )

            answers.append(
                types.InlineQueryResultPhoto(
                    photo_url=thumbnail or config.PING_IMG, # fallback thumbnail
                    title=title,
                    description=description,
                    caption=caption,
                    reply_markup=buttons.yt_key(link),
                )
            )

        if answers:
            await app.answer_inline_query(query.id, results=answers, cache_time=5)
    except Exception as e:
        pass
