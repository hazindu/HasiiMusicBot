# ==============================================================================
# play.py - Core Playback
# ==============================================================================
# Handles all /play commands, searching YouTube, managing queues, and initiating playback.
# ==============================================================================

from pyrogram import filters
from pyrogram import types
from pyrogram.errors import FloodWait, MessageIdInvalid, MessageDeleteForbidden, ChatSendPlainForbidden, ChatWriteForbidden

from HasiiMusic import tune, app, config, db, lang, queue, spotify, tg, yt
from HasiiMusic.helpers import buttons, utils
from HasiiMusic.helpers._play import checkUB
from HasiiMusic.helpers._dataclass import Media
import asyncio
import logging
import re

logger = logging.getLogger(__name__)


async def safe_edit(message, text, **kwargs):
    try:
        await message.edit_text(text, **kwargs)
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            await message.edit_text(text, **kwargs)
            return True
        except (MessageIdInvalid, MessageDeleteForbidden, Exception):
            return False
    except (MessageIdInvalid, MessageDeleteForbidden):
        # Message was deleted or became invalid - this is expected
        return False
    except Exception:
        # Other errors - log but don't crash
        return False


async def safe_reply(message, text, **kwargs):
    try:
        return await message.reply_text(text, **kwargs)
    except (ChatSendPlainForbidden, ChatWriteForbidden):
        logger.warning(
            f"Cannot send text in chat {message.chat.id} (chat write forbidden)")
        return None
    except Exception as e:
        logger.error(f"Error in safe_reply: {e}")
        return None


async def auto_delete(message: types.Message, delay: int = 15):
    """Auto-delete a message after a given timeout."""
    if not message:
        return
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"auto_delete: couldnt delete message: {e}")


