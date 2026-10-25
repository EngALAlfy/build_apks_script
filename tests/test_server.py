"""LAN server security, durable queue, artifacts, and isolated execution tests."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server.app import create_app, valid_branch
from server.processes import InstanceLock
from server.runtime import Runtime
from server.store import Store

PASSWORD = 'local-test-password-123'

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app(self.root)
        self.store = self.app.config['STORE']
        self.client = self.app.test_client()
        self.csrf = self.client.get('/api/session').json['csrf']
        response = self.post('/api/setup', {'username':'administrator','password':PASSWORD,'display_name':'Test Admin'})
        self.assertEqual(response.status_code, 201)
        self.admin = response.json['user']
        self.csrf = response.json['csrf']
        self.store.save_settings({'GIT_USER':'example'})

    def post(self, url, body=None, client=None, csrf=None, method='POST', **kwargs):
        return (client or self.client).open(url, method=method, json=body or {},
            headers={'X-CSRF-Token':csrf or self.csrf}, **kwargs)

    def account(self, username='teammate', role='builder', projects=None):
        user = self.store.create_user(username, PASSWORD, role, projects if projects is not None else ['hurryApp'])
        client = self.app.test_client()
        csrf = client.get('/api/session').json['csrf']
        response = self.post('/api/login', {'username':username,'password':PASSWORD}, client, csrf)
        self.assertEqual(response.status_code, 200)
        return user, client, response.json['csrf']

    def enqueue(self, user=None):
        return self.store.enqueue(user or self.admin, ['hurryApp'], ['release'], 'main')

    def test_auth_required_for_data_and_mutations(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/api/dashboard').status_code, 401)
        self.assertEqual(client.get('/api/config').status_code, 401)
        self.assertEqual(client.post('/api/jobs', json={}).status_code, 403)
        for url in ('/', '/assets/app.js'):
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_first_setup_is_local_only_and_single_use(self):
        app = create_app(self.root / 'fresh')
        client = app.test_client()
        token = client.get('/api/session').json['csrf']
        payload = {'username':'firstadmin','password':PASSWORD}
        response = client.post('/api/setup', json=payload, headers={'X-CSRF-Token':token}, environ_overrides={'REMOTE_ADDR':'192.168.1.20'})
        self.assertEqual(response.status_code,403)
        response = client.post('/api/setup', base_url='http://untrusted.example', json=payload, headers={'X-CSRF-Token':token})
        self.assertEqual(response.status_code,403)
        self.assertFalse(app.config['STORE'].has_users())
        response = self.post('/api/setup', payload)
        self.assertEqual(response.status_code,409)

    def test_csrf_and_cross_origin_requests_are_rejected(self):
        self.assertEqual(self.client.post('/api/logout',json={}).status_code,403)
        response = self.client.post('/api/logout',json={},headers={'X-CSRF-Token':self.csrf,'Origin':'http://attacker.example'})
        self.assertEqual(response.status_code,403)
        self.assertIsNotNone(self.client.get('/api/session').json['user'])

    def test_logout_revokes_the_session_token(self):
        cookie = self.client.get_cookie('apk_build_session').value
        self.assertEqual(self.post('/api/logout').status_code,200)
        self.client.set_cookie('apk_build_session',cookie)
        self.assertEqual(self.client.get('/api/dashboard').status_code,401)

    def test_login_rate_limit(self):
        client=self.app.test_client()
        csrf=client.get('/api/session').json['csrf']
        for _ in range(8):
            self.assertEqual(self.post('/api/login',{'username':'administrator','password':'wrong'},client,csrf).status_code,401)
        self.assertEqual(self.post('/api/login',{'username':'administrator','password':PASSWORD},client,csrf).status_code,429)

    def test_password_hash_and_secret_configuration_are_not_exposed(self):
        self.store.save_settings({'SLACK_WEBHOOK':'https://hooks.slack.com/services/TTEST/BTEST/private-secret'})
        response=self.client.get('/api/config')
        self.assertNotIn('private-secret', response.get_data(as_text=True))
        self.assertTrue(response.json['secrets_set']['SLACK_WEBHOOK'])
        self.assertNotIn('password_hash',self.client.get('/api/users').get_data(as_text=True))
        with self.store.connect() as db:
            hashed=db.execute('SELECT password_hash FROM users WHERE id=?',(self.admin['id'],)).fetchone()[0]
        self.assertNotIn(PASSWORD,hashed)

    def test_viewer_cannot_enqueue_or_manage_accounts(self):
        _,client,token=self.account(role='viewer')
        self.assertEqual(self.post('/api/jobs',{},client,token).status_code,403)
        self.assertEqual(client.get('/api/users').status_code,403)
        self.assertEqual(client.get('/api/config').status_code,403)
        self.assertEqual(client.get('/api/dashboard').status_code,200)

    def test_project_permissions_apply_to_enqueue_jobs_logs_and_downloads(self):
        _,client,token=self.account(projects=['BranchManager'])
        job=self.enqueue()
        self.assertEqual(client.get('/api/jobs/'+job['id']).status_code,404)
        self.assertEqual(client.get('/api/jobs/'+job['id']+'/logs').status_code,404)
        payload={'projects':['hurryApp'],'build_types':['release'],'branch':'main'}
        self.assertEqual(self.post('/api/jobs',payload,client,token).status_code,403)
        self.assertEqual(client.get('/api/dashboard').json['jobs'],[])
        artifact=self.root/'artifacts'/job['id']/'session'/'hurryApp'/'app-release.apk'
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b'APK')
        self.store.add_artifact(job['id'],artifact)
        item=self.store.artifacts(self.admin)[0]
        self.assertEqual(client.get('/api/artifacts/'+item['id']+'/download').status_code,404)

    def test_download_requires_auth_and_serves_only_managed_artifacts(self):
        job=self.enqueue()
        path=self.root/'artifacts'/job['id']/'session'/'hurryApp'/'app-release.apk'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'APK TEST BYTES')
        self.store.add_artifact(job['id'],path)
        artifact=self.store.artifacts(self.admin)[0]
        response=self.client.get('/api/artifacts/'+artifact['id']+'/download')
        self.assertEqual(response.data,b'APK TEST BYTES')
        self.assertIn('attachment',response.headers['Content-Disposition'])
        response.close()
        self.assertEqual(self.app.test_client().get('/api/artifacts/'+artifact['id']+'/download').status_code,401)
        outside=self.root/'outside.apk'
        outside.write_bytes(b'NO')
        with self.store.connect() as db:
            db.execute('UPDATE artifacts SET path=? WHERE id=?',(str(outside),artifact['id']))
        self.assertEqual(self.client.get('/api/artifacts/'+artifact['id']+'/download').status_code,404)
        with self.assertRaises(ValueError):
            self.store.add_artifact(job['id'],outside)

    def test_queue_submission_validates_payload_and_snapshots_settings(self):
        payload={'projects':['hurryApp'],'build_types':['release'],'branch':'release/test'}
        with patch('modules.build_service.shutil.which', return_value='tool'):
            response=self.post('/api/jobs',payload)
        self.assertEqual(response.status_code,201,response.json)
        job=self.store.job(response.json['job']['id'],internal=True)
        self.assertEqual(job['settings']['GIT_BRANCH'],'release/test')
        self.assertIn(job['id'],job['settings']['GIT_WORKSPACE'])
        self.assertNotIn('settings',response.json['job'])
        self.store.save_settings({'GIT_USER':'changed'})
        self.assertEqual(self.store.job(job['id'],internal=True)['settings']['GIT_USER'],'example')
        for bad in ('--config', 'main;echo', '../main', 'bad branch', 'x.lock', 'x//y'):
            self.assertFalse(valid_branch(bad))
        with patch('modules.build_service.shutil.which', return_value='tool'):
            self.assertEqual(self.post('/api/jobs',{**payload,'branch':'--help'}).status_code,400)
            self.assertEqual(self.post('/api/jobs',{**payload,'projects':[{}]}).status_code,400)

    def test_fifo_claim_is_atomic_and_only_one_job_runs(self):
        first,second=self.enqueue(),self.enqueue()
        with ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(lambda _:self.store.claim(),range(4)))
        claimed=[r for r in results if r]
        self.assertEqual(len(claimed),1)
        self.assertEqual(claimed[0]['id'],first['id'])
        self.assertEqual(self.store.job(second['id'])['status'],'queued')

    def test_cancel_own_queued_build_and_deny_cancelling_teammates(self):
        user,client,token=self.account()
        own=self.enqueue(user)
        others=self.enqueue()
        self.assertEqual(self.post('/api/jobs/'+others['id']+'/cancel',{},client,token).status_code,403)
        self.assertEqual(self.post('/api/jobs/'+own['id']+'/cancel',{},client,token).status_code,200)
        self.assertEqual(self.store.job(own['id'])['status'],'cancelled')

    def test_restart_marks_running_jobs_interrupted_and_preserves_queue(self):
        active=self.enqueue();queued=self.enqueue()
        self.store.claim()
        self.store.recover()
        self.assertEqual(self.store.job(active['id'])['status'],'interrupted')
        self.assertEqual(self.store.job(queued['id'])['status'],'queued')
        self.assertEqual(Store(self.root).claim()['id'],queued['id'])

    def test_disabled_user_sessions_are_revoked_immediately(self):
        user,client,token=self.account()
        response=self.post('/api/users/'+user['id'],{'role':'builder','projects':['hurryApp'],'enabled':False},method='PATCH')
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.get('/api/dashboard').status_code,401)
        self.assertEqual(self.post('/api/users/'+self.admin['id'],{'role':'viewer','projects':[],'enabled':False},method='PATCH').status_code,409)

    def test_blank_secret_preserves_saved_value_and_explicit_clear_removes_it(self):
        self.store.save_settings({'SLACK_WEBHOOK':'saved-secret'})
        self.post('/api/config',{'values':{'SLACK_WEBHOOK':''}},method='PUT')
        self.assertEqual(self.store.settings()['SLACK_WEBHOOK'],'saved-secret')
        self.post('/api/config',{'values':{},'clear_secrets':['SLACK_WEBHOOK']},method='PUT')
        self.assertEqual(self.store.settings()['SLACK_WEBHOOK'],'')
        self.assertEqual(self.post('/api/config',{'values':{'PATH':'untrusted'}},method='PUT').status_code,400)

    def test_log_cursor_is_bounded_and_no_paths_are_returned_in_artifact_listing(self):
        job=self.enqueue()
        log=self.root/'logs'/(job['id']+'.log')
        log.write_bytes(b'x'*300000)
        result=self.client.get('/api/jobs/'+job['id']+'/logs?offset=0').json
        self.assertTrue(result['truncated'])
        self.assertLessEqual(len(result['text']),256*1024)
        self.assertEqual(result['offset'],300000)
        self.assertEqual(self.client.get('/api/jobs/'+job['id']+'/logs?offset=bad').status_code,400)

    def test_cookie_and_browser_security_headers(self):
        client=self.app.test_client()
        response=client.get('/api/session')
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])

    def test_server_instance_lock_blocks_a_second_owner(self):
        first=InstanceLock(self.root/'test.lock')
        try:
            with self.assertRaises(RuntimeError):
                InstanceLock(self.root/'test.lock')
        finally:
            first.close()

    def test_https_proxy_origin_is_supported_without_trusting_forwarded_headers(self):
        app = create_app(self.root / 'secure', secure_cookies=True)
        client = app.test_client(use_cookies=False)
        response = client.get('/api/session')
        cookie = response.headers['Set-Cookie'].split(';', 1)[0]
        self.assertIn('Secure', response.headers['Set-Cookie'])
        response = client.post('/api/setup', json={'username': 'secure.admin', 'password': PASSWORD},
                               headers={'Cookie': cookie, 'X-CSRF-Token': response.json['csrf'], 'Origin': 'https://localhost'})
        self.assertEqual(response.status_code, 201)

    def test_pending_build_cap_and_revoked_dispatch_access(self):
        for _ in range(10):
            self.enqueue()
        with self.assertRaisesRegex(ValueError, 'ten pending'):
            self.enqueue()
        user = self.store.create_user('revoked.user', PASSWORD, 'builder', ['hurryApp'])
        job = self.store.enqueue(user, ['hurryApp'], ['release'], 'main')
        with self.store.connect() as db:
            db.execute("UPDATE jobs SET status='cancelled' WHERE user_id=?", (self.admin['id'],))
            db.execute('UPDATE users SET enabled=0 WHERE id=?', (user['id'],))
        runtime = Runtime(self.store)
        with patch('server.runtime.subprocess.Popen') as popen:
            runtime.execute(self.store.claim())
            popen.assert_not_called()
        self.assertEqual(self.store.job(job['id'])['status'], 'failed')

    def fixture_runtime(self, mode):
        runtime=Runtime(self.store)
        fixture=Path(__file__).resolve().parent/'server_fixture_worker.py'
        runtime.command=lambda job_id:[sys.executable,str(fixture),str(self.root),job_id,mode]
        return runtime

    def test_real_isolated_worker_collects_artifact_and_log(self):
        job=self.enqueue()
        runtime=self.fixture_runtime('success')
        runtime.execute(self.store.claim())
        result=self.store.job(job['id'])
        self.assertEqual(result['status'],'completed',result)
        artifacts=self.store.artifacts(self.admin)
        self.assertEqual(len(artifacts),1)
        self.assertEqual(artifacts[0]['size'],len(b'ISOLATED-TEST-ARTIFACT'))
        self.assertIn('Fixture console output',(self.root/'logs'/(job['id']+'.log')).read_text(encoding='utf-8'))
        self.assertNotIn('settings',self.client.get('/api/jobs/'+job['id']).json['job'])

    def test_running_subprocess_can_be_cancelled(self):
        job=self.enqueue()
        runtime=self.fixture_runtime('slow')
        thread=threading.Thread(target=runtime.execute,args=(self.store.claim(),))
        thread.start()
        try:
            deadline=time.monotonic()+10
            log=self.root/'logs'/(job['id']+'.log')
            while time.monotonic()<deadline:
                if log.exists() and 'fixture child running' in log.read_text(encoding='utf-8',errors='replace'):
                    break
                time.sleep(.05)
            self.store.request_cancel(job['id'])
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive())
            self.assertEqual(self.store.job(job['id'])['status'],'cancelled')
        finally:
            runtime.stop()
            thread.join(timeout=5)

if __name__=='__main__':
    unittest.main()
