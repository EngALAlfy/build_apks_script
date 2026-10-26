"""Authenticated LAN HTTP API and offline-capable browser dashboard."""
import hmac
import ipaddress
import re
import shutil
import sys
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from bin.constants import projects, project_colors, tasks
from modules.build_service import BuildPlan
from server.store import Store, Conflict, PUBLIC_FIELDS, SECRET_FIELDS

COOKIE = 'apk_build_session'


class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def valid_branch(value):
    return (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,119}', value)
            and not any(s in value for s in ('..', '//', '/.')) and not value.endswith(('/', '.', '.lock')))


def create_app(data_dir, secure_cookies=False):
    store = Store(data_dir)
    assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'server' / 'web'
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=64 * 1024, STORE=store, SECURE_COOKIES=secure_cookies)

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise APIError('A JSON object is required.')
        return value

    def require(*roles):
        def wrap(function):
            @wraps(function)
            def checked(*args, **kwargs):
                if not g.user:
                    raise APIError('Sign in to continue.', 401)
                if roles and g.user['role'] not in roles:
                    raise APIError('Your account does not have permission for this action.', 403)
                return function(*args, **kwargs)
            return checked
        return wrap

    def local_setup():
        try:
            address = ipaddress.ip_address(request.remote_addr)
        except ValueError:
            return False
        return address.is_loopback and urlsplit(request.host_url).hostname in ('localhost', '127.0.0.1', '::1')

    def rotate_session(user_id=None):
        if request.cookies.get(COOKIE):
            store.revoke_session(request.cookies[COOKIE])
        token, csrf = store.new_session(user_id)
        g.new_cookie = token
        g.session_data = {'csrf': csrf, 'user_id': user_id}
        return csrf

    @app.before_request
    def authentication():
        g.new_cookie, g.user = None, None
        g.session_data = store.session(request.cookies.get(COOKIE, ''))
        if g.session_data and g.session_data['user_id']:
            user = store.user(g.session_data['user_id'])
            if user and user['enabled']:
                g.user = user
        if request.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            expected_origin = ('https://' + request.host) if secure_cookies else request.host_url.rstrip('/')
            if origin and origin.rstrip('/') != expected_origin:
                raise APIError('Cross-origin requests are not allowed.', 403)
            token = request.headers.get('X-CSRF-Token', '')
            if not g.session_data or not hmac.compare_digest(token.encode(), g.session_data['csrf'].encode()):
                raise APIError('Your session expired. Refresh the page and try again.', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if request.path == '/' or request.path.startswith(('/api/', '/assets/')):
            response.headers['Cache-Control'] = 'no-store'
        if g.get('new_cookie'):
            response.set_cookie(COOKIE, g.new_cookie, max_age=28800 if g.session_data.get('user_id') else 1800,
                                httponly=True, secure=secure_cookies, samesite='Strict')
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 409 if isinstance(error, Conflict) else 400

    @app.errorhandler(PermissionError)
    def forbidden(error):
        return jsonify(error=str(error)), 403

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.error('Request failed: %s', type(error).__name__)
        return jsonify(error='The server could not complete this request. Contact your administrator.'), 500

    @app.get('/')
    def index():
        return send_from_directory(assets, 'index.html')

    @app.get('/assets/<path:name>')
    def static_asset(name):
        return send_from_directory(assets, name, max_age=0)

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.get('/api/session')
    def session_info():
        if not g.session_data:
            rotate_session()
        return jsonify(user=g.user, csrf=g.session_data['csrf'], setup_required=not store.has_users(), can_setup=local_setup())

    @app.post('/api/setup')
    def setup():
        if not local_setup():
            raise APIError('Initialize the first administrator from http://localhost on the server PC.', 403)
        data = body()
        user = store.create_user(data.get('username'), data.get('password'), 'admin', list(projects), data.get('display_name', ''), bootstrap=True)
        csrf = rotate_session(user['id'])
        store.audit(user['username'], 'server.initialized', user['id'])
        return jsonify(user=user, csrf=csrf), 201

    @app.post('/api/login')
    def login():
        data = body()
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 40 or len(password) > 256:
            raise APIError('Invalid username or password.', 401)
        if not store.rate_limit('login:' + str(request.remote_addr) + ':' + username.lower()) or not store.rate_limit('ip:' + str(request.remote_addr), limit=60):
            raise APIError('Too many sign-in attempts. Wait 15 minutes before trying again.', 429)
        user = store.authenticate(username, password)
        if not user:
            raise APIError('Invalid username or password.', 401)
        csrf = rotate_session(user['id'])
        store.audit(user['username'], 'session.login')
        return jsonify(user=user, csrf=csrf)

    @app.post('/api/logout')
    def logout():
        csrf = rotate_session()
        return jsonify(csrf=csrf)

    @app.get('/api/dashboard')
    @require()
    def dashboard():
        jobs = store.jobs(g.user)
        artifacts = store.artifacts(g.user)
        with store.connect() as db:
            queue = [r[0] for r in db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at,rowid")]
            busy = bool(db.execute("SELECT 1 FROM jobs WHERE status IN ('running','cancel_requested')").fetchone())
        positions = {job_id: i + 1 for i, job_id in enumerate(queue)}
        for job in jobs:
            job['queue_position'] = positions.get(job['id'])
        allowed = list(projects) if g.user['role'] == 'admin' else [p for p in g.user['projects'] if p in projects]
        return jsonify(jobs=jobs[:100], artifacts=artifacts[:100], worker_busy=busy,
                       max_parallel_builds=store.max_parallel_builds(),
                       projects=[dict(id=p, name=projects[p], color=project_colors[p]) for p in allowed],
                       formats=[dict(id=k, name=v) for k, v in tasks.items()],
                       default_branch=store.settings().get('GIT_BRANCH', 'main'),
                       network=app.config['DISCOVERY'].status() if app.config.get('DISCOVERY') else None,
                       tools={'git': bool(shutil.which('git')), 'flutter': bool(shutil.which('flutter'))},
                       stats={'queued': sum(j['status'] == 'queued' for j in jobs),
                              'running': sum(j['status'] in ('running', 'cancel_requested') for j in jobs),
                              'completed': sum(j['status'] in ('completed', 'warning') for j in jobs),
                              'artifacts': sum(a['available'] for a in artifacts)})

    def accessible_job(job_id):
        job = store.job(job_id)
        if not job or not store.can_view(g.user, job):
            raise APIError('Build not found.', 404)
        return job

    @app.post('/api/jobs')
    @require('admin', 'builder')
    def enqueue():
        data = body()
        selected, formats, branch = data.get('projects'), data.get('build_types'), data.get('branch')
        if not isinstance(selected, list) or not selected or len(selected) > len(projects) or any(not isinstance(p, str) or p not in projects for p in selected):
            raise APIError('Choose at least one recognized project.')
        if not isinstance(formats, list) or not formats or len(formats) > len(tasks) or any(not isinstance(t, str) or t not in tasks for t in formats):
            raise APIError('Choose at least one recognized build format.')
        if not valid_branch(branch):
            raise APIError('Enter a valid branch using letters, numbers, dots, underscores, slashes, or hyphens.')
        if g.user['role'] != 'admin' and not set(selected).issubset(g.user['projects']):
            raise APIError('You do not have access to those projects.', 403)
        settings = store.settings()
        settings.update(GIT_BRANCH=branch, GIT_WORKSPACE=str(store.root / 'workspaces' / 'validation'),
                        RESULT_WORKSPACE=str(store.root / 'artifacts' / 'validation'))
        errors = BuildPlan(tuple(selected), tuple(formats), settings).validate()
        if errors:
            raise APIError('Server setup needs attention: ' + ' '.join(errors), 422)
        job = store.enqueue(g.user, list(dict.fromkeys(selected)), list(dict.fromkeys(formats)), branch)
        store.audit(g.user['username'], 'build.queued', job['id'])
        return jsonify(job=job), 201

    @app.get('/api/jobs/<job_id>')
    @require()
    def job_detail(job_id):
        return jsonify(job=accessible_job(job_id), artifacts=store.artifacts(g.user, job_id))

    @app.post('/api/jobs/<job_id>/cancel')
    @require('admin', 'builder')
    def cancel(job_id):
        job = accessible_job(job_id)
        if g.user['role'] != 'admin' and job['user_id'] != g.user['id']:
            raise APIError('You can cancel only your own builds.', 403)
        store.request_cancel(job_id)
        store.audit(g.user['username'], 'build.cancel_requested', job_id)
        return jsonify(ok=True)

    @app.delete('/api/jobs/<job_id>')
    @require('admin', 'builder')
    def delete_job(job_id):
        accessible_job(job_id)
        from server.cleanup import delete_build
        delete_build(store, job_id, g.user)
        return jsonify(ok=True)

    @app.get('/api/jobs/<job_id>/logs')
    @require()
    def logs(job_id):
        accessible_job(job_id)
        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            raise APIError('Invalid log offset.')
        file = store.root / 'logs' / (job_id + '.log')
        if not file.is_file():
            return jsonify(text='', offset=0, truncated=False)
        size = file.stat().st_size
        start = min(size, max(offset, size - 256 * 1024))
        with file.open('rb') as stream:
            stream.seek(start)
            content = stream.read(256 * 1024)
        return jsonify(text=content.decode('utf-8', errors='replace'), offset=start + len(content), truncated=start > offset)

    @app.get('/api/artifacts/<artifact_id>/download')
    @require()
    def download(artifact_id):
        artifact = store.artifact(artifact_id)
        if not artifact or (g.user['role'] != 'admin' and artifact['project'] not in g.user['projects']):
            raise APIError('Artifact not found.', 404)
        path = Path(artifact['path']).resolve()
        job = store.job(artifact['job_id'])
        if not job or job['status'] == 'deleting':
            raise APIError('This build is being deleted.', 409)
        if not path.is_relative_to((store.root / 'artifacts' / artifact['job_id']).resolve()) or path.suffix not in ('.apk', '.aab') or not path.is_file():
            raise APIError('Artifact file is no longer available.', 404)
        store.audit(g.user['username'], 'artifact.download', artifact_id)
        return send_file(path, as_attachment=True, download_name=artifact['filename'], conditional=True,
                         mimetype='application/vnd.android.package-archive' if path.suffix == '.apk' else 'application/octet-stream')

    @app.get('/api/users')
    @require('admin')
    def users():
        return jsonify(users=store.users())

    @app.post('/api/users')
    @require('admin')
    def create_user():
        data = body()
        user = store.create_user(data.get('username'), data.get('password'), data.get('role'), data.get('projects'), data.get('display_name', ''))
        store.audit(g.user['username'], 'user.created', user['username'])
        return jsonify(user=user), 201

    @app.patch('/api/users/<user_id>')
    @require('admin')
    def update_user(user_id):
        data = body()
        if not isinstance(data.get('enabled'), bool):
            raise APIError('Enabled must be true or false.')
        password = data.get('password') or None
        store.update_user(user_id, g.user['id'], data.get('role'), data.get('projects'), data['enabled'], password)
        store.audit(g.user['username'], 'user.updated', user_id)
        return jsonify(ok=True)

    @app.get('/api/config')
    @require('admin')
    def config():
        settings = store.settings()
        settings.setdefault('MAX_PARALLEL_BUILDS', str(store.max_parallel_builds()))
        return jsonify(values={k: v for k, v in settings.items() if k in PUBLIC_FIELDS},
                       secrets_set={k: bool(settings.get(k)) for k in SECRET_FIELDS},
                       storage=str(store.root))

    @app.put('/api/config')
    @require('admin')
    def save_config():
        data = body()
        values, clears = data.get('values', {}), data.get('clear_secrets', [])
        if not isinstance(values, dict) or not isinstance(clears, list) or any(not isinstance(k, str) for k in clears):
            raise APIError('Invalid configuration payload.')
        store.save_settings(values, clears)
        store.audit(g.user['username'], 'settings.updated')
        return jsonify(ok=True)

    @app.get('/api/audit')
    @require('admin')
    def audit():
        with store.connect() as db:
            items = [dict(row) for row in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]
        return jsonify(events=items)

    return app
