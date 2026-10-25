"""Standalone app configuration: no adjacent .env and no real user-data writes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from utils import app_paths, settings_utils, history_utils

class SettingsStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app_dir = self.root / 'install'
        self.app_dir.mkdir()
        self.data = self.root / 'profile' / 'APKBuilder'
        self.settings_file = self.data / 'settings.json'
        self.legacy = self.app_dir / '.env'
        for target, name, value in (
            (settings_utils, 'SETTINGS_FILE', self.settings_file),
            (settings_utils, 'LEGACY_SETTINGS_FILE', self.legacy),
            (history_utils, 'HISTORY_FILE', self.data / 'build_history.json'),
            (history_utils, 'LEGACY_HISTORY_FILE', self.app_dir / 'build_history.json'),
        ):
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_fresh_install_loads_without_env_or_profile(self):
        self.assertEqual(settings_utils.load_settings(), {})
        self.assertEqual(history_utils.get_history(), [])
        self.assertFalse(self.data.exists())
        self.assertEqual(list(self.app_dir.iterdir()), [])

    def test_save_creates_only_per_user_settings_and_reloads(self):
        settings_utils.save_settings({'GIT_BRANCH': 'release', 'SLACK_ENABLED': 'false', 'EMAIL_PASSWORD': 'secret'})
        self.assertEqual(json.loads(self.settings_file.read_text())['GIT_BRANCH'], 'release')
        self.assertEqual(list(self.app_dir.iterdir()), [])
        os.environ.clear()
        self.assertEqual(settings_utils.load_settings()['EMAIL_PASSWORD'], 'secret')
        self.assertFalse(self.legacy.exists())

    def test_saved_settings_override_environment(self):
        settings_utils.save_settings({'GIT_BRANCH': 'saved'})
        os.environ['GIT_BRANCH'] = 'environment'
        self.assertEqual(settings_utils.load_settings()['GIT_BRANCH'], 'saved')

    def test_legacy_env_import_is_read_only_and_saved_in_profile(self):
        self.legacy.write_text('GIT_BRANCH=legacy\nSLACK_WEBHOOK=legacy-secret\n', encoding='utf-8')
        original = self.legacy.read_bytes()
        self.assertEqual(settings_utils.load_settings()['GIT_BRANCH'], 'legacy')
        self.assertFalse(self.data.exists())
        settings_utils.save_settings({'GIT_BRANCH': 'updated'})
        saved = json.loads(self.settings_file.read_text())
        self.assertEqual(saved['GIT_BRANCH'], 'updated')
        self.assertEqual(saved['SLACK_WEBHOOK'], 'legacy-secret')
        self.assertEqual(self.legacy.read_bytes(), original)

    def test_cleared_settings_are_not_restored_from_legacy_env(self):
        self.legacy.write_text('SLACK_WEBHOOK=old-secret\n', encoding='utf-8')
        settings_utils.save_settings({'SLACK_WEBHOOK': ''})
        self.assertEqual(settings_utils.load_settings()['SLACK_WEBHOOK'], '')

    def test_invalid_json_is_reported_and_not_overwritten(self):
        self.data.mkdir(parents=True)
        self.settings_file.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            settings_utils.save_settings({'GIT_BRANCH': 'main'})
        self.assertEqual(self.settings_file.read_text(), '{broken')

    def test_invalid_settings_schema_is_rejected(self):
        self.data.mkdir(parents=True)
        for invalid in ([], {'SLACK_ENABLED': True}, {'GIT_BRANCH': None}):
            self.settings_file.write_text(json.dumps(invalid), encoding='utf-8')
            with self.assertRaises(ValueError):
                settings_utils.load_settings()

    def test_interrupted_replace_preserves_previous_settings_and_environment(self):
        settings_utils.save_settings({'GIT_BRANCH': 'stable'})
        original = self.settings_file.read_bytes()
        with patch.object(settings_utils.os, 'replace', side_effect=OSError('simulated failure')):
            with self.assertRaises(OSError):
                settings_utils.save_settings({'GIT_BRANCH': 'new'})
        self.assertEqual(self.settings_file.read_bytes(), original)
        self.assertEqual(os.environ['GIT_BRANCH'], 'stable')
        self.assertFalse(list(self.data.glob('*.tmp')))

    def test_history_migrates_on_write_without_changing_install_directory(self):
        legacy = self.app_dir / 'build_history.json'
        legacy.write_text(json.dumps([{'id': 'old', 'project_name': 'Existing'}]), encoding='utf-8')
        original = legacy.read_bytes()
        self.assertEqual(history_utils.get_history()[0]['id'], 'old')
        history_utils.add_entry('hurryApp', 'Customer', 'release', 'session', 'app.apk', {})
        self.assertEqual(len(history_utils.get_history()), 2)
        self.assertTrue((self.data / 'build_history.json').is_file())
        self.assertEqual(legacy.read_bytes(), original)

    def test_user_data_location_is_independent_of_executable_location(self):
        with patch.dict(os.environ, LOCALAPPDATA=str(self.root / 'local'), XDG_DATA_HOME=str(self.root / 'local')):
            expected = self.root / 'local' / 'APKBuilder'
            with patch.object(app_paths.sys, 'executable', str(self.app_dir / 'first.exe')):
                self.assertEqual(app_paths.user_data_dir(), expected)
            with patch.object(app_paths.sys, 'executable', str(self.root / 'elsewhere' / 'second.exe')):
                self.assertEqual(app_paths.user_data_dir(), expected)

if __name__ == '__main__':
    unittest.main()
