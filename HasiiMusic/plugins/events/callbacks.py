# ==============================================================================
# callbacks.py - Button Interactions
# ==============================================================================
# All the logic for when users click inline buttons (skipping tracks, pausing,
# navigating the help menu, etc).
# ==============================================================================

import re
import asyncio
from functools import wraps

from pyrogram import filters, types
from pyrogram.errors import FloodWait, QueryIdInvalid

from HasiiMusic import tune, app, config, db, lang, logger, queue, tg, yt
from HasiiMusic.helpers import admin_check, buttons, can_manage_vc
from HasiiMusic.helpers._requester import TrackChangedError, ensure_current_track


def safe_callback(func):
    @wraps(func)
    async def wrapper(client, query: types.CallbackQuery):
        try:
            return await func(client, query)
        except TrackChangedError:
            try:
                return await query.answer(query.lang["play_expired"], show_alert=True)
            except QueryIdInvalid:
                return
        except QueryIdInvalid:
            return
        except Exception as e:
            logger.error(f"Error in callback {func.__name__}: {e}", exc_info=True)
            try:
                await query.answer("❌ An error occurred. Please try again.", show_alert=True)
            except Exception:
                pass
    return wrapper


@app.on_callback_query(filters.regex("^start$") & ~app.bl_users)
@lang.language()
@safe_callback
async def _start_callback(_, query: types.CallbackQuery):
    await query.answer()
    
    _text = query.lang["start_pm"].format(query.from_user.first_name, app.name)
    key = buttons.start_key(query.lang, True)
    
    try:
        await query.edit_message_caption(
            caption=_text,
            reply_markup=key,
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=_text,
                reply_markup=key,
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
@safe_callback
async def cancel_dl(_, query: types.CallbackQuery):
    await query.answer()
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
@safe_callback
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()
    action, chat_id = args[1], int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention

    # Handle close action first - allow any user to delete the message (no popup notification)
    if action == "close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if chat_id != query.message.chat.id:
        return await query.answer(query.lang["user_no_perms"], show_alert=True)

    user_id = query.from_user.id
    has_permission = False
    expected_media = None
    
    if user_id in app.sudoers:
        has_permission = True
    elif await db.is_auth(chat_id, user_id):
        has_permission = True
    else:
        admins = await db.get_admins(chat_id)
        if user_id in admins:
            has_permission = True

    if not has_permission and action != "force":
        current = queue.get_current(chat_id)
        if current is not None and getattr(current, "requester_id", None) == user_id:
            has_permission = True
            expected_media = current
    
    if not has_permission:
        return await query.answer("⚠️ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜsᴇ ᴛʜɪs.", show_alert=True)

    if not await db.get_call(chat_id):
        return await query.answer(query.lang["not_playing"], show_alert=True)

    if action == "status":
        return await query.answer()
    
    # Handle seek actions
    if action.startswith("seek_"):
        return await handle_seek(query, chat_id, action, user, expected_media=expected_media)
    
    # Handle loop action
    if action == "loop":
        return await handle_loop(query, chat_id, user, expected_media=expected_media)
    

    await query.answer(query.lang["processing"], show_alert=True)
    control_options = {"expected_media": expected_media} if expected_media is not None else {}

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer(
                query.lang["play_already_paused"], show_alert=True
            )
        if not await tune.pause(chat_id, **control_options):
            return await query.answer(query.lang["not_playing"], show_alert=True)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(
                    chat_id, query.lang["paused"], False)
            )
        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        status = query.lang["playing"]
        if await db.playing(chat_id):
            return await query.answer(query.lang["play_not_paused"], show_alert=True)
        if not await tune.resume(chat_id, **control_options):
            return await query.answer(query.lang["not_playing"], show_alert=True)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(
                    chat_id, query.lang["playing"], True)
            )
        reply = query.lang["play_resumed"].format(user)

    elif action == "previous":
        await tune.play_previous(chat_id, **control_options)
        status = query.lang["skipped"]  # We reuse the "skipped" text or define a new one if available
        reply = "Track reverted." # Basic reply

    elif action == "skip":
        await tune.play_next(chat_id, **control_options)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await query.edit_message_text(query.lang["play_expired"])

        current = queue.get_current(chat_id)
        m_id = current.message_id if current else None
        async with tune.get_lock(chat_id):
            pos, media = queue.check_item(chat_id, args[3])
            if not media or pos == -1:
                return await query.edit_message_text(query.lang["play_expired"])
            queue.force_add(chat_id, media, remove=pos)
        try:
            await app.delete_messages(
                chat_id=chat_id, message_ids=[
                    m_id, media.message_id], revoke=True
            )
            media.message_id = None
        except:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])
        if not media.file_path:
            media.file_path = await yt.download(
                media.id,
                video=getattr(media, "video", False),
            )
        media.message_id = msg.id
        return await tune.play_media(chat_id, msg, media)

    elif action == "replay":
        await tune.replay(chat_id, **control_options)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await tune.stop(chat_id, **control_options)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    try:
        if action in ["skip", "replay", "stop"]:
            sent_msg = None
            try:
                sent_msg = await query.message.reply_text(reply)
            except FloodWait as e:
                # If FloodWait occurs, wait and retry once
                await asyncio.sleep(e.value)
                try:
                    sent_msg = await query.message.reply_text(reply)
                except Exception:
                    pass
            except Exception:
                pass
            await query.message.delete()
            
            # Auto-delete the reply message after 5 seconds
            if sent_msg:
                await asyncio.sleep(5)
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
        else:
            mtext = re.sub(
                r"\n\n<blockquote>.*?</blockquote>",
                "",
                query.message.caption.html or query.message.text.html,
                flags=re.DOTALL,
            )
            keyboard = buttons.controls(
                chat_id, status=status if action != "resume" else None,
                is_playing=(action != "pause")
            )
        await query.edit_message_text(
            f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
        )
    except FloodWait as e:
        # Handle FloodWait on edit_message_text
        await asyncio.sleep(e.value)
        try:
            await query.edit_message_text(
                f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
            )
        except Exception:
            pass
    except Exception:
        pass


