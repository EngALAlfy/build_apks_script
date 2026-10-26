"""Bounded FIFO scheduler with independent process lifetime for every build."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from server.processes import ProcessGuard, kill_tree
from server.store import TERMINAL, now


class Runtime:
    def __init__(self, store):
        self.store = store
        self.stopping = threading.Event()
        self.thread = None
        self._lock = threading.Lock()
        self._processes = {}
        self._executions = {}

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.store.recover()
        self.thread = threading.Thread(target=self.run, name='build-scheduler', daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        with self._lock:
            jobs = set(self._executions) | set(self._processes)
        for job_id in jobs:
            try:
                self.store.request_cancel(job_id)
            except ValueError:
                pass
        if self.thread:
            self.thread.join(timeout=2)
        deadline = time.monotonic() + 13
        with self._lock:
            executions = list(self._executions.values())
        for execution in executions:
            execution.join(timeout=max(0, deadline - time.monotonic()))
        with self._lock:
            remaining = list(self._processes.values())
        for process in remaining:
            kill_tree(process)
        for execution in executions:
            execution.join(timeout=2)

    def command(self, job_id):
        prefix = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve().parents[1] / 'server_main.py')]
        return [*prefix, '--worker', job_id, '--data-dir', str(self.store.root)]

    def run(self):
        while not self.stopping.is_set():
            try:
                with self._lock:
                    self._executions = {job_id: thread for job_id, thread in self._executions.items() if thread.is_alive()}
                job = self.store.claim()
                if not job:
                    self.stopping.wait(.5)
                    continue
                execution = threading.Thread(target=self.execute, args=(job,), name='build-' + job['id'][:8], daemon=True)
                with self._lock:
                    self._executions[job['id']] = execution
                try:
                    execution.start()
                except Exception:
                    self.store.update_job(job['id'], status='failed', worker_active=0, finished_at=now(), stage='Worker thread could not start')
                    raise
            except Exception as exc:
                print(f'Scheduler error: {type(exc).__name__}', flush=True)
                self.stopping.wait(1)

    def execute(self, job):
        process = None
        guard = None
        try:
            owner = self.store.user(job['user_id'])
            if not owner or not owner['enabled'] or owner['role'] not in ('admin', 'builder') or not self.store.can_view(owner, job):
                self.store.update_job(job['id'], status='failed', stage='Build access was revoked before execution', finished_at=now())
                return
            environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            log_path = self.store.root / 'logs' / (job['id'] + '.log')
            with log_path.open('ab', buffering=0) as log:
                process = subprocess.Popen(self.command(job['id']), cwd=self.store.root, env=environment,
                                                stdout=log, stderr=subprocess.STDOUT,
                                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                                start_new_session=os.name != 'nt')
                with self._lock:
                    self._processes[job['id']] = process
                guard = ProcessGuard(process)
                cancelling_at = None
                while process.poll() is None:
                    state = self.store.job(job['id'])
                    if self.stopping.is_set() or state['status'] == 'cancel_requested':
                        if cancelling_at is None:
                            cancelling_at = time.monotonic()
                        if time.monotonic() - cancelling_at >= 10:
                            kill_tree(process)
                            break
                    self.stopping.wait(.2) if not self.stopping.is_set() else time.sleep(.2)
            current = self.store.job(job['id'])
            if current['status'] not in TERMINAL:
                cancelled = current['status'] == 'cancel_requested' or self.stopping.is_set()
                self.store.update_job(job['id'], status='cancelled' if cancelled else 'failed', finished_at=now(),
                                      stage='Cancelled' if cancelled else 'Worker exited unexpectedly; inspect the build log')
        except Exception as exc:
            if process:
                try:
                    kill_tree(process)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            self.store.update_job(job['id'], status='failed', finished_at=now(), stage='Unable to run build worker',
                                  errors=[f'Worker startup failed: {type(exc).__name__}'])
        finally:
            if guard:
                guard.close()
            with self._lock:
                self._processes.pop(job['id'], None)
            self.store.update_job(job['id'], worker_active=0)
