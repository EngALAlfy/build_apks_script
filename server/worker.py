"""Isolated worker entry point. Build configuration never reaches the command line."""
import os
import re
import sys
import threading

from server.store import Store, now


class RedactingOutput:
    encoding = 'utf-8'
    def __init__(self, stream):
        self.stream = stream
        self.written = 0
        self.lock = threading.Lock()

    def write(self, value):
        from utils.settings_utils import redact
        clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', redact(str(value)))
        with self.lock:
            if self.written < 20 * 1024 * 1024:
                self.stream.write(clean)
                self.stream.flush()
                self.written += len(clean.encode('utf-8'))
                if self.written >= 20 * 1024 * 1024:
                    self.stream.write('\nLog limit reached; further console output omitted.\n')
        return len(value)

    def flush(self):
        self.stream.flush()


def run_worker(root, job_id):
    from modules.build_service import BuildService, BuildPlan
    from modules.process_runner import cancel
    from utils import history_utils
    store = Store(root)
    job = store.job(job_id, internal=True)
    if not job or job['status'] not in ('running', 'cancel_requested'):
        return 1
    os.environ.update(job['settings'])
    history_utils.HISTORY_FILE = store.root / 'history' / (job_id + '.json')
    history_utils.LEGACY_HISTORY_FILE = history_utils.HISTORY_FILE
    sys.stdout = RedactingOutput(sys.stdout)
    sys.stderr = sys.stdout
    stopped = threading.Event()

    class Service(BuildService):
        def emit(self, kind, **data):
            if kind == 'project':
                store.update_job(job_id, progress=data['progress'], stage=f"{data['project']} / {data['state']}")
            elif kind == 'stage':
                store.update_job(job_id, stage=f"{data['project']} / {data['stage']}")
            elif kind == 'artifact':
                store.add_artifact(job_id, data['path'])
            elif kind == 'finished':
                state = {'Complete': 'completed'}.get(data['state'], data['state'].lower())
                if store.job(job_id)['status'] == 'cancel_requested':
                    state = 'cancelled'
                from utils.settings_utils import redact
                store.update_job(job_id, status=state, stage=state.capitalize(), finished_at=now(),
                                 progress=1 if state in ('completed', 'warning') else store.job(job_id)['progress'],
                                 errors=[redact(e) for e in data['errors']], warnings=[redact(w) for w in data['warnings']])

    def watch_cancel():
        while not stopped.wait(.3):
            current = store.job(job_id)
            if current and current['status'] == 'cancel_requested':
                cancel()
                return

    monitor = threading.Thread(target=watch_cancel, daemon=True)
    monitor.start()
    try:
        plan = BuildPlan(tuple(job['projects']), tuple(job['build_types']), job['settings'])
        errors = plan.validate()
        if errors:
            store.update_job(job_id, status='failed', stage='Server configuration needs attention', errors=errors, finished_at=now())
            return 1
        print(f"Build {job_id[:8]} requested by {job['username']}\nBranch: {job['branch']}", flush=True)
        Service()._run(plan)
        return 0
    finally:
        stopped.set()
        monitor.join(timeout=2)