async def handle_seek(query: types.CallbackQuery, chat_id: int, action: str, user: str, *, expected_media=None):
    media = queue.get_current(chat_id)
    ensure_current_track(media, expected_media)
    if not media or media.is_live:
        return await query.answer("⚠️ ᴄᴀɴɴᴏᴛ ꜱᴇᴇᴋ ɪɴ ʟɪᴠᴇ ꜱᴛʀᴇᴀᴍꜱ!", show_alert=True)
    
    if not media.duration_sec or media.duration_sec == 0:
        return await query.answer("⚠️ ᴄᴀɴɴᴏᴛ ꜱᴇᴇᴋ ɪɴ ᴛʜɪꜱ ᴛʀᴀᴄᴋ!", show_alert=True)
    
    # Determine seek amount and direction
    if action == "seek_back_10":
        seconds = -10
        label = "« 10s"
    elif action == "seek_back_30":
        seconds = -30
        label = "« 30s"
    elif action == "seek_forward_10":
        seconds = 10
        label = "10s »"
    elif action == "seek_forward_30":
        seconds = 30
        label = "30s »"
    else:
        return await query.answer("⚠️ ɪɴᴠᴀʟɪᴅ ꜱᴇᴇᴋ ᴀᴄᴛɪᴏɴ!", show_alert=True)
    
    # Calculate new position
    current_time = getattr(media, 'time', 0)
    new_time = max(0, min(current_time + seconds, media.duration_sec - 5))
    
    # Check if we're at the boundaries
    if new_time == 0 and seconds < 0:
        return await query.answer(f"⏮️ ᴀʟʀᴇᴀᴅʏ ᴀᴛ ᴛʜᴇ ʙᴇɢɪɴɴɪɴɢ!", show_alert=True)
    if new_time >= media.duration_sec - 5 and seconds > 0:
        return await query.answer(f"⏭️ ᴛᴏᴏ ᴄʟᴏꜱᴇ ᴛᴏ ᴛʜᴇ ᴇɴᴅ!", show_alert=True)
    
    # Perform seek
    options = {"expected_media": expected_media} if expected_media is not None else {}
    success = await tune.seek_stream(chat_id, int(new_time), **options)
    if success:
        # Format time display
        import time as time_module
        if media.duration_sec >= 3600:
            time_str = time_module.strftime('%H:%M:%S', time_module.gmtime(new_time))
        else:
            time_str = time_module.strftime('%M:%S', time_module.gmtime(new_time))
        
        # Use callback answer to avoid FloodWait
        await query.answer(f"✅ ꜱᴇᴇᴋᴇᴅ ᴛᴏ {time_str}", show_alert=True)
        
        # Try to send reply message with FloodWait handling and auto-delete after 5 seconds
        try:
            sent_msg = await query.message.reply_text(
                f"✅ ꜱᴇᴇᴋᴇᴅ ᴛᴏ {time_str}\n\n<blockquote>ʙʏ {user}</blockquote>"
            )
            # Auto-delete after 5 seconds
            await asyncio.sleep(5)
            try:
                await sent_msg.delete()
            except Exception:
                pass
        except FloodWait as e:
            # If rate limited, just skip the message since user already got feedback via callback
            pass
        except Exception:
            pass


