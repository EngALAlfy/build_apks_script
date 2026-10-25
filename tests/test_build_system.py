import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from bin import constants
from modules.build_service import BuildPlan, BuildService
from modules import git_module, upload_module, file_module
from modules.process_runner import run_command, BuildCancelled, cancel
from utils import history_utils

class BuildSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.history = patch.object(history_utils, 'HISTORY_FILE', self.root / 'history.json')
        self.history.start()
        self.env = patch.dict(os.environ, {'MEGA_ENABLED': 'false', 'FTP_ENABLED': 'false',
                                          'DISCORD_ENABLED': 'false', 'EMAIL_ENABLED': 'false'})
        self.env.start()
        constants.stop_requested = False

    def tearDown(self):
        constants.stop_requested = False
        self.env.stop()
        self.history.stop()
        self.temp.cleanup()

    def plan(self, **updates):
        settings = dict(GIT_WORKSPACE=str(self.root / 'source'), RESULT_WORKSPACE=str(self.root / 'output'),
                        GIT_BRANCH='main', GIT_USER='example', MEGA_ENABLED='false', FTP_ENABLED='false',
                        DISCORD_ENABLED='false', EMAIL_ENABLED='false')
        settings.update(updates)
        return BuildPlan(('hurryApp',), ('release',), settings)

    def final_event(self, service):
        events = []
        while not service.events.empty():
            events.append(service.events.get_nowait())
        return [data for kind, data in events if kind == 'finished'][-1]

    def record_build(self, project, stamp, on_stage, on_artifact):
        artifact = self.root / 'release.apk'
        artifact.write_bytes(b'APK')
        on_stage('Building release')
        on_artifact('release', str(artifact))
        return {'release': str(artifact)}

    def test_validation_collects_actionable_errors(self):
        plan = BuildPlan((), (), {'GIT_BRANCH': '-bad', 'SMTP_PORT': 'wrong', 'EMAIL_ENABLED': 'true'})
        with patch('modules.build_service.shutil.which', return_value=None):
            errors = plan.validate()
        self.assertGreaterEqual(len(errors), 8)
        self.assertTrue(any('SMTP port' in e for e in errors))

    def test_local_only_build_records_artifact(self):
        service = BuildService()
        with patch('modules.build_service.build_project_module.build_project', side_effect=self.record_build):
            service._run(self.plan())
        self.assertEqual(self.final_event(service)['state'], 'Complete')
        self.assertEqual(len(history_utils.get_history()), 1)
        self.assertEqual(history_utils.get_history()[0]['urls'], {})

    def test_partial_build_preserves_completed_artifact_and_reports_failure(self):
        def partial(*args):
            self.record_build(*args)
            raise RuntimeError('second format failed')
        service = BuildService()
        with patch('modules.build_service.build_project_module.build_project', side_effect=partial):
            service._run(self.plan())
        final = self.final_event(service)
        self.assertEqual((final['state'], final['count']), ('Failed', 1))
        self.assertEqual(len(history_utils.get_history()), 1)

    def test_distribution_failure_keeps_local_history_and_reports_warning(self):
        service = BuildService()
        with patch('modules.build_service.build_project_module.build_project', side_effect=self.record_build), patch.object(upload_module, 'mass_upload', side_effect=RuntimeError('offline')):
            service._run(self.plan(FTP_ENABLED='true'))
        self.assertEqual(self.final_event(service)['state'], 'Warning')
        self.assertEqual(len(history_utils.get_history()), 1)

    def test_cancelled_build_is_never_reported_successful(self):
        service = BuildService()
        with patch('modules.build_service.build_project_module.build_project', side_effect=BuildCancelled()):
            service._run(self.plan())
        self.assertEqual(self.final_event(service)['state'], 'Cancelled')

    def test_history_concurrent_writes_and_updates_are_atomic(self):
        def add(index):
            return history_utils.add_entry('hurryApp', 'Customer App', 'release', str(index), 'a.apk', {})
        with ThreadPoolExecutor(max_workers=5) as executor:
            ids = list(executor.map(add, range(30)))
        self.assertEqual(len(history_utils.get_history()), 30)
        self.assertEqual(len(set(ids)), 30)
        history_utils.update_entry(ids[0], urls={'ftp': 'https://example.com/a.apk'})
        self.assertTrue(any(e['urls'] for e in history_utils.get_history()))
        history_utils.remove_entry(ids[0])
        self.assertEqual(len(history_utils.get_history()), 29)

    def test_corrupt_history_is_not_silently_overwritten(self):
        target = self.root / 'history.json'
        target.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            history_utils.add_entry('hurryApp', 'App', 'release', 'now', 'a.apk', {})
        self.assertEqual(target.read_text(), '{broken')

    def test_dirty_git_repository_is_preserved(self):
        repo = self.root / 'hurryApp'
        repo.mkdir()
        subprocess.run(['git', 'init', str(repo)], capture_output=True, check=True)
        local_file = repo / 'local.txt'
        local_file.write_text('keep my changes')
        with patch.dict(os.environ, GIT_WORKSPACE=str(self.root)), patch.object(git_module, 'run_command') as command:
            with self.assertRaisesRegex(ValueError, 'local changes'):
                git_module.git_clone('hurryApp')
            command.assert_not_called()
        self.assertEqual(local_file.read_text(), 'keep my changes')

    def test_streaming_subprocess_propagates_failure_and_clears_handle(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, 'exit code 7'):
                run_command([sys.executable, '-c', "print('streamed output'); raise SystemExit(7)"], self.root, 'Test')
        self.assertIn('streamed output', output.getvalue())
        self.assertIsNone(constants.current_process)

    def test_active_process_is_cancelled_and_handle_cleared(self):
        result = []
        def work():
            try:
                run_command([sys.executable, '-c', 'import time; time.sleep(30)'], self.root, 'Cancellation test')
            except Exception as exc:
                result.append(exc)
        worker = threading.Thread(target=work)
        worker.start()
        deadline = time.monotonic() + 5
        while constants.current_process is None and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        try:
            self.assertIsNotNone(constants.current_process)
        finally:
            cancel()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], BuildCancelled)
        self.assertIsNone(constants.current_process)

    def test_secret_redaction_covers_webhook_and_git_credentials(self):
        from utils.settings_utils import redact
        with patch.dict(os.environ, MEGA_PASSWORD='test-secret'):
            text = redact('test-secret https://user:token@github.com /api/webhooks/123/hidden-token?wait=true')
        self.assertNotIn('test-secret', text)
        self.assertNotIn('user:token', text)
        self.assertNotIn('hidden-token', text)

    def test_cancelled_command_does_not_start(self):
        constants.stop_requested = True
        with self.assertRaises(BuildCancelled), patch('modules.process_runner.subprocess.Popen') as popen:
            run_command(['git', 'status'], self.root, 'Test')
        popen.assert_not_called()

    def test_appbundle_upload_keeps_aab_extension(self):
        artifact = self.root / 'app.aab'
        artifact.write_bytes(b'AAB')
        class FakeFTP:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def login(self, **kwargs): pass
            def cwd(self, path): pass
            def storbinary(self, command, stream, callback):
                self_test.assertTrue(command.endswith('.aab'))
                callback(stream.read())
        self_test = self
        with patch.dict(os.environ, FTP_HOST='example.com', FTP_USER='user', FTP_PASS='pass', FTP_BASE_URL='https://example.com'), patch.object(upload_module, 'FTP', FakeFTP):
            url = upload_module.upload_to_ftp('hurryApp', 'appbundle', 'now', str(artifact))
        self.assertTrue(url.endswith('.aab'))

    def test_cleanup_rejects_files_outside_artifact_directory(self):
        from modules.artifact_service import delete_artifact
        artifact = self.root / 'external.apk'
        artifact.write_bytes(b'keep')
        entry_id = history_utils.add_entry('hurryApp', 'App', 'release', 'now', str(artifact), {})
        with self.assertRaisesRegex(ValueError, 'outside'):
            delete_artifact(entry_id, str(self.root / 'output'))
        self.assertTrue(artifact.exists())
        self.assertEqual(len(history_utils.get_history()), 1)

    def test_cleanup_failure_retains_record_for_retry(self):
        from modules.artifact_service import delete_artifact
        artifact = self.root / 'release.apk'
        artifact.write_bytes(b'APK')
        entry_id = history_utils.add_entry('hurryApp', 'App', 'release', 'now', str(artifact), {}, mega_handles={'mega': 'tracked'})
        with patch.object(upload_module, 'delete_from_mega', return_value=False):
            errors = delete_artifact(entry_id, str(self.root))
        self.assertTrue(errors)
        self.assertFalse(artifact.exists())
        self.assertEqual(len(history_utils.get_history()), 1)
        with patch.object(upload_module, 'delete_from_mega', return_value=True):
            self.assertEqual(delete_artifact(entry_id, str(self.root)), [])
        self.assertEqual(history_utils.get_history(), [])

    def test_artifact_collection_uses_explicit_paths(self):
        source = self.root / 'source' / 'hurryApp'
        apk = source / 'build/app/outputs/flutter-apk/app-release.apk'
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b'APK')
        (source / 'pubspec.yaml').write_text('version: 2.0.0+10')
        before = Path.cwd()
        with patch.dict(os.environ, GIT_WORKSPACE=str(self.root / 'source'), RESULT_WORKSPACE=str(self.root / 'output')):
            result = file_module.copy_files('hurryApp', 'session', 'release')
        self.assertEqual(Path(result).read_bytes(), b'APK')
        self.assertIn('2.0.0+10', result)
        self.assertEqual(Path.cwd(), before)

if __name__ == '__main__':
    unittest.main()
