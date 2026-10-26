"""Run the actual frozen build pipeline with offline Git/Flutter command fixtures.
Usage: python tests/worker_unicode_smoke.py "path/to/APK Build Server.exe" [--expect-failure]
Does not access repositories, Gradle, uploads, or notification services.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.runtime import Runtime
from server.store import Store

executable=Path(sys.argv[1]).resolve()
actual_git=shutil.which('git')
assert actual_git,'Git is needed only to initialize the local fixture repository.'
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    store=Store(root)
    user=store.create_user('unicode.test','Offline-Fixture-Password-123','admin',['hurryApp'])
    store.save_settings({'GIT_USER':'offline-fixture','CLEAN_BUILD':'false'})
    job=store.enqueue(user,['hurryApp'],['debug'],'main')
    source=root/'workspaces'/job['id']/'hurryApp'
    source.mkdir(parents=True)
    (source/'pubspec.yaml').write_text('name: fixture\nversion: 1.2.3\n',encoding='utf-8')
    (source/'.gitignore').write_text('build/\n',encoding='utf-8')
    for args in ([actual_git,'init','--initial-branch','main',str(source)],
                 [actual_git,'-C',str(source),'add','.'],
                 [actual_git,'-C',str(source),'-c','commit.gpgsign=false','-c','user.name=Offline Fixture','-c','user.email=fixture@example.invalid','commit','-m','Offline fixture']):
        subprocess.run(args,check=True,capture_output=True)
    artifact=source/'build/app/outputs/flutter-apk/app-debug.apk'
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b'UNICODE-LOGGING-TEST-APK')
    fakebin=root/'fake-tools'
    fakebin.mkdir()
    # The scripts contain ASCII Python byte literals so output bytes are UTF-8
    # independently of cmd.exe's console/OEM code page.
    message='√ Built app-debug.apk / العربية / 🚀\n'
    python_code='import sys;sys.stdout.buffer.write('+repr(message.encode('utf-8'))+')'
    command='"'+sys.executable+'" -c "'+python_code+'"\r\nexit /b 0\r\n'
    (fakebin/'flutter.cmd').write_text('@echo off\r\n'+command,encoding='ascii',newline='')
    (fakebin/'git.cmd').write_text('@echo off\r\nif "%~1"=="status" exit /b 0\r\n'+command,encoding='ascii',newline='')
    internal=store.job(job['id'],internal=True)
    settings=internal['settings']
    settings['PATH']=str(fakebin)+os.pathsep+os.environ['PATH']
    with store.connect() as db:db.execute('UPDATE jobs SET settings=? WHERE id=?',(json.dumps(settings),job['id']))
    runtime=Runtime(store)
    runtime.command=lambda jid:[str(executable),'--worker',jid,'--data-dir',str(root)]
    runtime.execute(store.claim())
    result=store.job(job['id'])
    if '--expect-failure' in sys.argv:
        assert result['status']=='failed' and 'charmap' in str(result['errors']),result
        print('Reproduced the packaged Windows encoding bug with offline Unicode command output.')
    else:
        assert result['status']=='completed',result
        saved=store.artifacts(user)
        assert len(saved)==1,saved
        assert saved[0]['filename'].endswith('-debug.apk')
        log=(root/'logs'/(job['id']+'.log')).read_text(encoding='utf-8')
        assert '√ Built' in log and 'العربية' in log and '🚀' in log,repr(log)
        print('Packaged Unicode pipeline passed: command output, Git/Flutter stages, artifact collection, and completed status.')
