"""Non-destructive repository synchronization."""
import os
import subprocess
from pathlib import Path
from modules.process_runner import run_command

def git_clone(project):
    workspace = Path(os.environ['GIT_WORKSPACE']).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    destination = workspace / project
    branch = os.getenv('GIT_BRANCH', 'main').strip()
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
        owner = os.getenv('GIT_USER', '').strip()
        if not owner:
            raise ValueError('Set the GitHub owner in Build settings before cloning.')
        # Private repositories use Git Credential Manager; tokens never enter URLs.
        run_command(['git', 'clone', '--single-branch', '--branch', branch,
                     f'https://github.com/{owner}/{project}.git', str(destination)], workspace, 'Clone repository')
    if not (destination / 'pubspec.yaml').is_file():
        raise ValueError(f'{project} does not contain pubspec.yaml.')
    return destination
