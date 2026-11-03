import asyncio
import importlib.util
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pyrogram import filters
from pyrogram.errors import QueryIdInvalid


PROJECT = Path(__file__).resolve().parents[1]


class RequesterControlsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context = ModuleType('HasiiMusic')
        self.helpers = ModuleType('HasiiMusic.helpers')
        self.helpers.__path__ = [str(PROJECT / 'HasiiMusic/helpers')]
        self.context.app = SimpleNamespace(
            sudoers={9001}, bl_users=filters.user([]),
            on_message=lambda *a, **kw: lambda f: f,
            on_callback_query=lambda *a, **kw: lambda f: f)
        self.context.lang = SimpleNamespace(language=lambda: lambda f: f)
        self.context.logger = logging.getLogger('requester-tests')
        self.context.config = SimpleNamespace(DURATION_LIMIT=3600, SUPPORT_CHAT='https://example.com',
                                              PLAYLIST_LIMIT=30, PLAYLIST_MAX=100)
        self.context.db = SimpleNamespace(
            is_auth=AsyncMock(return_value=False), get_admins=AsyncMock(return_value=set()),
            get_call=AsyncMock(return_value=True), is_logger=AsyncMock(return_value=False))
        self.context.tune = SimpleNamespace(get_lock=lambda chat_id: self.lock)
        self.lock = asyncio.Lock()
        self.helpers.admin_check = lambda f: f
        self.helpers.can_manage_vc = lambda f: f
        self.helpers.buttons = SimpleNamespace(play_queued=Mock(return_value=None))
        self.helpers.utils = SimpleNamespace(play_log=AsyncMock())
        for name in ('tg', 'yt', 'spotify', 'preload'):
            setattr(self.context, name, SimpleNamespace())
        self.modules = {'HasiiMusic': self.context, 'HasiiMusic.helpers': self.helpers}
        self.models = self.load('HasiiMusic.helpers._dataclass', 'HasiiMusic/helpers/_dataclass.py')
        self.modules['HasiiMusic.helpers._dataclass'] = self.models
        self.helpers.Track = self.models.Track
        self.helpers.Media = self.models.Media
        queue_module = self.load('HasiiMusic.helpers._queue', 'HasiiMusic/helpers/_queue.py')
        self.context.queue = queue_module.Queue()
        checker = ModuleType('HasiiMusic.helpers._play')
        checker.checkUB = lambda f: f
        self.modules['HasiiMusic.helpers._play'] = checker
        self.context.preload.start_preload = AsyncMock()
        self.context.tg.get_media = Mock(return_value=None)
        self.context.yt.is_direct_stream = Mock(return_value=False)
        self.context.spotify.valid = Mock(return_value=False)

    def load(self, name, relative):
        spec = importlib.util.spec_from_file_location(name, PROJECT / relative)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {**self.modules, name: module}):
            spec.loader.exec_module(module)
        return module

    def track(self, **kwargs):
        requester_id = kwargs.pop('requester_id', None)
        track = self.models.Track(id='AAAAAAAAAAA', channel_name='Artist', duration='04:00',
                                 duration_sec=240, title='Test track', url='https://example.com/track',
                                 file_path='/tmp/test.ogg', **kwargs)
        if requester_id is not None:
            track.requester_id = requester_id
        return track

    def query(self, user_id=42, chat_id=-10):
        return SimpleNamespace(
            data='controls status -10', from_user=SimpleNamespace(id=user_id, mention='Listener'),
            message=SimpleNamespace(chat=SimpleNamespace(id=chat_id),
                                    caption=SimpleNamespace(html='Track'), delete=AsyncMock(),
                                    reply_text=AsyncMock(return_value=None)),
            answer=AsyncMock(), edit_message_text=AsyncMock(),
            lang=json.loads((PROJECT / 'HasiiMusic/locales/en.json').read_text(encoding='utf-8')))

    def callbacks(self):
        return self.load('requester_callbacks', 'HasiiMusic/plugins/events/callbacks.py')

    async def test_current_requester_can_use_controls(self):
        self.context.queue.add(-10, self.track(requester_id=42))
        query = self.query()
        await self.callbacks()._controls(None, query)
        query.answer.assert_awaited_once_with()

    async def test_permission_moves_with_current_track(self):
        self.context.queue.add(-10, self.track(requester_id=42))
        self.context.queue.add(-10, self.track(requester_id=43))
        callbacks = self.callbacks()
        waiting = self.query(43)
        await callbacks._controls(None, waiting)
        self.assertTrue(waiting.answer.await_args.kwargs.get('show_alert'))
        self.context.queue.get_next(-10)
        old = self.query(42)
        await callbacks._controls(None, old)
        self.assertTrue(old.answer.await_args.kwargs.get('show_alert'))
        current = self.query(43)
        await callbacks._controls(None, current)
        current.answer.assert_awaited_once_with()

    async def test_display_mention_does_not_grant_permission(self):
        track = self.track()
        track.user = '<a href="tg://user?id=42">Listener</a>'
        self.context.queue.add(-10, track)
        query = self.query()
        await self.callbacks()._controls(None, query)
        self.assertTrue(query.answer.await_args.kwargs.get('show_alert'))

    async def test_owner_admin_and_authorized_keep_access(self):
        callbacks = self.callbacks()
        for role in ('owner', 'admin', 'authorized'):
            with self.subTest(role=role):
                self.context.db.get_admins.return_value = {42} if role == 'admin' else set()
                self.context.db.is_auth.return_value = role == 'authorized'
                query = self.query(9001 if role == 'owner' else 42)
                await callbacks._controls(None, query)
                query.answer.assert_awaited_once_with()

    async def test_forwarded_controls_do_not_target_original_group(self):
        self.context.queue.add(-10, self.track(requester_id=42))
        for user_id in (42, 9001):
            with self.subTest(user_id=user_id):
                query = self.query(user_id, chat_id=-20)
                await self.callbacks()._controls(None, query)
                self.assertTrue(query.answer.await_args.kwargs.get('show_alert'))

    async def test_requester_actions_pass_guard_to_playback_operations(self):
        current = self.track(requester_id=42)
        self.context.queue.add(-10, current)
        self.context.db.playing = AsyncMock(return_value=True)
        self.context.tune.get_volume = Mock(return_value=100)
        self.helpers.buttons.controls = Mock(return_value=None)
        callbacks = self.callbacks()
        for action, method in (('pause', 'pause'), ('resume', 'resume'), ('replay', 'replay'),
                               ('stop', 'stop'), ('skip', 'play_next'), ('previous', 'play_previous')):
            with self.subTest(action=action):
                operation = AsyncMock(return_value=True)
                setattr(self.context.tune, method, operation)
                self.context.db.playing.return_value = action != 'resume'
                query = self.query()
                query.data = f'controls {action} -10'
                await callbacks._controls(None, query)
                operation.assert_awaited_once_with(-10, expected_media=current)

    async def test_changed_track_is_reported_without_performing_action(self):
        current = self.track(requester_id=42)
        self.context.queue.add(-10, current)
        self.context.db.playing = AsyncMock(return_value=True)
        callbacks = self.callbacks()
        self.context.tune.pause = AsyncMock(side_effect=callbacks.TrackChangedError())
        query = self.query()
        query.data = 'controls pause -10'
        await callbacks._controls(None, query)
        self.assertEqual(query.answer.await_args.args[0], query.lang['play_expired'])

    async def test_expired_callback_during_changed_track_feedback_is_ignored(self):
        self.context.queue.add(-10, self.track(requester_id=42))
        self.context.db.playing = AsyncMock(return_value=True)
        callbacks = self.callbacks()
        self.context.tune.pause = AsyncMock(side_effect=callbacks.TrackChangedError())
        query = self.query()
        query.data = 'controls pause -10'
        query.answer.side_effect = [None, QueryIdInvalid()]
        await callbacks._controls(None, query)

    async def test_requester_does_not_gain_force_queue_permission(self):
        self.context.queue.add(-10, self.track(requester_id=42))
        query = self.query()
        query.data = 'controls force -10 next'
        await self.callbacks()._controls(None, query)
        self.assertTrue(query.answer.await_args.kwargs.get('show_alert'))

    async def test_loop_rechecks_track_after_waiting_for_lock(self):
        current = self.track(requester_id=42)
        self.context.queue.add(-10, current)
        self.context.queue.add(-10, self.track(requester_id=43))
        self.context.db.set_loop = AsyncMock()
        callbacks = self.callbacks()
        await self.lock.acquire()
        task = asyncio.create_task(callbacks.handle_loop(self.query(), -10, 'Listener', expected_media=current))
        try:
            await asyncio.sleep(0)
            self.context.queue.get_next(-10)
        finally:
            self.lock.release()
        with self.assertRaises(callbacks.TrackChangedError):
            await task
        self.context.db.set_loop.assert_not_awaited()

    def message(self):
        return SimpleNamespace(
            chat=SimpleNamespace(id=-10), from_user=SimpleNamespace(id=42, mention='Listener'),
            command=['play', 'test track'], reply_to_message=None,
            delete=AsyncMock(), react=AsyncMock(), reply_text=AsyncMock(return_value=SimpleNamespace(
                id=50, edit_text=AsyncMock())),
            lang={'play_emoji': '🎵', 'play_searching': '{} Searching',
                  'play_queued': '{} {} {} {} {}', 'play_now': 'Play now'})

    async def run_play(self, message, **kwargs):
        self.context.tune.play_media = AsyncMock()
        plugin = self.load('requester_play', 'HasiiMusic/plugins/playback/play.py')
        with patch.dict(sys.modules, self.modules):
            await plugin.play_hndlr(None, message, **kwargs)

    async def test_search_result_is_attributed_to_command_sender(self):
        track = self.track()
        self.context.yt.search = AsyncMock(return_value=track)
        await self.run_play(self.message())
        self.assertEqual(getattr(self.context.queue.get_current(-10), 'requester_id', None), 42)

    async def test_telegram_reply_is_attributed_to_command_sender_not_uploader(self):
        media = self.models.Media(id='file', duration='04:00', duration_sec=240,
                                 file_path='/tmp/test.ogg', message_id=1,
                                 title='Test file', url='https://example.com/file')
        self.context.tg.get_media.return_value = object()
        self.context.tg.download = AsyncMock(return_value=media)
        message = self.message()
        message.reply_to_message = SimpleNamespace(from_user=SimpleNamespace(id=43))
        await self.run_play(message)
        self.assertEqual(getattr(media, 'requester_id', None), 42)

    async def test_every_initial_playlist_track_has_requester(self):
        for active in (False, True):
            with self.subTest(active=active):
                self.context.queue.clear(-10)
                self.context.db.get_call.return_value = active
                tracks = [self.track() for _ in range(3)]
                self.context.yt.playlist = AsyncMock(return_value=tracks[:])
                await self.run_play(self.message(), url='https://example.com/playlist')
                self.assertEqual([getattr(item, 'requester_id', None) for item in tracks], [42, 42, 42])
                self.assertEqual(len(self.context.queue.get_queue(-10)), 3)

    async def test_direct_stream_has_requester(self):
        self.context.yt.is_direct_stream.return_value = True
        await self.run_play(self.message(), url='https://example.com/live.m3u8')
        self.assertEqual(getattr(self.context.queue.get_current(-10), 'requester_id', None), 42)

    async def test_force_queue_mutation_uses_chat_lock(self):
        track = self.track()
        self.context.yt.search = AsyncMock(return_value=track)
        original_force = self.context.queue.force_add

        def force_add(chat_id, item):
            self.assertTrue(self.lock.locked())
            return original_force(chat_id, item)

        self.context.queue.force_add = force_add
        await self.run_play(self.message(), force=True)
        self.assertIs(self.context.queue.get_current(-10), track)

    async def test_cached_search_drops_requester_identity(self):
        cached = self.track()
        cached.requester_id = 43
        cached.user = 'Earlier listener'
        search = self.load('requester_search', 'HasiiMusic/core/youtube/search.py')
        searcher = search.Searcher(SimpleNamespace())
        searcher.search_cache['test'] = (cached, asyncio.get_running_loop().time())
        fresh = await searcher.search('test', 99)
        self.assertIsNone(getattr(fresh, 'requester_id', None))
        self.assertEqual(cached.requester_id, 43)
        self.assertIsNot(fresh, cached)

    def test_requester_identity_is_part_of_both_media_models(self):
        for model in (self.models.Media, self.models.Track):
            with self.subTest(model=model.__name__):
                self.assertIn('requester_id', model.__dataclass_fields__)


if __name__ == '__main__':
    unittest.main()
