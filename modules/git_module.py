"""Non-destructive repository synchronization."""
import json
import os
import subprocess
from pathlib import Path
from modules.process_runner import run_command

def source_for(project):
    """(clone url, branch) from the job's frozen per-project source, falling back to legacy global settings."""
    try:
        source = json.loads(os.getenv('PROJECT_SOURCES') or '{}').get(project, {})
    except ValueError:
        source = {}
    branch = os.getenv('GIT_BRANCH', '').strip() or source.get('branch') or 'main'
    url = source.get('url') or ''
    if not url:
        owner = os.getenv('GIT_USER', '').strip()
        if owner:
            url = f'https://github.com/{owner}/{project}.git'
    return url, branch

def branch_for(project):
    return source_for(project)[1]

def git_clone(project):
    workspace = Path(os.environ['GIT_WORKSPACE']).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    destination = workspace / project
    url, branch = source_for(project)
    if destination.exists():
        if not (destination / '.git').exists():
            raise ValueError(f'{destination} is not a Git repository.')
        dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=destination, text=True)
        if dirty.strip():
            raise ValueError(f'{project} has local changes. Commit or stash them before building.')
        run_command(['git', 'fetch', 'origin', branch], destination, 'Fetch source')
        run_command(['git', 'checkout', branch], destination, 'Switch branch')
        run_command(['git', 'merge', '--ff-only', 'FETCH_HEAD'], destination, 'Update source')
    else:
        if not url:
            raise ValueError(f'Set the GitHub repository URL for {project} before cloning.')
        # Private repositories use Git Credential Manager; tokens never enter URLs.
        run_command(['git', 'clone', '--single-branch', '--branch', branch,
                     url, str(destination)], workspace, 'Clone repository')
    if not (destination / 'pubspec.yaml').is_file():
        raise ValueError(f'{project} does not contain pubspec.yaml.')
    return destination


def restore_clean(project):
    """Tenant setup rewrites tracked files and generates icons; discard them so the next sync starts clean."""
    destination = Path(os.environ['GIT_WORKSPACE']).expanduser().resolve() / project
    if (destination / '.git').exists():
        subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=destination, capture_output=True)
        subprocess.run(['git', 'clean', '-fd'], cwd=destination, capture_output=True)
