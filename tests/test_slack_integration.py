"""Slack regression tests: every HTTP request is mocked."""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from bin import constants
from modules import slack_module
from modules.build_service import BuildPlan, BuildService
from utils import history_utils, settings_utils

WEBHOOK = 'https://hooks.slack.com/services/TTEST/BTEST/test-secret'

class SlackTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, SLACK_ENABLED='true', SLACK_WEBHOOK=WEBHOOK,
                              GIT_BRANCH='release/test', DISCORD_ENABLED='false', EMAIL_ENABLED='false')
        self.env.start()
        constants.stop_requested = False

    def tearDown(self):
        self.env.stop()
        constants.stop_requested = False

    def send(self):
        return slack_module.send_to_slack('hurryApp', 'release', {'mega': 'https://example.com/app.apk'}, 'session', 'private-folder/app.apk')

    def test_disabled_integration_does_not_make_requests(self):
        with patch.dict(os.environ, SLACK_ENABLED='false'), patch.object(slack_module.requests, 'post') as post:
            self.assertIsNone(self.send())
            post.assert_not_called()

    def test_slack_and_govslack_webhook_validation(self):
        self.assertTrue(slack_module.valid_webhook_url(WEBHOOK))
        self.assertTrue(slack_module.valid_webhook_url(WEBHOOK.replace('slack.com', 'slack-gov.com')))
        for url in ('http://hooks.slack.com/services/T/B/secret', 'https://example.com/services/T/B/secret',
                    WEBHOOK + '?query=secret', WEBHOOK + '#fragment', 'https://hooks.slack.com.attacker.com/services/T/B/secret',
                    'https://user:password@hooks.slack.com/services/T/B/secret', ''):
            self.assertFalse(slack_module.valid_webhook_url(url), url)

    def test_invalid_webhook_fails_without_transmitting(self):
        with patch.dict(os.environ, SLACK_WEBHOOK='https://example.com/secret'), patch.object(slack_module.requests, 'post') as post:
            self.assertFalse(self.send())
            post.assert_not_called()

    def test_success_posts_rich_message_once_with_bounded_timeout(self):
        with patch.object(slack_module.requests, 'post', return_value=Mock(status_code=200, text='ok')) as post:
            self.assertTrue(self.send())
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args, (WEBHOOK,))
        self.assertEqual(kwargs['timeout'], (5, 20))
        self.assertFalse(kwargs['allow_redirects'])
        payload = kwargs['json']
        self.assertIn('Customer App', payload['text'])
        self.assertIn('RELEASE', payload['text'])
        self.assertIn('https://example.com/app.apk', str(payload))
        self.assertNotIn('private-folder', str(payload))
        self.assertNotIn('test-secret', str(payload))
        self.assertFalse(payload['unfurl_links'])

    def test_unexpected_acknowledgements_and_http_failures_are_not_retried(self):
        for status, body in ((200, 'not_ok'), (403, 'action_prohibited'), (404, 'no_service'),
                             (429, 'rate_limited'), (500, 'server_error'), (302, 'redirect')):
            with self.subTest(status=status), patch.object(slack_module.requests, 'post', return_value=Mock(status_code=status, text=body)) as post:
                self.assertFalse(self.send())
                post.assert_called_once()

    def test_transport_errors_do_not_expose_credentials(self):
        for error in (requests.Timeout(WEBHOOK), requests.ConnectionError(WEBHOOK)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch.object(slack_module.requests, 'post', side_effect=error) as post:
                self.assertFalse(self.send())
            self.assertNotIn('test-secret', output.getvalue())
            self.assertNotIn(WEBHOOK, output.getvalue())
            post.assert_called_once()

    def test_markup_and_unsafe_links_cannot_be_injected(self):
        payload = slack_module.build_payload('<!channel>', 'release', {
            'bad': 'javascript:alert(1)', 'credentials': 'https://user:pass@example.com/file',
            'injected': 'https://example.com/a|<!channel>', 'mega': 'https://example.com/a?x=1&y=2'}, 'session')
        links = payload['blocks'][2]['text']['text']
        self.assertNotIn('javascript', links)
        self.assertNotIn('user:pass', links)
        self.assertNotIn('<!channel>', payload['text'])
        self.assertIn('&amp;', links)
        with self.assertRaises(ValueError):
            slack_module.build_payload('hurryApp', 'release', {'ftp': 'ftp://example.com/file.apk'}, 'session')

    def test_redaction_handles_webhooks_not_in_environment(self):
        with patch.dict(os.environ, SLACK_WEBHOOK=''):
            for url in (WEBHOOK, WEBHOOK.replace('slack.com', 'slack-gov.com')):
                self.assertNotIn('test-secret', settings_utils.redact('Failed request: ' + url))
        self.assertIn('SLACK_WEBHOOK', settings_utils.SECRET_KEYS)

    def test_plan_validation_requires_webhook_and_delivery(self):
        settings = dict(GIT_WORKSPACE='source', RESULT_WORKSPACE='output', GIT_BRANCH='main', GIT_USER='example',
                        SLACK_ENABLED='true', SLACK_WEBHOOK='', MEGA_ENABLED='false', FTP_ENABLED='false')
        with patch('modules.build_service.shutil.which', return_value='tool'):
            errors = BuildPlan(('hurryApp',), ('release',), settings).validate()
            self.assertTrue(any('SLACK_WEBHOOK' in error for error in errors))
            self.assertTrue(any('MEGA or FTP' in error for error in errors))
            settings.update(SLACK_WEBHOOK='https://example.com/webhook', FTP_ENABLED='true',
                            FTP_HOST='example.com', FTP_USER='user', FTP_PASS='pass', FTP_BASE_URL='https://example.com')
            self.assertTrue(any('Slack requires' in error for error in BuildPlan(('hurryApp',), ('release',), settings).validate()))
            settings['SLACK_WEBHOOK'] = WEBHOOK
            self.assertEqual(BuildPlan(('hurryApp',), ('release',), settings).validate(), [])

    def test_build_pipeline_persists_slack_outcome_and_keeps_artifacts(self):
        for acknowledged in (True, False):
            with self.subTest(acknowledged=acknowledged), tempfile.TemporaryDirectory() as folder, patch.object(history_utils, 'HISTORY_FILE', Path(folder) / 'history.json'):
                artifact = Path(folder) / 'app.apk'
                artifact.write_bytes(b'APK')
                def build(project, stamp, stage, record):
                    record('release', str(artifact))
                    return {'release': str(artifact)}
                settings = dict(SLACK_ENABLED='true', SLACK_WEBHOOK=WEBHOOK, FTP_ENABLED='true', MEGA_ENABLED='false',
                                DISCORD_ENABLED='false', EMAIL_ENABLED='false')
                service = BuildService()
                with patch('modules.build_service.build_project_module.build_project', side_effect=build), patch(
                        'modules.upload_module.mass_upload', return_value={'hurryApp': {'release': {'urls': {'ftp': 'https://example.com/app.apk'}}}}), patch.object(
                        slack_module, 'send_to_slack', return_value=acknowledged) as send, patch('modules.send_module.send_to_discord', return_value=None) as discord, patch('modules.send_module.send_to_email', return_value=None) as email:
                    service._run(BuildPlan(('hurryApp',), ('release',), settings))
                send.assert_called_once()
                discord.assert_called_once()
                email.assert_called_once()
                entry = history_utils.get_history()[0]
                self.assertEqual(entry['slack_notified'], acknowledged)
                self.assertTrue(artifact.exists())
                self.assertIn('ftp', entry['urls'])
                events = []
                while not service.events.empty():
                    events.append(service.events.get_nowait())
                report = [data for kind, data in events if kind == 'finished'][-1]
                self.assertEqual(report['state'], 'Complete' if acknowledged else 'Warning')
                self.assertEqual(report['count'], 1)

if __name__ == '__main__':
    unittest.main()
