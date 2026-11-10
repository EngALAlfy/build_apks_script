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
from bin.constants import projects, project_colors, project_tenants, project_sources

TERMINAL = {'completed', 'warning', 'failed', 'cancelled', 'interrupted', 'delete_failed'}
ROLES = {'admin', 'builder', 'viewer'}
SECRET_FIELDS = {'MEGA_PASSWORD', 'FTP_PASS', 'EMAIL_PASSWORD', 'DISCORD_WEBHOOK', 'SLACK_WEBHOOK'}
PUBLIC_FIELDS = {'CLEAN_BUILD', 'MAX_PARALLEL_BUILDS', 'MEGA_ENABLED', 'MEGA_USERNAME',
                 'FTP_ENABLED', 'FTP_HOST', 'FTP_USER', 'FTP_PATH', 'FTP_BASE_URL',
                 'DISCORD_ENABLED', 'SLACK_ENABLED', 'EMAIL_ENABLED', 'EMAILS', 'SMTP_HOST', 'SMTP_PORT', 'EMAIL_USER'}
DUMMY_PASSWORD_HASH = generate_password_hash('nonexistent-user-placeholder')


class Conflict(ValueError):
    pass


DEFAULT_PROJECTS, DEFAULT_COLORS = dict(projects), dict(project_colors)
TENANT_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,39}')
PROJECT_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}')
PALETTE = ('#007bff', '#28a745', '#dc3545', '#17a2b8', '#6610f2', '#fd7e14', '#e83e8c', '#20c997', '#6f42c1', '#ffc107')


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
            fresh = not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='projects'").fetchone()
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL, position INTEGER NOT NULL, tenants TEXT NOT NULL DEFAULT \'[]\', repo_url TEXT NOT NULL DEFAULT \'\', branch TEXT NOT NULL DEFAULT \'main\')')
            if 'tenants' not in {r['name'] for r in db.execute('PRAGMA table_info(projects)')}:
                db.execute("ALTER TABLE projects ADD COLUMN tenants TEXT NOT NULL DEFAULT '[]'")
            have = {r['name'] for r in db.execute('PRAGMA table_info(projects)')}
            for column, definition in (('repo_url', "TEXT NOT NULL DEFAULT ''"), ('branch', "TEXT NOT NULL DEFAULT 'main'")):
                if column not in have:
                    db.execute(f'ALTER TABLE projects ADD COLUMN {column} {definition}')
            if fresh:
                db.executemany('INSERT INTO projects(id,name,color,position) VALUES (?,?,?,?)',
                               [(k, v, DEFAULT_COLORS.get(k, PALETTE[i % len(PALETTE)]), i) for i, (k, v) in enumerate(DEFAULT_PROJECTS.items())])
            defaults = {k: 'false' for k in PUBLIC_FIELDS if k.endswith('_ENABLED')}
            defaults.update(CLEAN_BUILD='true', MAX_PARALLEL_BUILDS='2', SMTP_PORT='587', FTP_PATH='/')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (json.dumps(defaults),))
            # Legacy global owner/branch settings become per-project sources, then are retired.
            stored = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            owner, branch = (stored.get('GIT_USER') or '').strip(), (stored.get('GIT_BRANCH') or '').strip() or 'main'
            if re.fullmatch(r'[A-Za-z0-9-]+', owner):
                db.execute("UPDATE projects SET repo_url='https://github.com/'||?||'/'||id||'.git', branch=? WHERE repo_url=''", (owner, branch))
            if 'GIT_USER' in stored or 'GIT_BRANCH' in stored:
                stored.pop('GIT_USER', None)
                stored.pop('GIT_BRANCH', None)
                db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(stored),))
        with self.connect(immediate=True) as db:
            columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)')}
            for name, definition in (('worker_slot', 'INTEGER'), ('worker_active', 'INTEGER NOT NULL DEFAULT 0'), ('tenants', "TEXT NOT NULL DEFAULT '{}'")):
                if name not in columns:
                    db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {definition}')
        self.sync_projects()

    def sync_projects(self):
        """Mirror the persisted registry into the shared in-memory dicts (mutated in place)."""
        with self.connect() as db:
            rows = db.execute('SELECT * FROM projects ORDER BY position,id').fetchall()
        projects.clear()
        project_colors.clear()
        project_tenants.clear()
        project_sources.clear()
        for row in rows:
            projects[row['id']] = row['name']
            project_colors[row['id']] = row['color']
            project_tenants[row['id']] = json.loads(row['tenants'])
            project_sources[row['id']] = {'url': row['repo_url'], 'branch': row['branch']}

    @staticmethod
    def clean_tenants(tenants):
        if tenants is None:
            return []
        if not isinstance(tenants, list) or len(tenants) > 30 or any(not isinstance(t, str) or not TENANT_ID.fullmatch(t) for t in tenants):
            raise ValueError('Tenants must be lowercase ids (letters, digits, underscores, hyphens), at most 30.')
        return list(dict.fromkeys(tenants))

    @staticmethod
    def parse_repo_url(url):
        """Return (normalized clone URL, repository name) for a GitHub HTTPS URL."""
        match = re.fullmatch(r'https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,80}?)(?:\.git)?/?', (url or '').strip()) if isinstance(url, str) else None
        if not match or match.group(2) in ('.', '..') or match.group(2).startswith('-'):
            raise ValueError('Enter the full GitHub repository URL, like https://github.com/owner/repository.')
        return f'https://github.com/{match.group(1)}/{match.group(2)}.git', match.group(2)

    @staticmethod
    def clean_branch(branch):
        branch = (branch or 'main').strip() if isinstance(branch, str) or branch is None else ''
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,119}', branch) or any(x in branch for x in ('..', '//', '/.')) or branch.endswith(('/', '.', '.lock')):
            raise ValueError('Enter a valid default branch using letters, numbers, dots, underscores, slashes, or hyphens.')
        return branch

    def add_project(self, url, name, branch='main', color=None, tenants=None):
        url, key = self.parse_repo_url(url)
        branch = self.clean_branch(branch)
        name = name.strip() if isinstance(name, str) else ''
        if not 1 <= len(name) <= 60:
            raise ValueError('Enter a display name of 1–60 characters.')
        if color is not None and (not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)):
            raise ValueError('Color must look like #1a73e8.')
        tenants = self.clean_tenants(tenants)
        with self.connect(immediate=True) as db:
            rows = db.execute('SELECT id,position FROM projects').fetchall()
            if any(r['id'].lower() == key.lower() for r in rows):
                raise Conflict(f'A project named {key} already exists.')
            if len(rows) >= 50:
                raise Conflict('The project limit (50) has been reached.')
            db.execute('INSERT INTO projects(id,name,color,position,tenants,repo_url,branch) VALUES (?,?,?,?,?,?,?)',
                       (key, name, color or PALETTE[len(rows) % len(PALETTE)], max([r['position'] for r in rows], default=-1) + 1, json.dumps(tenants), url, branch))
        self.sync_projects()
        return key

    def update_project(self, key, name=None, color=None, tenants=None, url=None, branch=None):
        with self.connect(immediate=True) as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (key,)).fetchone()
            if not row:
                raise ValueError('Project not found.')
            name = row['name'] if name is None else name.strip() if isinstance(name, str) else ''
            color = row['color'] if color is None else color
            if not 1 <= len(name) <= 60 or not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError('Enter a display name (1–60 characters) and a color like #1a73e8.')
            tenants = json.loads(row['tenants']) if tenants is None else self.clean_tenants(tenants)
            if url is None:
                url = row['repo_url']
            else:
                url, repo = self.parse_repo_url(url)
                if repo.lower() != key.lower():
                    raise ValueError(f'The repository must be named {key}. Add a new project to build a different repository.')
            branch = row['branch'] if branch is None else self.clean_branch(branch)
            db.execute('UPDATE projects SET name=?,color=?,tenants=?,repo_url=?,branch=? WHERE id=?', (name, color, json.dumps(tenants), url, branch, key))
        self.sync_projects()

    def sources_for(self, selected):
        return json.dumps({p: dict(project_sources[p]) for p in selected if p in project_sources})

    def remove_project(self, key):
        with self.connect(immediate=True) as db:
            if not db.execute('SELECT 1 FROM projects WHERE id=?', (key,)).fetchone():
                raise ValueError('Project not found.')
            for job in db.execute("SELECT projects FROM jobs WHERE status IN ('queued','running','cancel_requested','deleting')"):
                if key in json.loads(job['projects']):
                    raise Conflict('This project has queued or running builds. Cancel or wait for them first.')
            db.execute('DELETE FROM projects WHERE id=?', (key,))
            for user in db.execute('SELECT id,projects FROM users').fetchall():
                allowed = json.loads(user['projects'])
                if key in allowed:
                    db.execute('UPDATE users SET projects=? WHERE id=?', (json.dumps([p for p in allowed if p != key]), user['id']))
        self.sync_projects()

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
        if 'MAX_PARALLEL_BUILDS' in values and values['MAX_PARALLEL_BUILDS'] not in ('1', '2', '3', '4'):
            raise ValueError('Parallel build slots must be a number from 1 to 4.')
        with self.connect(immediate=True) as db:
            settings = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            settings.update({k: v for k, v in values.items() if k not in SECRET_FIELDS or v})
            for key in clear_secrets:
                settings[key] = ''
            db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(settings),))

    def max_parallel_builds(self):
        return int(self.settings().get('MAX_PARALLEL_BUILDS', '2'))

    @staticmethod
    def can_view(user, job):
        return user['role'] == 'admin' or set(job['projects']).issubset(user['projects'])

    @staticmethod
    def decode_job(row, internal=False):
        if row is None:
            return None
        data = dict(row)
        for key in ('projects', 'build_types', 'errors', 'warnings', 'tenants'):
            data[key] = json.loads(data[key])
        settings = json.loads(data.pop('settings'))
        data['branch_override'] = settings.get('GIT_BRANCH', '')
        if internal:
            data['settings'] = settings
        data['can_delete'] = not data.get('worker_active') and (data['status'] in TERMINAL or data['status'] == 'queued')
        return data

    def job(self, job_id, internal=False):
        with self.connect() as db:
            return self.decode_job(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone(), internal)

    def jobs(self, user):
        with self.connect() as db:
            rows = db.execute('SELECT jobs.*, (SELECT COUNT(*) FROM artifacts WHERE job_id=jobs.id) AS artifact_count FROM jobs ORDER BY created_at DESC,rowid DESC LIMIT 1000')
            return [j for r in rows if self.can_view(user, j := self.decode_job(r))]

    def enqueue(self, user, selected_projects, build_types, branch='', tenants=None):
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
            label = branch or ', '.join(dict.fromkeys(project_sources.get(p, {}).get('branch', 'main') for p in selected_projects))
            settings.update(GIT_BRANCH=branch, PROJECT_SOURCES=self.sources_for(selected_projects), GIT_WORKSPACE=str(self.root / 'workspaces' / job_id),
                            RESULT_WORKSPACE=str(self.root / 'artifacts' / job_id),
                            GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
            db.execute('INSERT INTO jobs(id,user_id,username,projects,build_types,branch,settings,created_at,tenants) VALUES (?,?,?,?,?,?,?,?,?)',
                       (job_id, user['id'], user['username'], json.dumps(selected_projects), json.dumps(build_types), label, json.dumps(settings), now(), json.dumps(tenants or {})))
        return self.job(job_id)

    def claim(self):
        with self.connect(immediate=True) as db:
            settings = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            limit = int(settings.get('MAX_PARALLEL_BUILDS', '2'))
            reserved = list(db.execute("SELECT worker_slot FROM jobs WHERE worker_active=1 OR status IN ('running','cancel_requested')"))
            if len(reserved) >= limit:
                return None
            busy = {row['worker_slot'] for row in reserved}
            slot = next(index for index in range(1, limit + 1) if index not in busy)
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,rowid LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',started_at=?,stage='Starting isolated worker',worker_slot=?,worker_active=1 WHERE id=?", (now(), slot, row['id']))
        return self.job(row['id'], internal=True)

    def update_job(self, job_id, **values):
        allowed = {'status', 'stage', 'progress', 'started_at', 'finished_at', 'errors', 'warnings', 'cancel_at', 'worker_active'}
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
            if not row or row['status'] in TERMINAL or row['status'] == 'deleting':
                raise Conflict('This build is already finished.')
            queued = row['status'] == 'queued'
            db.execute('UPDATE jobs SET status=?,stage=?,cancel_at=?,finished_at=? WHERE id=?',
                       ('cancelled' if queued else 'cancel_requested', 'Cancelled before execution' if queued else 'Cancellation requested', now(), now() if queued else None, job_id))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='interrupted',stage='Server restarted; submit a new build to retry',finished_at=? WHERE status IN ('running','cancel_requested')", (now(),))
            db.execute('UPDATE jobs SET worker_active=0')
            db.execute("UPDATE jobs SET status='delete_failed',stage='Cleanup interrupted; retry deletion' WHERE status='deleting'")
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
            rows = db.execute('SELECT artifacts.*, jobs.projects AS job_projects, jobs.username, jobs.branch FROM artifacts JOIN jobs ON jobs.id=artifacts.job_id ' +
                              ('WHERE job_id=? ' if job_id else '') + 'ORDER BY artifacts.created_at DESC LIMIT 1000', (job_id,) if job_id else ())
            result = []
            for row in rows:
                item = dict(row)
                if user['role'] != 'admin' and item['project'] not in user['projects']:
                    continue
                item['can_view_build'] = user['role'] == 'admin' or set(json.loads(item['job_projects'])).issubset(user['projects'])
                item.pop('job_projects')
                item['available'] = Path(item.pop('path')).is_file()
                result.append(item)
            return result

    def artifact(self, artifact_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            return dict(row) if row else None
