"""
# ==============================================================================
# queue.py - Calls Queue and Transition Manager
# ==============================================================================
# This file handles playback transitions and queue management.
# Features:
# - Plays the next track when current ends
# - Handles loop mode logic
# - Lazily auto-fetches large Spotify playlists in the background
# ==============================================================================
"""

import asyncio
import re
from pyrogram import errors
from HasiiMusic import app, config, db, lang, logger, preload, queue, yt
from HasiiMusic.helpers._requester import ensure_current_track

class CallQueue:
    def __init__(self, controller):
        self.controller = controller

    async def replay(self, chat_id: int, *, expected_media=None) -> None:
        async with self.controller.get_lock(chat_id):
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            try:
                if not await db.get_call(chat_id):
                    return

                media = queue.get_current(chat_id)
                _lang = await lang.get_lang(chat_id)
                msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
                await self.controller._player._play_media_impl(chat_id, msg, media)
            except Exception as e:
                logger.error(f"Error in replay for {chat_id}: {e}", exc_info=True)

    async def play_next(self, chat_id: int, expected_index: int = None, *, expected_media=None) -> None:
        lock = self.controller.get_lock(chat_id)
        async with lock:
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            self.controller._pending_transitions.discard(chat_id)
            if expected_index is not None and self.controller._track_index.get(chat_id, 0) != expected_index:
                logger.info(f"Skipping stale play_next for {chat_id}")
                return
            
            self.controller._track_index[chat_id] = self.controller._track_index.get(chat_id, 0) + 1
            await self._play_next_impl(chat_id)

    async def play_previous(self, chat_id: int, *, expected_media=None) -> bool:
        lock = self.controller.get_lock(chat_id)
        async with lock:
            if expected_media is not None:
                ensure_current_track(queue.get_current(chat_id), expected_media)
            self.controller._pending_transitions.discard(chat_id)
            self.controller._track_index[chat_id] = self.controller._track_index.get(chat_id, 0) + 1
            
            media = queue.get_previous(chat_id)
            if not media:
                return False
            
            await self._play_next_impl(chat_id, is_previous=True)
            return True

    async def _play_next_impl(self, chat_id: int, is_previous: bool = False) -> None:
        try:
            if not await db.get_call(chat_id):
                return

            loop_mode = await db.get_loop(chat_id)

            if loop_mode == 1 and not is_previous:
                media = queue.get_current(chat_id)
                if media:
                    _lang = await lang.get_lang(chat_id)
                    try:
                        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
                        await self.controller._player._play_media_impl(chat_id, msg, media)
                    except errors.ChannelPrivate:
                        logger.warning(
                            f"Bot removed from {chat_id}, cleaning up")
                        try:
                            await self.controller._controls._stop_impl(chat_id)
                        except (AttributeError, Exception) as leave_ex:
                            logger.debug(
                                f"Could not leave call for {chat_id}: {leave_ex}")
                        await db.rm_chat(chat_id)
                    return

            if not is_previous:
                media = queue.get_next(chat_id)
            else:
                media = queue.get_current(chat_id)

            if not media and loop_mode == 10:
                # the queue is empty now; the played tracks are in history
                queue.requeue_history(chat_id)
                all_items = queue.get_all(chat_id)
                if all_items:
                    first_track = all_items[0]
                    _lang = await lang.get_lang(chat_id)
                    try:
                        msg = await app.send_message(chat_id=chat_id, text="🔁 Looping queue...")
                        if not first_track.file_path:
                            is_live = getattr(first_track, 'is_live', False)
                            lock = self.controller.get_lock(chat_id)
                            current_session = self.controller._session_gen.get(chat_id, 0)
                            lock.release()
                            try:
                                first_track.file_path = await yt.download(
                                    first_track.id,
                                    is_live=is_live,
                                    video=getattr(first_track, 'video', False),
                                )
                            finally:
                                await lock.acquire()
                            
                            if self.controller._session_gen.get(chat_id, 0) != current_session:
                                logger.info(f"Session invalidated during looping download for {chat_id}")
                                return
                            if queue.get_current(chat_id) != first_track:
                                logger.info(f"Queue altered during looping download for {chat_id}")
                                return
                        first_track.message_id = msg.id
                        await self.controller._player._play_media_impl(chat_id, msg, first_track)
                    except errors.ChannelPrivate:
                        logger.warning(
                            f"Bot removed from {chat_id}, cleaning up")
                        await self.controller._controls._stop_impl(chat_id)
                        await db.rm_chat(chat_id)
                    return

            try:
                if media and media.message_id:
                    await app.delete_messages(
                        chat_id=chat_id,
                        message_ids=media.message_id,
                        revoke=True,
                    )
                    media.message_id = 0
            except Exception as e:
                logger.debug(
                    f"Could not delete previous message in {chat_id}: {e}")

            if not media:
                if config.QUEUE_END_MESSAGE:
                    _lang = await lang.get_lang(chat_id)
                    try:
                        await app.send_message(
                            chat_id=chat_id,
                            text=_lang.get(
                                "queue_end_message", "✅ Queue finished. Stream ended automatically.")
                        )
                    except Exception as e:
                        logger.debug(
                            f"Could not send queue_end message in {chat_id}: {e}")
                return await self.controller._controls._stop_impl(chat_id)

            _lang = await lang.get_lang(chat_id)
            msg = None

            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", media.id) or not getattr(media, "thumbnail", None):
                try:
                    # use YouTube Music search for spotify tracks, regular YT for everything else
                    is_spotify_track = getattr(media, "playlist_type", None) in ("playlist", "album", "artist")
                    resolved = await yt.search(media.id, 0, music=is_spotify_track)
                    if resolved:
                        media.id = resolved.id
                        if resolved.thumbnail:
                            media.thumbnail = resolved.thumbnail
                        if resolved.duration_sec:
                            media.duration_sec = resolved.duration_sec
                            media.duration = resolved.duration
                except Exception:
                    pass

            if not media.file_path:
                is_live = getattr(media, 'is_live', False)
                lock = self.controller.get_lock(chat_id)
                current_session = self.controller._session_gen.get(chat_id, 0)
                lock.release()
                try:
                    media.file_path = await yt.download(
                        media.id,
                        is_live=is_live,
                        video=getattr(media, 'video', False),
                    )
                finally:
                    await lock.acquire()

                if self.controller._session_gen.get(chat_id, 0) != current_session:
                    logger.info(f"Session invalidated during play_next download for {chat_id}")
                    return
                if queue.get_current(chat_id) != media:
                    logger.info(f"Queue altered during play_next download for {chat_id}")
                    return
                if not media.file_path:
                    if len(queue.get_queue(chat_id)) > 1:
                        logger.warning(
                            f"Skipping unplayable track '{getattr(media, 'title', 'unknown')}' in {chat_id}")
                        return await self._play_next_impl(chat_id)
                    await self.controller._controls._stop_impl(chat_id)
                    if msg:
                        try:
                            await msg.edit_text(
                                _lang["error_no_file"].format(
                                    config.SUPPORT_CHAT)
                            )
                        except Exception:
                            pass
                    return

            try:
                msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])
            except errors.FloodWait as fw:
                # keep playback running even if the status message hits FloodWait
                logger.warning(
                    f"FloodWait in play_next for {chat_id}: skipping status message ({fw.value}s)")
                msg = None
            except errors.ChannelPrivate:
                logger.warning(f"Bot removed from {chat_id}, cleaning up")
                await self.controller._controls._stop_impl(chat_id)
                await db.rm_chat(chat_id)
                return
            except Exception as e:
                logger.error(
                    f"Failed to send play_next message for {chat_id}: {e}")
                msg = None

            media.message_id = msg.id if msg else 0
            if msg:
                await self.controller._player._play_media_impl(chat_id, msg, media)
            else:
                logger.info(
                    f"Playing next track for {chat_id} without message update")
                await self.controller._player._play_media_impl(chat_id, None, media)

            try:
                asyncio.create_task(
                    preload.start_preload(chat_id, count=2))
            except Exception as e:
                logger.debug(
                    f"Error starting preload after play_next for {chat_id}: {e}")

            # Autoload next playlist batch in background when reaching track 28 (up to PLAYLIST_MAX)
            pl_url = getattr(media, "playlist_url", None)
            pl_idx = getattr(media, "playlist_index", 0)
            pl_limit = getattr(config, "PLAYLIST_LIMIT", 30)
            pl_max = getattr(config, "PLAYLIST_MAX", 100)
            trigger_mod = max(1, pl_limit - 2) if pl_limit > 2 else 0
            if pl_url and pl_idx > 0 and pl_idx % pl_limit == (trigger_mod % pl_limit):
                next_offset = (pl_idx // pl_limit + 1) * pl_limit
                if next_offset < pl_max:
                    batch_limit = min(pl_limit, pl_max - next_offset)
                    asyncio.create_task(
                        self._fetch_next_playlist_batch(
                            chat_id=chat_id,
                            playlist_url=pl_url,
                            user=media.user,
                            offset=next_offset,
                            limit=batch_limit,
                            requester_id=getattr(media, "requester_id", None),
                        )
                    )
        except Exception as e:
            logger.error(
                f"Error in play_next for {chat_id}: {e}", exc_info=True)
            try:
                await self.controller._controls._stop_impl(chat_id)
            except Exception:
                pass

    async def _fetch_next_playlist_batch(
        self, chat_id: int, playlist_url: str, user: str, offset: int, limit: int = 30,
        requester_id: int | None = None,
    ) -> None:
        try:
            from HasiiMusic import spotify, queue
            if spotify.valid(playlist_url) and spotify.is_playlist(playlist_url):
                next_tracks = await spotify.playlist(limit, user, playlist_url, offset=offset)
                if next_tracks:
                    for track in next_tracks:
                        track.requester_id = requester_id
                        queue.add(chat_id, track)
                    logger.info(
                        f"📋 Autoloaded next {len(next_tracks)} playlist tracks (offset {offset}) for chat {chat_id}"
                    )
        except Exception as e:
            logger.debug(f"Could not autoload next playlist batch for {chat_id}: {e}")
