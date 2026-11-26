# ==============================================================================
# cookies.py - Live YouTube Cookie Update
# ==============================================================================
# Replace YouTube cookies without restarting the bot.
#   /cookies               -> re-download from COOKIE_URL in .env
#   /cookies <url> [url]   -> replace with cookies from paste url(s)
#   reply to a .txt file with /cookies -> replace with that file
#   /cookies status        -> show loaded cookie files
# ==============================================================================

import os

from pyrogram import filters, types

from HasiiMusic import app, config, logger, yt


@app.on_message(filters.command(["cookies", "setcookies"]) & app.sudo_filter)
async def _cookies(_, m: types.Message):
    manager = yt._cookies
    args = m.command[1:]

    if args and args[0].lower() == "status":
        manager.get_cookies()
        files = manager.cookies or ["(none)"]
        return await m.reply_text(
            "<blockquote>🍪 Loaded cookie files:\n" + "\n".join(f"• {f}" for f in files) + "</blockquote>"
        )

    src = m.reply_to_message if m.reply_to_message and m.reply_to_message.document else None
    if src is None and m.document:
        src = m
    doc = src.document if src else None

    sent = await m.reply_text("<blockquote>🍪 Updating cookies...</blockquote>")

    # 1) Cookie file sent as a document
    if doc:
        if not (doc.file_name or "").lower().endswith(".txt"):
            return await sent.edit_text("<blockquote>❌ Send a Netscape-format .txt cookie file.</blockquote>")
        buf = await src.download(in_memory=True)
        content = bytes(buf.getbuffer())
        if not manager.looks_valid(content):
            return await sent.edit_text(
                "<blockquote>❌ That file doesn't look like YouTube cookies (no .youtube.com entries).</blockquote>"
            )
        removed = manager.clear()
        name = manager.add_file(content)
        yt._downloader.clear_bot_blocks()
        logger.info(f"🍪 Cookies replaced from Telegram file by {m.from_user.id}: {name}")
        try:
            # Don't leave the cookie file sitting in the chat
            await src.delete()
        except Exception:
            pass
        return await sent.edit_text(
            f"<blockquote>✅ Cookies updated ({len(content)} bytes). Removed {removed} old file(s).</blockquote>"
        )

    # 2) URLs given, or fall back to COOKIE_URL from .env
    urls = args or config.COOKIES_URL
    if not urls:
        return await sent.edit_text(
            "<blockquote>❌ No COOKIE_URL set. Reply to a .txt cookie file or pass a paste url.</blockquote>"
        )

    old = list(manager.cookies)
    manager.cookies = []
    await manager.save_cookies(urls)
    if not manager.cookies:
        manager.cookies = old  # keep the old ones rather than none at all
        return await sent.edit_text("<blockquote>❌ Download failed; kept the old cookies. Check the url(s).</blockquote>")

    yt._downloader.clear_bot_blocks()
    for name in old:
        if name not in manager.cookies:
            try:
                os.remove(f"HasiiMusic/cookies/{name}")
            except OSError:
                pass
    await sent.edit_text(
        f"<blockquote>✅ Cookies updated from {len(urls)} url(s). Active files: {len(manager.cookies)}.</blockquote>"
    )