async def handle_loop(query: types.CallbackQuery, chat_id: int, user: str, *, expected_media=None):
    async with tune.get_lock(chat_id):
        ensure_current_track(queue.get_current(chat_id), expected_media)
        current_loop = await db.get_loop(chat_id)
        new_loop = {0: 1, 1: 10}.get(current_loop, 0)
        await db.set_loop(chat_id, new_loop)
    
    # Cycle through loop modes: 0 (off) -> 1 (single) -> 10 (queue) -> 0
    if current_loop == 0:
        new_loop = 1
        text = "🔂 ʟᴏᴏᴘ: ꜱɪɴɢʟᴇ ᴛʀᴀᴄᴋ"
        message = f"🔂 ʟᴏᴏᴘ ᴍᴏᴅᴇ ꜱᴇᴛ ᴛᴏ <b>ꜱɪɴɢʟᴇ ᴛʀᴀᴄᴋ</b>"
    elif current_loop == 1:
        new_loop = 10
        text = "🔁 ʟᴏᴏᴘ: ǫᴜᴇᴜᴇ"
        message = f"🔁 ʟᴏᴏᴘ ᴍᴏᴅᴇ ꜱᴇᴛ ᴛᴏ <b>ǫᴜᴇᴜᴇ</b>"
    else:
        new_loop = 0
        text = "➡️ ʟᴏᴏᴘ: ᴏꜰꜰ"
        message = f"➡️ ʟᴏᴏᴘ ᴍᴏᴅᴇ <b>ᴅɪꜱᴀʙʟᴇᴅ</b>"
    
    await query.answer(text, show_alert=False)
    await query.message.reply_text(message)





@app.on_callback_query(filters.regex(r"^help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    await query.answer()
    
    # Handle plain "help" callback - show main menu
    if query.data == "help":
        try:
            # Try to edit as photo message first
            await query.edit_message_caption(
                caption=query.lang["help_menu"], 
                reply_markup=buttons.help_markup(query.lang)
            )
        except Exception:
            # Fallback to text edit if not a photo message
            try:
                await query.edit_message_text(
                    text=query.lang["help_menu"], 
                    reply_markup=buttons.help_markup(query.lang)
                )
            except Exception:
                pass
        return
    
    category = query.data.replace("help_", "")
    
    if category == "main":
        # Return to main help menu from category
        try:
            await query.edit_message_caption(
                caption=query.lang["help_menu"], 
                reply_markup=buttons.help_markup(query.lang)
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=query.lang["help_menu"], 
                    reply_markup=buttons.help_markup(query.lang)
                )
            except Exception:
                pass
        return

    # Handle all help categories
    help_texts = {
        "admins": query.lang["help_admins"],
        "auth": query.lang["help_auth"],
        "broadcast": query.lang["help_sudo"],  # Broadcast is sudo feature
        "blchat": query.lang["help_blchat"],
        "bluser": query.lang["help_bluser"],
        "loop": query.lang["help_loop"],
        "play": query.lang["help_play"],
        "queue": query.lang["help_queue"],
        "seek": query.lang["help_seek"],
        "ping": query.lang["help_ping"],
        "stats": query.lang["help_stats"],
        "sudo": query.lang["help_sudo"],
    }
    
    help_text = help_texts.get(category, query.lang["help_admins"])
    
    try:
        await query.edit_message_caption(
            caption=help_text,
            reply_markup=buttons.help_markup(query.lang, True),
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=help_text,
                reply_markup=buttons.help_markup(query.lang, True),
            )
        except Exception:
            pass


@app.on_callback_query(filters.regex("playmode") & ~app.bl_users)
@lang.language()
@admin_check
async def _playmode(_, query: types.CallbackQuery):
    await query.answer(query.lang["processing"], show_alert=True)
    chat_id = query.message.chat.id
    admin_only = await db.get_play_mode(chat_id)
    _language = "en"
    await db.set_play_mode(chat_id, admin_only)
    await query.edit_message_reply_markup(
        reply_markup=buttons.settings_markup(
            query.lang,
            not admin_only,
            _language,
            chat_id,
        )
    )
    