# ==============================================================================
# iquery.py - Inline Queries
# ==============================================================================
# Lets users type @botname in any chat to search YouTube and share tracks.
# ==============================================================================

from pyrogram import types

from HasiiMusic import app, config, yt
from HasiiMusic.helpers import buttons


@app.on_inline_query(~app.bl_users)
async def inline_query_handler(_, query: types.InlineQuery):
    text = query.query.strip().lower()
    if not text:
        return

    try:
        results = await yt.search_many(text, 15)
        if not results:
            return

        answers = []
        for video in results:
            title = (video.get("title") or "Unknown Title").title()
            duration = video.get("duration") or "LIVE"
            views = (video.get("viewCount") or {}).get("short") or "N/A"
            thumbs = video.get("thumbnails") or [{}]
            thumbnail = (thumbs[-1].get("url") or "").split("?")[0]
            ch = video.get("channel") or {}
            channel = ch.get("name") or "Unknown Channel"
            channellink = ch.get("link") or "https://youtube.com"
            link = video.get("link") or f"https://youtube.com/watch?v={video.get('id')}"

            description = f"{views} | {duration} | {channel}"
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
