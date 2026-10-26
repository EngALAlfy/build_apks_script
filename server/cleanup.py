"""Remove exactly one stopped build's managed files and database records."""
import os
import re
import shutil
import stat
from pathlib import Path

from server.store import Conflict, TERMINAL


def _reparse(path):
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def managed_paths(root, job_id):
    if not re.fullmatch(r'[0-9a-f]{32}', job_id):
        raise ValueError('Invalid managed build ID.')
    root = Path(root).resolve()
    paths = [root / 'workspaces' / job_id, root / 'artifacts' / job_id,
             root / 'logs' / (job_id + '.log'), root / 'history' / (job_id + '.json')]
    # Validate every target before deleting anything. Never trust job settings or
    # artifact paths as deletion roots; only these fixed server-owned locations.
    for path in paths:
        if not path.parent.resolve().is_relative_to(root) or path.parent.resolve() == root:
            raise ValueError('Managed build directory points outside server storage.')
        if path.parent != path.parent.resolve():
            raise ValueError('Refusing to delete through a redirected storage directory.')
        if os.path.lexists(path):
            if _reparse(path) or path.resolve().parent != path.parent.resolve():
                raise ValueError('Refusing to delete a redirected build path.')
    return paths


def _remove_readonly(function, filename, error):
    path = Path(filename)
    # shutil.rmtree does not traverse symlinks/junctions. Its readonly fallback
    # must not chmod the target of one either.
    if path.is_symlink():
        path.unlink()
        return
    if _reparse(path):
        path.rmdir()
        return
    if not isinstance(error[1], PermissionError):
        raise error[1]
    path.chmod(stat.S_IWRITE | stat.S_IREAD)
    function(filename)


def delete_build(store, job_id, actor):
    paths = managed_paths(store.root, job_id)
    with store.connect(immediate=True) as db:
        current = store.public_user(db.execute('SELECT * FROM users WHERE id=?', (actor['id'],)).fetchone())
        if not current or not current['enabled']:
            raise PermissionError('This account no longer has access.')
        actor = current
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        job = store.decode_job(row)
        if not job or not store.can_view(actor, job):
            raise LookupError('Build not found.')
        if actor['role'] != 'admin' and (actor['role'] != 'builder' or job['user_id'] != actor['id']):
            raise PermissionError('You can delete only your own builds.')
        if job['worker_active'] or job['status'] not in TERMINAL | {'queued'}:
            raise Conflict('Cancel the build and wait for its worker to stop before deleting it.')
        db.execute("UPDATE jobs SET status='deleting',stage='Deleting local build files' WHERE id=?", (job_id,))
    try:
        for path in paths:
            if not os.path.lexists(path):
                continue
            # Check again immediately before removal; nested directory links are
            # unlinked by rmtree and their targets are not recursively traversed.
            managed_paths(store.root, job_id)
            if path.is_dir():
                shutil.rmtree(path, onerror=_remove_readonly)
            else:
                path.unlink()
    except Exception as exc:
        store.update_job(job_id, status='delete_failed', stage='Cleanup incomplete; close open files and retry deletion')
        store.audit(actor['username'], 'build.delete_failed', job_id)
        raise Conflict(f'Local cleanup was incomplete ({type(exc).__name__}). The build record was kept so deletion can be retried.')
    with store.connect(immediate=True) as db:
        db.execute('DELETE FROM artifacts WHERE job_id=?', (job_id,))
        db.execute('DELETE FROM jobs WHERE id=?', (job_id,))
    store.audit(actor['username'], 'build.deleted', job_id)
