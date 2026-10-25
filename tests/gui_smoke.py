"""Run manually on a Windows desktop: python tests/gui_smoke.py."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bin.gui import App
from modules.build_service import BuildPlan
from utils import settings_utils, history_utils

with tempfile.TemporaryDirectory() as folder, patch.object(settings_utils, 'load_settings', return_value={
        'BUILD_TYPES': 'release', 'PROJECTS_REPOS': 'hurryApp,BranchManager'}), patch.object(
        history_utils, 'HISTORY_FILE', Path(folder) / 'history.json'):
    app = App()
    try:
        app.update()
        for page in app.pages:
            app.show_page(page)
            app.update()
            assert app.pages[page].winfo_ismapped(), page
        app.geometry('1120x740')
        app.show_page('Build workspace')
        app.update()
        assert app.metrics['jobs'].cget('text') == '2'
        app.select_projects(True)
        assert app.metrics['jobs'].cget('text') == '5'
        app.logs.put('worker log test\n')
        app.drain_logs()
        assert 'worker log test' in app.console.get('1.0', 'end')
        app.select_projects(False)
        app.project_vars['hurryApp'].set(True)
        app.update_selection()
        artifact = Path(folder) / 'release.apk'
        artifact.write_bytes(b'APK')
        def fake_build(project, stamp, stage, record):
            stage('Building release')
            record('release', str(artifact))
            return {'release': str(artifact)}
        with patch.object(BuildPlan, 'validate', return_value=[]), patch.object(settings_utils, 'save_settings'), patch(
                'modules.build_service.build_project_module.build_project', side_effect=fake_build):
            app.start_build()
            assert app.busy
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                app.update()
                time.sleep(.01)
            assert not app.busy
            assert app.status.cget('text') == 'COMPLETE'
            assert app.start_btn.cget('state') == 'normal'
            assert app.project_status['hurryApp'].cget('text') == 'Complete'
            assert len(history_utils.get_history()) == 1
    finally:
        app.destroy_app()
print('Desktop smoke passed: navigation, minimum size, metrics, logging, background build, progress, history, control recovery.')
