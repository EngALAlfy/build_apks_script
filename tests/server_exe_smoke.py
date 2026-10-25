"""Validate a packaged server without user repositories or external services.
Usage: python tests/server_exe_smoke.py "path/to/APK Build Server.exe"
"""
import hashlib
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.processes import kill_tree
from server.store import Store

executable=Path(sys.argv[1]).resolve()
repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    with socket.socket() as socket_handle:
        socket_handle.bind(('127.0.0.1',0))
        port=socket_handle.getsockname()[1]
    log=(root/'startup.log').open('wb')
    process=subprocess.Popen([str(executable),'--host','127.0.0.1','--port',str(port),'--data-dir',str(root/'data'),'--no-browser'],
                             stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        url=f'http://127.0.0.1:{port}'
        deadline=time.monotonic()+30
        while True:
            try:
                if requests.get(url+'/health',timeout=1).status_code==200:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None or time.monotonic()>deadline:
                raise AssertionError('Packaged server did not become ready.')
            time.sleep(.2)
        session=requests.Session()
        first=session.get(url+'/api/session',timeout=5).json()
        assert first['setup_required'] and first['can_setup']
        response=session.post(url+'/api/setup',json={'username':'packaged.test','password':'Packaged-Test-Only-123'},
                              headers={'X-CSRF-Token':first['csrf']},timeout=5)
        assert response.status_code==201,response.text
        assert session.get(url+'/api/dashboard',timeout=5).status_code==200
        for file in ('index.html','app.css','app.js'):
            result=session.get(url+('/' if file=='index.html' else '/assets/'+file),timeout=5)
            assert result.status_code==200
            assert hashlib.sha256(result.content).hexdigest()==hashlib.sha256((repo/'server/web'/file).read_bytes()).hexdigest(),file
        store=Store(root/'data')
        user=store.user(response.json()['user']['id'])
        # Empty owner intentionally fails validation before any Git/Flutter operation.
        job=store.enqueue(user,['hurryApp'],['release'],'main')
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            result=store.job(job['id'])
            if result['status']=='failed':
                break
            time.sleep(.2)
        assert result['status']=='failed',result
        assert any('GitHub owner' in error for error in result['errors']),result
        assert not list((root/'data/workspaces').iterdir()),'Unexpected repository checkout'
        assert not (executable.parent/'.env').exists()
    finally:
        kill_tree(process)
        log.close()
print('Packaged server smoke passed: standalone startup, admin setup, authentication, bundled assets, and frozen worker dispatch without .env.')
