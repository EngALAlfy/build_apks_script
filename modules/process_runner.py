"""Streaming subprocess execution and process-tree cancellation."""
import os
import shutil
import subprocess
import threading
import bin.constants as state

class BuildCancelled(Exception):
    pass

_lock = threading.Lock()

def check_cancelled():
    if state.stop_requested:
        raise BuildCancelled('Build cancelled by user.')

def cancel():
    with _lock:
        state.stop_requested = True
        process = state.current_process
    if process and process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            process.terminate()

def run_command(args, cwd, label):
    check_cancelled()
    args = list(args)
    args[0] = shutil.which(args[0]) or args[0]
    command = subprocess.list2cmdline(args) if os.name == 'nt' else args
    print(f'\n[{label}]', flush=True)
    with _lock:
        check_cancelled()
        process = subprocess.Popen(command, cwd=str(cwd), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                   errors='replace', bufsize=1,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        state.current_process = process
    try:
        for line in process.stdout:
            print(line, end='', flush=True)
        process.wait()
        check_cancelled()
        if process.returncode:
            raise RuntimeError(f'{label} failed (exit code {process.returncode}). See the console.')
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()
        with _lock:
            state.current_process = None
