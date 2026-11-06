import asyncio
import importlib.util
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import wave


class TelegramDurationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_directory = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.previous_directory)
        os.chdir(self.temp.name)
        Path('downloads').mkdir()
        self.fixture = Path('fixture.wav')
        with wave.open(str(self.fixture), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b'\0\0' * 98000)  # 12.25 seconds.

        project = Path(__file__).resolve().parents[1]
        model_spec = importlib.util.spec_from_file_location(
            'duration_test_models', project / 'HasiiMusic/helpers/_dataclass.py')
        models = importlib.util.module_from_spec(model_spec)
        context = ModuleType('HasiiMusic')
        context.config = SimpleNamespace(DURATION_LIMIT=600)
        context.logger = logging.getLogger('telegram-duration-test')
        helpers = ModuleType('HasiiMusic.helpers')
        with patch.dict(sys.modules, {'duration_test_models': models}):
            model_spec.loader.exec_module(models)
        helpers.Media = models.Media
        helpers.buttons = SimpleNamespace()
        helpers.utils = SimpleNamespace()
        spec = importlib.util.spec_from_file_location(
            'telegram_duration_under_test', project / 'HasiiMusic/core/telegram.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'HasiiMusic': context, 'HasiiMusic.helpers': helpers}):
            spec.loader.exec_module(self.module)
        self.telegram = self.module.Telegram()
        self.sent = StatusMessage()

    def message(self, duration=0, cached=True):
        media = SimpleNamespace(
            file_unique_id='test_audio', file_name='track.wav',
            file_size=self.fixture.stat().st_size, title='Test track')
        if duration != 'missing':
            media.duration = duration
        destination = Path('downloads/test_audio.wav')
        if cached:
            shutil.copyfile(self.fixture, destination)

        async def download(*, file_name, progress):
            shutil.copyfile(self.fixture, file_name)
            return file_name

        return SimpleNamespace(
            audio=media, voice=None, video=None, document=None,
            link='https://t.me/example/123', download=download)

    async def test_recovers_missing_duration_from_cached_file(self):
        for duration in (0, None, 'missing', -1):
            with self.subTest(duration=duration):
                result = await self.telegram.download(self.message(duration), self.sent)
                self.assertEqual(result.duration_sec, 12)
                self.assertEqual(result.duration, '00:12')

    async def test_recovers_duration_after_new_download(self):
        result = await self.telegram.download(self.message(cached=False), self.sent)
        self.assertEqual(result.duration_sec, 12)
        self.assertEqual(result.duration, '00:12')
        self.assertTrue(Path(result.file_path).is_file())

    async def test_preserves_valid_telegram_duration(self):
        result = await self.telegram.download(self.message(duration=21), self.sent)
        self.assertEqual(result.duration_sec, 21)
        self.assertEqual(result.duration, '00:21')

    async def test_unreadable_duration_does_not_abort_playback(self):
        message = self.message()
        Path('downloads/test_audio.wav').write_bytes(b'not an audio file')
        with self.assertLogs('telegram-duration-test', level='WARNING'):
            result = await self.telegram.download(message, self.sent)
        self.assertEqual(result.duration_sec, 0)
        self.assertEqual(result.duration, '00:00')

    async def test_detected_duration_respects_existing_limit(self):
        self.module.config.DURATION_LIMIT = 10
        result = await self.telegram.download(self.message(), self.sent)
        self.assertIsNone(result)
        self.assertIn('limit', self.sent.text)

    async def test_document_without_duration_uses_downloaded_file(self):
        message = self.message(duration='missing')
        message.document, message.audio = message.audio, None
        result = await self.telegram.download(message, self.sent)
        self.assertEqual(result.duration_sec, 12)
        self.assertEqual(result.duration, '00:12')

    async def test_missing_ffprobe_does_not_abort_playback(self):
        with patch.dict(os.environ, {'PATH': self.temp.name}), \
                self.assertLogs('telegram-duration-test', level='WARNING'):
            result = await self.telegram.download(self.message(), self.sent)
        self.assertEqual(result.duration_sec, 0)

    @unittest.skipUnless(os.name == 'posix', 'Uses a POSIX executable fixture')
    async def test_invalid_probe_duration_does_not_abort_playback(self):
        for output in ('N/A', 'nan', 'inf'):
            with self.subTest(output=output):
                self.install_probe_script(f'print({output!r})\n')
                with self.assertLogs('telegram-duration-test', level='WARNING'):
                    result = await self.telegram.download(self.message(), self.sent)
                self.assertEqual(result.duration_sec, 0)

    @unittest.skipUnless(os.name == 'posix', 'Uses a POSIX executable fixture')
    async def test_cancellation_during_probe_never_returns_playable_media(self):
        self.install_blocking_probe()
        task = asyncio.create_task(self.telegram.download(self.message(), self.sent))
        try:
            pid = await self.wait_for_probe()
            query = SimpleNamespace(
                message=SimpleNamespace(id=self.sent.id),
                from_user=SimpleNamespace(mention='Test user'),
                lang={'dl_cancel': 'cancelled'},
                edit_message_text=self.sent.edit_text,
            )
            await self.telegram.cancel(query)
            done, _ = await asyncio.wait({task}, timeout=0.5)
            self.assertIn(task, done, 'Cancel must interrupt the duration probe')
            self.assertIsNone(await task)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            self.assertNotIn(self.sent.id, self.telegram.active_tasks)
        finally:
            if not task.done():
                task.cancel()
                await task

    @unittest.skipUnless(os.name == 'posix', 'Uses a POSIX executable fixture')
    async def test_probe_timeout_keeps_playback_available_and_reaps_child(self):
        self.install_blocking_probe()
        original_wait_for = asyncio.wait_for

        async def short_wait_for(awaitable, timeout):
            return await original_wait_for(awaitable, timeout=0.5)

        with patch.object(self.module.asyncio, 'wait_for', new=short_wait_for), \
                self.assertLogs('telegram-duration-test', level='WARNING'):
            result = await self.telegram.download(self.message(), self.sent)
        self.assertEqual(result.duration_sec, 0)
        pid = int(Path('probe.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def install_blocking_probe(self):
        self.install_probe_script(
            'import os, time\n'
            'from pathlib import Path\n'
            'Path("probe.pid").write_text(str(os.getpid()))\n'
            'time.sleep(60)\n')

    def install_probe_script(self, body):
        executable = Path('ffprobe').resolve()
        executable.write_text(f'#!{sys.executable}\n' + body)
        executable.chmod(0o755)
        environment = patch.dict(os.environ, {'PATH': str(executable.parent)})
        environment.start()
        self.addCleanup(environment.stop)

    async def wait_for_probe(self):
        for _ in range(200):
            if Path('probe.pid').exists():
                return int(Path('probe.pid').read_text())
            await asyncio.sleep(0.01)
        self.fail('ffprobe fixture did not start')


class StatusMessage:
    id = 123
    lang = {'dl_complete': 'downloaded in {0}', 'play_duration_limit': 'limit {0} minutes'}

    def __init__(self):
        self.text = ''

    async def edit_text(self, text, **kwargs):
        self.text = text

    async def stop_propagation(self):
        return None


if __name__ == '__main__':
    unittest.main()
