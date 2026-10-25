"""Flutter operations use explicit working directories."""
import os
from pathlib import Path
import yaml
from modules.process_runner import run_command

def run_flutter(project, args, label):
    return run_command(['flutter', *args], Path(os.environ['GIT_WORKSPACE']) / project, label)

def clean(project):
    run_flutter(project, ['clean'], 'Clean workspace')

def pub_get(project):
    run_flutter(project, ['pub', 'get'], 'Resolve dependencies')

def intl_generate(project):
    spec = Path(os.environ['GIT_WORKSPACE']) / project / 'pubspec.yaml'
    data = yaml.safe_load(spec.read_text(encoding='utf-8')) or {}
    if data.get('flutter_intl', {}).get('enabled', False):
        run_flutter(project, ['pub', 'run', 'intl_utils:generate'], 'Generate localization')
    else:
        print('Localization skipped (flutter_intl is not enabled).')

def build_debug(project):
    run_flutter(project, ['build', 'apk', '--debug'], 'Build debug APK')

def build_release(project):
    run_flutter(project, ['build', 'apk', '--release'], 'Build release APK')

def build_appbundle(project):
    run_flutter(project, ['build', 'appbundle', '--release'], 'Build Android App Bundle')
