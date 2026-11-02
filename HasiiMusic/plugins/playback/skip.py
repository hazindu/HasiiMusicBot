# ==============================================================================
# skip.py - Skip Track
# ==============================================================================
# Skips the current track and automatically starts the next one in queue.
# ==============================================================================

import asyncio
import logging
from pyrogram import filters, types
from pyrogram.errors import ChatSendPlainForbidden, ChatWriteForbidden

from HasiiMusic import tune, app, db, lang
from HasiiMusic.helpers import can_manage_vc

logger = logging.getLogger(__name__)


@app.on_message(filters.command(["skip", "next"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _skip(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    if not await db.get_call(m.chat.id):
        try:
            return await m.reply_text(m.lang["not_playing"])
        except (ChatSendPlainForbidden, ChatWriteForbidden):
            return

    await tune.play_next(m.chat.id)
    try:
        sent_msg = await m.reply_text(m.lang["play_skipped"].format(m.from_user.mention))
    except (ChatSendPlainForbidden, ChatWriteForbidden):
        logger.warning("Cannot send plain text in media-only chat")
        return
    except Exception as e:
        logger.warning(f"Could not send skip confirmation: {e}")
        return

    # Auto-delete after 5 seconds
    await asyncio.sleep(5)
    try:
        await sent_msg.delete()
    except Exception:
        pass
