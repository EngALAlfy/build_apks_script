"""SQLite persistence. Every operation opens its own thread-local connection."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash
from bin.constants import projects

TERMINAL = {'completed', 'warning', 'failed', 'cancelled', 'interrupted'}
ROLES = {'admin', 'builder', 'viewer'}
SECRET_FIELDS = {'MEGA_PASSWORD', 'FTP_PASS', 'EMAIL_PASSWORD', 'DISCORD_WEBHOOK', 'SLACK_WEBHOOK'}
PUBLIC_FIELDS = {'GIT_USER', 'GIT_BRANCH', 'CLEAN_BUILD', 'MEGA_ENABLED', 'MEGA_USERNAME',
                 'FTP_ENABLED', 'FTP_HOST', 'FTP_USER', 'FTP_PATH', 'FTP_BASE_URL',
                 'DISCORD_ENABLED', 'SLACK_ENABLED', 'EMAIL_ENABLED', 'EMAILS', 'SMTP_HOST', 'SMTP_PORT', 'EMAIL_USER'}
DUMMY_PASSWORD_HASH = generate_password_hash('nonexistent-user-placeholder')


class Conflict(ValueError):
    pass


def now():
    return int(time.time())


def validate_user(username, password, role, allowed):
    if not isinstance(username, str) or not re.fullmatch(r'[a-z][a-z0-9._-]{2,39}', username):
        raise ValueError('Username must be 3–40 lowercase letters, digits, dots, underscores, or hyphens.')
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError('Use a password of 12–256 characters.')
    if not isinstance(role, str) or role not in ROLES or not isinstance(allowed, list) or any(not isinstance(p, str) or p not in projects for p in allowed):
        raise ValueError('Invalid role or project access.')


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ('logs', 'artifacts', 'workspaces'):
            (self.root / folder).mkdir(exist_ok=True)
        self.database = self.root / 'server.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL, projects TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT, csrf TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, count INTEGER, expires INTEGER);
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
                    projects TEXT NOT NULL, build_types TEXT NOT NULL, branch TEXT NOT NULL,
                    settings TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
                    stage TEXT NOT NULL DEFAULT 'Waiting for a worker', progress REAL NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL, started_at INTEGER, finished_at INTEGER,
                    cancel_at INTEGER, errors TEXT NOT NULL DEFAULT '[]', warnings TEXT NOT NULL DEFAULT '[]');
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,created_at);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL, project TEXT NOT NULL, build_type TEXT NOT NULL,
                    filename TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                    created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, target TEXT, created_at INTEGER);
            ''')
            defaults = {k: 'false' for k in PUBLIC_FIELDS if k.endswith('_ENABLED')}
            defaults.update(GIT_USER='', GIT_BRANCH='main', CLEAN_BUILD='true', SMTP_PORT='587', FTP_PATH='/')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (json.dumps(defaults),))

    @contextmanager
    def connect(self, immediate=False):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=15000')
        try:
            if immediate:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, actor, action, target=''):
        with self.connect() as db:
            db.execute('INSERT INTO audit(actor,action,target,created_at) VALUES (?,?,?,?)', (actor, action, target, now()))

    def has_users(self):
        with self.connect() as db:
            return bool(db.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    @staticmethod
    def public_user(row):
        if row is None:
            return None
        return {**{k: row[k] for k in ('id', 'username', 'display_name', 'role', 'enabled', 'created_at')},
                'projects': json.loads(row['projects'])}

    def user(self, user_id):
        with self.connect() as db:
            return self.public_user(db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())

    def users(self):
        with self.connect() as db:
            return [self.public_user(r) for r in db.execute('SELECT * FROM users ORDER BY created_at,username')]

    def create_user(self, username, password, role, allowed, display_name='', bootstrap=False):
        validate_user(username, password, role, allowed)
        if not isinstance(display_name, str):
            raise ValueError('Display name must be text.')
        display_name = (display_name or username).strip()
        if not 1 <= len(display_name) <= 60:
            raise ValueError('Display name must contain 1–60 characters.')
        password_hash = generate_password_hash(password)
        user_id = uuid4().hex
        with self.connect(immediate=True) as db:
            if bootstrap and db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise Conflict('The server administrator has already been configured.')
            try:
                db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,1,?)',
                           (user_id, username, display_name, password_hash, role, json.dumps(allowed), now()))
            except sqlite3.IntegrityError:
                raise Conflict('That username is already in use.')
        return self.user(user_id)

    def update_user(self, user_id, actor_id, role, allowed, enabled, password=None):
        validate_user('valid', password or 'validation-placeholder', role, allowed)
        hashed = generate_password_hash(password) if password else None
        with self.connect(immediate=True) as db:
            current = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not current:
                raise ValueError('User not found.')
            if user_id == actor_id and (not enabled or role != 'admin'):
                raise Conflict('You cannot disable or remove your own administrator access.')
            if current['role'] == 'admin' and current['enabled'] and (role != 'admin' or not enabled):
                count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND enabled=1").fetchone()[0]
                if count <= 1:
                    raise Conflict('At least one active administrator is required.')
            db.execute('UPDATE users SET role=?,projects=?,enabled=?,password_hash=? WHERE id=?',
                       (role, json.dumps(allowed), int(enabled), hashed or current['password_hash'], user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))

    def authenticate(self, username, password):
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        # Always perform a hash check, including for unknown names.
        reference = row['password_hash'] if row else DUMMY_PASSWORD_HASH
        valid = check_password_hash(reference, password)
        return self.public_user(row) if row and row['enabled'] and valid else None

    def rate_limit(self, key, limit=8, period=900):
        with self.connect(immediate=True) as db:
            db.execute('DELETE FROM attempts WHERE expires<?', (now(),))
            row = db.execute('SELECT count FROM attempts WHERE key=?', (key,)).fetchone()
            if row and row['count'] >= limit:
                return False
            db.execute('INSERT INTO attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now() + period))
            return True

    def new_session(self, user_id=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (now(),))
            db.execute('DELETE FROM sessions WHERE user_id IS NULL AND token_hash IN (SELECT token_hash FROM sessions WHERE user_id IS NULL ORDER BY expires DESC LIMIT -1 OFFSET 200)')
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest, user_id, csrf, now() + (28800 if user_id else 1800)))
        return token, csrf

    def session(self, token):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), now())).fetchone()
            return dict(row) if row else None

    def revoke_session(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def settings(self):
        with self.connect() as db:
            return json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])

    def save_settings(self, values, clear_secrets=()):
        if set(values) - (PUBLIC_FIELDS | SECRET_FIELDS) or set(clear_secrets) - SECRET_FIELDS:
            raise ValueError('Unknown configuration field.')
        if any(not isinstance(v, str) or len(v) > 4000 for v in values.values()):
            raise ValueError('Configuration values must be strings up to 4000 characters.')
        with self.connect(immediate=True) as db:
            settings = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            settings.update({k: v for k, v in values.items() if k not in SECRET_FIELDS or v})
            for key in clear_secrets:
                settings[key] = ''
            db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(settings),))

    @staticmethod
    def can_view(user, job):
        return user['role'] == 'admin' or set(job['projects']).issubset(user['projects'])

    @staticmethod
    def decode_job(row, internal=False):
        if row is None:
            return None
        data = dict(row)
        for key in ('projects', 'build_types', 'errors', 'warnings'):
            data[key] = json.loads(data[key])
        settings = json.loads(data.pop('settings'))
        if internal:
            data['settings'] = settings
        return data

    def job(self, job_id, internal=False):
        with self.connect() as db:
            return self.decode_job(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone(), internal)

    def jobs(self, user):
        with self.connect() as db:
            rows = db.execute('SELECT jobs.*, (SELECT COUNT(*) FROM artifacts WHERE job_id=jobs.id) AS artifact_count FROM jobs ORDER BY created_at DESC,rowid DESC LIMIT 1000')
            return [j for r in rows if self.can_view(user, j := self.decode_job(r))]

    def enqueue(self, user, selected_projects, build_types, branch):
        job_id = uuid4().hex
        with self.connect(immediate=True) as db:
            current = self.public_user(db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone())
            if not current or not current['enabled'] or current['role'] not in ('admin', 'builder'):
                raise PermissionError('Build access is required.')
            if current['role'] != 'admin' and not set(selected_projects).issubset(current['projects']):
                raise PermissionError('You do not have access to every selected project.')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] >= 100:
                raise Conflict('The queue is full. Wait for an active build to finish.')
            if db.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status IN ('queued','running','cancel_requested')", (user['id'],)).fetchone()[0] >= 10:
                raise Conflict('You already have ten pending builds.')
            settings = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            settings.update(GIT_BRANCH=branch, GIT_WORKSPACE=str(self.root / 'workspaces' / job_id),
                            RESULT_WORKSPACE=str(self.root / 'artifacts' / job_id),
                            GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
            db.execute('INSERT INTO jobs(id,user_id,username,projects,build_types,branch,settings,created_at) VALUES (?,?,?,?,?,?,?,?)',
                       (job_id, user['id'], user['username'], json.dumps(selected_projects), json.dumps(build_types), branch, json.dumps(settings), now()))
        return self.job(job_id)

    def claim(self):
        with self.connect(immediate=True) as db:
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','cancel_requested')").fetchone():
                return None
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,rowid LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',started_at=?,stage='Starting isolated worker' WHERE id=?", (now(), row['id']))
        return self.job(row['id'], internal=True)

    def update_job(self, job_id, **values):
        allowed = {'status', 'stage', 'progress', 'started_at', 'finished_at', 'errors', 'warnings', 'cancel_at'}
        if not values or set(values) - allowed:
            raise ValueError('Invalid job update.')
        for key in ('errors', 'warnings'):
            if key in values:
                values[key] = json.dumps(values[key])
        with self.connect() as db:
            db.execute('UPDATE jobs SET ' + ','.join(k + '=?' for k in values) + ' WHERE id=?', (*values.values(), job_id))

    def request_cancel(self, job_id):
        with self.connect(immediate=True) as db:
            row = db.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row or row['status'] in TERMINAL:
                raise Conflict('This build is already finished.')
            queued = row['status'] == 'queued'
            db.execute('UPDATE jobs SET status=?,stage=?,cancel_at=?,finished_at=? WHERE id=?',
                       ('cancelled' if queued else 'cancel_requested', 'Cancelled before execution' if queued else 'Cancellation requested', now(), now() if queued else None, job_id))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='interrupted',stage='Server restarted; submit a new build to retry',finished_at=? WHERE status IN ('running','cancel_requested')", (now(),))
            db.execute('DELETE FROM sessions WHERE expires<?', (now(),))

    def add_artifact(self, job_id, path):
        path = Path(path).resolve()
        base = (self.root / 'artifacts' / job_id).resolve()
        if not path.is_relative_to(base) or path.suffix not in ('.apk', '.aab') or not path.is_file():
            raise ValueError('Artifact lies outside the managed job output directory.')
        project = path.parent.name
        if project not in projects:
            raise ValueError('Unknown artifact project.')
        kind = 'appbundle' if path.suffix == '.aab' else 'debug' if path.stem.endswith('-debug') else 'release'
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        with self.connect() as db:
            db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?)',
                       (uuid4().hex, job_id, project, kind, path.name, str(path), path.stat().st_size, digest.hexdigest(), now()))

    def artifacts(self, user, job_id=None):
        with self.connect() as db:
            rows = db.execute('SELECT artifacts.*, jobs.projects AS job_projects, jobs.username FROM artifacts JOIN jobs ON jobs.id=artifacts.job_id ' +
                              ('WHERE job_id=? ' if job_id else '') + 'ORDER BY artifacts.created_at DESC LIMIT 1000', (job_id,) if job_id else ())
            result = []
            for row in rows:
                item = dict(row)
                if user['role'] != 'admin' and item['project'] not in user['projects']:
                    continue
                item.pop('job_projects')
                item['available'] = Path(item.pop('path')).is_file()
                result.append(item)
            return result

    def artifact(self, artifact_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            return dict(row) if row else None
