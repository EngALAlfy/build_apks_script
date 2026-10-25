"""Windows-only background supervisor smoke test. No real user profile is used."""
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.processes import kill_tree

root=Path(__file__).resolve().parents[1]
exe=root/'dist/APK Build Server/APK Build Server.exe'
with tempfile.TemporaryDirectory() as folder:
    data=Path(folder)/'data'
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1',0))
        port=endpoint.getsockname()[1]
    process=subprocess.Popen(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-File',str(root/'scripts/run-server.ps1'),'-ExecutablePath',str(exe),'-DataDirectory',str(data),'-BindAddress','127.0.0.1','-Port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    def ready(previous=None):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            record=data/'startup/managed-process.json'
            if record.exists():
                try:
                    value=json.loads(record.read_text(encoding='utf-8-sig'))
                    if value['ProcessId']!=previous and requests.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200:
                        return value
                except (ValueError,requests.RequestException):
                    pass
            if process.poll() is not None:
                raise AssertionError('Background supervisor exited unexpectedly.')
            time.sleep(.2)
        raise AssertionError('Background server did not become ready.')
    try:
        first=ready()
        details=subprocess.check_output(['powershell.exe','-NoProfile','-Command',f"Get-CimInstance Win32_Process -Filter 'ProcessId = {first['ProcessId']}' | Select-Object CommandLine | ConvertTo-Json -Compress"],text=True)
        assert '--no-browser' in details,details
        subprocess.run(['taskkill','/PID',str(first['ProcessId']),'/T','/F'],capture_output=True,check=True)
        second=ready(first['ProcessId'])
        assert second['ProcessId']!=first['ProcessId']
        assert 'Retrying in 10 seconds' in (data/'startup/supervisor.log').read_text(encoding='utf-8-sig')
    finally:
        kill_tree(process)
print('Startup supervisor passed: hidden startup, no-browser argument, isolated profile, and restart after server termination.')