@app.on_message(
    filters.command(
        [
            "play",
            "playforce",
            "vplay",
            "vplayforce",
        ]
    )
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    url: str = None,
    video: bool = False,
) -> None:
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass

    chat_id = m.chat.id

    # Select emoji for this play session
    play_emoji = m.lang["play_emoji"]

    try:
        sent = await safe_reply(m, m.lang["play_searching"].format(play_emoji))
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            sent = await safe_reply(m, m.lang["play_searching"].format(play_emoji))
        except FloodWait as e2:
            # If still flood wait, wait longer and give up gracefully
            await asyncio.sleep(e2.value)
            return  # Abort silently
        except Exception:
            return  # Abort silently
    except Exception:
        return  # If we can't even send initial message, abort

    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []
    file = None  # Initialize file variable

    # Check media first (Telegram files) before URL extraction
    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif url:
        # Handle direct stream URLs (m3u8, HLS, DASH) — no download needed
        if yt.is_direct_stream(url):
            # Build a Media object directly and treat it as a live stream
            stream_title = url.split("/")[-1].split("?")[0] or "Live Stream"
            file = Media(
                id=url,
                title=stream_title,
                duration="🔴 Live",
                duration_sec=0,
                file_path=url,   # Pass URL directly — no download
                message_id=sent.id,
                url=url,
                is_live=True,
                video=video,
            )
        elif spotify.valid(url):
            if spotify.is_playlist(url):
                try:
                    tracks = await spotify.playlist(
                        min(config.PLAYLIST_LIMIT, getattr(
                            config, "PLAYLIST_MAX", 100)), mention, url
                    )
                except Exception as e:
                    await safe_edit(
                        sent,
                        f"<blockquote>❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ꜰᴇᴛᴄʜ ꜱᴘᴏᴛɪꜰʏ ᴘʟᴀʏʟɪꜱᴛ.\n\n"
                        f"ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</blockquote>"
                    )
                    return

                if not tracks:
                    await safe_edit(sent, m.lang["playlist_error"])
                    return

                file = tracks[0]
                tracks.remove(file)
                file.message_id = sent.id
            else:
                file = await spotify.search(url, sent.id)
        elif "playlist" in url:
            try:
                tracks = await yt.playlist(
                    min(config.PLAYLIST_LIMIT, getattr(
                        config, "PLAYLIST_MAX", 100)), mention, url
                )
            except Exception as e:
                await safe_edit(
                    sent,
                    f"<blockquote>❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ꜰᴇᴛᴄʜ ᴘʟᴀʏʟɪꜱᴛ.\n\n"
                    f"ʏᴏᴜᴛᴜʙᴇ ᴘʟᴀʏʟɪꜱᴛꜱ ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ᴇxᴘᴇʀɪᴇɴᴄɪɴɢ ɪꜱꜱᴜᴇꜱ. "
                    f"ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴘʟᴀʏɪɴɢ ɪɴᴅɪᴠɪᴅᴜᴀʟ ꜱᴏɴɢꜱ ɪɴꜱᴛᴇᴀᴅ.</blockquote>"
                )
                return

            if not tracks:
                await safe_edit(sent, m.lang["playlist_error"])
                return

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id)

        if not file:
            await safe_edit(
                sent,
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )
            return

    elif len(m.command) >= 2:
        # Drop the -f (force) flag so it isn't part of the search
        args = m.command[2:] if m.command[1] == "-f" else m.command[1:]
        query = " ".join(args)
        file = await yt.search(query, sent.id)
        if not file:
            await safe_edit(
                sent,
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )
            return

    if not file:
        return

    file.video = getattr(file, "video", False) or video
    if file.video:
        for track in tracks:
            track.video = True

    # Skip duration check for live streams
    if not file.is_live and file.duration_sec > config.DURATION_LIMIT:
        await safe_edit(
            sent,
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )
        return

    if await db.is_logger():
        await utils.play_log(m, file.title, file.duration)

    file.user = mention
    if force:
        queue.force_add(chat_id, file)
    else:
        position = queue.add(chat_id, file)  # Returns 0-based index

        # If a call is already active OR we are not the first in queue,
        # we return early and let the background queue processor handle it.
        if await db.get_call(chat_id) or position > 0:
            # When call is active, position 0 is currently playing
            # So actual waiting position is: position (e.g., 1st waiting = index 1)
            # Display as 1-based for users: index 1 → "1st in queue"
            await safe_edit(
                sent,
                m.lang["play_queued"].format(
                    position,  # Shows waiting position: 1, 2, 3...
                    file.url,
                    file.title,
                    file.duration,
                    m.from_user.mention,
                ),
                reply_markup=buttons.play_queued(
                    chat_id, file.id, m.lang["play_now"]
                ),
            )
            if tracks:
                for track in tracks:
                    queue.add(chat_id, track)

            # ✨ NEW: Start preloading queued tracks in background
            try:
                from HasiiMusic import preload
                asyncio.create_task(preload.start_preload(chat_id, count=2))
            except Exception:
                # Non-critical, continue without preload
                pass

            return

    if not file.file_path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", file.id):
            try:
                resolved = await yt.search(file.id, sent.id)
                if resolved:
                    file.id = resolved.id
                    if resolved.thumbnail:
                        file.thumbnail = resolved.thumbnail
                    if resolved.duration_sec:
                        file.duration_sec = resolved.duration_sec
                        file.duration = resolved.duration
            except Exception:
                pass
        file.file_path = await yt.download(
            file.id,
            is_live=file.is_live,
            video=getattr(file, "video", False),
        )
        if not file.file_path:
            if not await db.get_call(chat_id):
                queue.clear(chat_id)
            await safe_edit(
                sent,
                "<blockquote>❌ Failed to download media.\n\n"
                "Possible reasons:\n"
                "• YouTube detected bot activity (update cookies)\n"
                "• Video is region-blocked or private\n"
                "• Age-restricted content (requires cookies)</blockquote>"
            )
            return

    try:
        await tune.play_media(
            chat_id=chat_id,
            message=sent,
            media=file
        )
        # React with emoji on successful play
        try:
            emoji = m.lang["play_emoji"]
            await m.react(emoji)
        except Exception:
            # If reaction fails, continue anyway (not critical)
            pass
    except Exception as e:
        error_msg = str(e)
        if not await db.get_call(chat_id):
            queue.clear(chat_id)
        if "bot" in error_msg.lower() or "sign in" in error_msg.lower():
            await safe_edit(
                sent,
                "<blockquote>❌ YouTube bot detection triggered.\n\n"
                "Solution:\n"
                "• Update YouTube cookies in `HasiiMusic/cookies/` folder\n"
                "• Wait a few minutes before trying again\n"
                "• Try /radio for uninterrupted music\n\n"
                f"Support: {config.SUPPORT_CHAT}</blockquote>"
            )
        else:
            await safe_edit(
                sent,
                f"<blockquote>❌ Playback error:\n{error_msg}\n\n"
                f"Support: {config.SUPPORT_CHAT}</blockquote>"





















            )
        return
    if tracks:
        for track in tracks:
            queue.add(chat_id, track)
