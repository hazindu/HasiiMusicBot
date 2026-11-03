import asyncio
import importlib.util
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

PROJECT = Path(__file__).resolve().parents[1]
REQUESTER_MODULE = None
helper_path = PROJECT / 'HasiiMusic/helpers/_requester.py'
if helper_path.exists():
    helper_spec = importlib.util.spec_from_file_location('HasiiMusic.helpers._requester', helper_path)
    REQUESTER_MODULE = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(REQUESTER_MODULE)


def load_module(name, path, context):
    spec = importlib.util.spec_from_file_location(name, PROJECT / path)
    module = importlib.util.module_from_spec(spec)
    modules = {'HasiiMusic': context, name: module}
    if REQUESTER_MODULE is not None:
        modules['HasiiMusic.helpers._requester'] = REQUESTER_MODULE
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class Database:
    def __init__(self, effects):
        self.client = SimpleNamespace(volume={})
        self.saved = {}
        self.paused = False

        async def pause(chat_id):
            effects.append('pause')

        async def resume(chat_id):
            effects.append('resume')

        self.client.pause = pause
        self.client.resume = resume

    async def get_call(self, chat_id):
        return True

    async def get_assistant(self, chat_id):
        return self.client

    async def playing(self, chat_id, paused=None):
        if paused is not None:
            self.paused = paused
        return not self.paused


class Component:
    def __init__(self, controller):
        self.controller = controller


class Player(Component):
    async def _play_media_impl(self, chat_id, message, media, seek_time=0):
        self.controller.played.append(media)

    async def play_media(self, chat_id, message, media, seek_time=0):
        async with self.controller.get_lock(chat_id):
            await self._play_media_impl(chat_id, message, media, seek_time)


class RequesterGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.requester = REQUESTER_MODULE
        self.effects = []
        self.db = Database(self.effects)
        self.context = ModuleType('HasiiMusic')
        self.context.db = self.db
        self.context.logger = logging.getLogger('requester-guards-test')
        for name in ('app', 'config', 'lang', 'preload', 'queue', 'yt'):
            setattr(self.context, name, SimpleNamespace())
        self.helpers = ModuleType('HasiiMusic.helpers')
        self.helpers.Media = type('Media', (), {})
        self.helpers.Track = type('Track', (), {})
        self.locks = {}
        self.controller = SimpleNamespace(
            get_lock=lambda chat_id: self.locks.setdefault(chat_id, asyncio.Lock()))
        controls = load_module('requester_call_controls', 'HasiiMusic/core/calls/controls.py', self.context)
        self.controls = controls.CallControls(self.controller)
        self.original = SimpleNamespace(id='same-track', message_id=12, time=0)
        self.current = self.original
        self.context.queue.get_current = lambda chat_id: self.current
        self.queue_module = load_module('requester_call_queue', 'HasiiMusic/core/calls/queue.py', self.context)
        self.call_queue = self.queue_module.CallQueue(self.controller)
        self.controller._pending_transitions = set()
        self.controller._track_index = {}
        self.controller._session_gen = {}

    async def assert_changed(self, awaitable):
        try:
            await awaitable
        except Exception as error:
            self.assertEqual(type(error).__name__, 'TrackChangedError')
        else:
            self.fail('A changed track must reject the requester operation')

    async def test_control_guards_check_identity_after_waiting_for_chat_lock(self):
        operations = [('pause', ()), ('resume', ()), ('stop', ())]
        if hasattr(self.controls, 'adjust_volume'):
            operations.append(('adjust_volume', (-5,)))
        for name, args in operations:
            with self.subTest(operation=name):
                self.current = self.original
                lock = self.controller.get_lock(-10)
                await lock.acquire()
                async def invoke():
                    return await getattr(self.controls, name)(
                        -10, *args, expected_media=self.original)
                task = asyncio.create_task(invoke())
                try:
                    await asyncio.sleep(0)
                    self.current = SimpleNamespace(**vars(self.original))
                finally:
                    lock.release()
                await self.assert_changed(task)
                self.assertEqual(self.effects, [])
                self.assertEqual(self.db.client.volume, {})
                self.assertEqual(self.db.saved, {})

    async def test_current_requester_can_pause_and_resume(self):
        self.assertTrue(await self.controls.pause(-10, expected_media=self.original))
        self.assertTrue(await self.controls.resume(-10, expected_media=self.original))
        self.assertEqual(self.effects, ['pause', 'resume'])

    async def test_queue_guards_reject_before_transition_state_changes(self):
        for name in ('play_next', 'play_previous', 'replay'):
            with self.subTest(operation=name):
                self.current = self.original
                self.controller._pending_transitions = {-10}
                lock = self.controller.get_lock(-10)
                await lock.acquire()
                async def invoke():
                    return await getattr(self.call_queue, name)(
                        -10, expected_media=self.original)
                task = asyncio.create_task(invoke())
                try:
                    await asyncio.sleep(0)
                    self.current = SimpleNamespace(**vars(self.original))
                finally:
                    lock.release()
                await self.assert_changed(task)
                self.assertEqual(self.controller._pending_transitions, {-10})
                self.assertEqual(self.controller._track_index, {})

    def facade(self, *, load_real_queue=False):
        name = 'requester_calls_facade'
        package_path = PROJECT / 'HasiiMusic/core/calls/__init__.py'
        spec = importlib.util.spec_from_file_location(name, package_path,
                                                    submodule_search_locations=[str(package_path.parent)])
        module = importlib.util.module_from_spec(spec)
        stubs = {'HasiiMusic': self.context, 'HasiiMusic.helpers': self.helpers, name: module}
        if REQUESTER_MODULE is not None:
            stubs['HasiiMusic.helpers._requester'] = REQUESTER_MODULE
        for suffix, values in {
            'utils': {'CallsUtils': Component, 'PyTgCallsErrorFilter': logging.Filter},
            'manager': {'CallsManager': Component},
            'player': {'CallPlayer': Player},
            'controls': {'CallControls': type(self.controls)},
            'queue': {'CallQueue': type(self.call_queue)},
        }.items():
            if load_real_queue and suffix == 'queue':
                continue
            component = ModuleType(f'{name}.{suffix}')
            component.__dict__.update(values)
            stubs[component.__name__] = component
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(module)
        controller = module.TgCall()
        controller.played = []
        self.facade_module = module
        return controller

    async def test_seek_guard_survives_real_queue_submodule_import(self):
        controller = self.facade(load_real_queue=True)
        self.assertIsInstance(self.facade_module.queue, ModuleType)
        controller._controls.seek_stream = AsyncMock(return_value=True)
        self.assertTrue(await controller.seek_stream(-10, 15, expected_media=self.original))
        controller._controls.seek_stream.assert_awaited_once_with(-10, 15)
        self.current = SimpleNamespace(**vars(self.original))
        with self.assertRaises(self.requester.TrackChangedError):
            await controller.seek_stream(-10, 20, expected_media=self.original)
        self.assertEqual(controller._controls.seek_stream.await_count, 1)

    async def test_facade_forwards_expected_track_to_each_guarded_operation(self):
        controller = self.facade()
        self.current = SimpleNamespace(**vars(self.original))
        operations = [('pause', ()), ('resume', ()), ('stop', ()),
                      ('play_next', ()), ('play_previous', ()), ('replay', ())]
        if hasattr(controller, 'adjust_volume'):
            operations.append(('adjust_volume', (-5,)))
        for name, args in operations:
            with self.subTest(operation=name):
                async def invoke():
                    return await getattr(controller, name)(
                        -10, *args, expected_media=self.original)
                await self.assert_changed(invoke())

    async def test_seek_facade_checks_changed_track_inside_lock(self):
        controller = self.facade()
        lock = controller.get_lock(-10)
        await lock.acquire()
        async def invoke():
            return await controller.seek_stream(-10, 15, expected_media=self.original)
        task = asyncio.create_task(invoke())
        try:
            await asyncio.sleep(0)
            self.current = SimpleNamespace(**vars(self.original))
        finally:
            lock.release()
        await self.assert_changed(task)
        self.assertEqual(controller.played, [])

    async def test_replay_keeps_lock_across_message_send_without_nested_acquisition(self):
        controller = self.facade()

        async def get_lang(chat_id):
            return {'play_again': 'Replay'}

        async def send_message(**kwargs):
            self.assertTrue(controller.get_lock(-10).locked())
            return SimpleNamespace(id=13)

        self.context.lang.get_lang = get_lang
        self.context.app.send_message = send_message
        await asyncio.wait_for(controller.replay(-10, expected_media=self.original), 0.5)
        self.assertEqual(controller.played, [self.original])

    async def test_play_next_keeps_expected_index_compatibility(self):
        transitions = []

        async def play_next_impl(chat_id):
            transitions.append(chat_id)

        self.call_queue._play_next_impl = play_next_impl
        self.controller._track_index[-10] = 3
        await self.call_queue.play_next(-10, 2)
        self.assertEqual(transitions, [])
        await self.call_queue.play_next(-10, 3, expected_media=self.original)
        self.assertEqual(transitions, [-10])

    async def test_lazy_playlist_batch_assigns_requester_before_enqueueing(self):
        tracks = [SimpleNamespace(), SimpleNamespace()]
        added = []

        async def playlist(*args, **kwargs):
            return tracks

        self.context.spotify = SimpleNamespace(valid=lambda url: True,
                                               is_playlist=lambda url: True, playlist=playlist)
        self.context.queue.add = lambda chat_id, track: added.append((track, track.requester_id))
        with patch.dict(sys.modules, {'HasiiMusic': self.context}):
            await self.call_queue._fetch_next_playlist_batch(
                -10, 'https://example.com/playlist', 'Display name', 30, requester_id=42)
        self.assertEqual(added, [(track, 42) for track in tracks])

    def test_pure_guard_uses_identity_and_preserves_unguarded_calls(self):
        self.assertIsNotNone(self.requester, 'Pure requester guard helper must exist')
        self.requester.ensure_current_track(self.original, None)
        self.requester.ensure_current_track(self.original, self.original)
        with self.assertRaises(self.requester.TrackChangedError):
            self.requester.ensure_current_track(SimpleNamespace(**vars(self.original)), self.original)


if __name__ == '__main__':
    unittest.main()
