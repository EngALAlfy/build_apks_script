"""Subprocess fixture; never clones a repository, uploads, or sends notifications."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.worker import run_worker
from modules.process_runner import run_command


def fake_build(project, stamp, stage, record):
    stage('Fixture compilation')
    if sys.argv[3] == 'slow':
        run_command([sys.executable, '-c', 'import time; print("fixture child running", flush=True); time.sleep(30)'], Path(os.environ['GIT_WORKSPACE']).parent, 'Fixture child')
    artifact = Path(os.environ['RESULT_WORKSPACE']) / stamp / project / (project + '-1.0-release.apk')
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b'ISOLATED-TEST-ARTIFACT')
    print('Fixture console output')
    print('\u221a Flutter success / \u2713 verified / العربية / \U0001f680')
    record('release', str(artifact))
    return {'release': str(artifact)}


with patch('modules.build_service.BuildPlan.validate', return_value=[]), patch('modules.build_service.build_project_module.build_project', side_effect=fake_build):
    raise SystemExit(run_worker(sys.argv[1], sys.argv[2]))
