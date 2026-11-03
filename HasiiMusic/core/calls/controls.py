"""
# ==============================================================================
# controls.py - Calls Playback Controls
# ==============================================================================
# This file manages playback controls for PyTgCalls.
# Features:
# - Pause, Resume, Stop
# - Seek stream functionality
# ==============================================================================
"""

import asyncio
from ntgcalls import ConnectionNotFound
from pytgcalls import exceptions
from HasiiMusic import app, db, logger, preload, queue, lang
from HasiiMusic.helpers._requester import ensure_current_track

class CallControls:
    def __init__(self, controller):
        self.controller = controller

    async def pause(self, chat_id: int, *, expected_media=None) -> bool:
        async with self.controller.get_lock(chat_id):
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            client = await db.get_assistant(chat_id)
            try:
                await client.pause(chat_id)
                await db.playing(chat_id, paused=True)
                return True
            except (ConnectionNotFound, exceptions.NotInCallError):
                await db.playing(chat_id, paused=False)
                await db.remove_call(chat_id)
                queue.clear(chat_id)
                logger.warning(
                    f"Pause requested but assistant not in call for {chat_id}, syncing state")
                return False
            except Exception as e:
                await db.playing(chat_id, paused=False)
                logger.error(f"Pause failed for {chat_id}: {e}")
                return False

    async def resume(self, chat_id: int, *, expected_media=None) -> bool:
        async with self.controller.get_lock(chat_id):
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            client = await db.get_assistant(chat_id)
            try:
                await client.resume(chat_id)
                await db.playing(chat_id, paused=False)
                return True
            except (ConnectionNotFound, exceptions.NotInCallError):
                await db.playing(chat_id, paused=False)
                await db.remove_call(chat_id)
                queue.clear(chat_id)
                logger.warning(
                    f"Resume requested but assistant not in call for {chat_id}, syncing state")
                return False
            except Exception as e:
                logger.error(f"Resume failed for {chat_id}: {e}")
                return False

    async def stop(self, chat_id: int, *, expected_media=None) -> None:
        async with self.controller.get_lock(chat_id):
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            await self._stop_impl(chat_id)

    async def _stop_impl(self, chat_id: int) -> None:
        self.controller._session_gen[chat_id] = self.controller._session_gen.get(chat_id, 0) + 1
        client = await db.get_assistant(chat_id)

        # Cancel any active preload tasks when stopping
        try:
            await preload.cancel_preload(chat_id)
        except Exception as e:
            logger.debug(f"Error cancelling preload for {chat_id}: {e}")

        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except Exception as e:
            logger.warning(f"Error clearing queue/call for {chat_id}: {e}")

        try:
            await client.leave_call(chat_id, close=False)
            # Small delay to let group call state stabilize after leaving
            await asyncio.sleep(0.5)
        except (ConnectionNotFound, exceptions.NotInCallError):
            # the userbot is already out of the call
            pass
        except Exception as e:
            # unexpected errors
            error_msg = str(e).lower()
            if not any(ignore in error_msg for ignore in [
                "not in a call",
                "not in the group call",
                "groupcall_forbidden",
                "no active group call",
                "call was already stopped",
                "call already disconnected"
            ]):
                logger.warning(f"Error leaving call for {chat_id}: {e}")

    async def seek_stream(self, chat_id: int, seconds: int) -> bool:
        """seek to a position in the current stream"""
        try:
            if not await db.get_call(chat_id):
                return False

            media = queue.get_current(chat_id)
            if not media or getattr(media, "is_live", False):
                return False

            _lang = await lang.get_lang(chat_id)

            media.time = seconds

            try:
                msg = await app.get_messages(chat_id, media.message_id)
            except Exception:
                msg = None

            if not msg:
                _lang = await lang.get_lang(chat_id)
                msg = await app.send_message(chat_id=chat_id, text=_lang["seeking"])

            await self.controller._player._play_media_impl(chat_id, msg, media, seek_time=seconds)
            return True
        except Exception as e:
            logger.warning(f"Seek stream failed for {chat_id}: {e}")
            return False
