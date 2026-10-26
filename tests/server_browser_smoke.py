"""Optional end-to-end browser check. Requires playwright and installed Edge.
Run: python tests/server_browser_smoke.py
No repositories, uploads, or external notification channels are contacted.
"""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from waitress import create_server
from server.app import create_app
from server.runtime import Runtime

screens=Path(__file__).resolve().parents[1]/'test-output'/'server-browser'
screens.mkdir(parents=True,exist_ok=True)
errors=[]
with tempfile.TemporaryDirectory() as folder, patch('modules.build_service.BuildPlan.validate',return_value=[]):
    app=create_app(folder)
    store=app.config['STORE']
    app.config['DISCOVERY']=SimpleNamespace(status=lambda:dict(hostname='apk-builder.local',url='http://apk-builder.local:8080',status='advertised',addresses=['192.168.1.8']))
    http=create_server(app,host='127.0.0.1',port=0,threads=4)
    thread=threading.Thread(target=http.run,daemon=True)
    thread.start()
    url=f'http://localhost:{http.effective_port}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(url)
            expect(page.get_by_role('heading',name='Set up your workspace')).to_be_visible()
            page.screenshot(path=str(screens/'setup.png'),full_page=True,animations='disabled')
            auth=page.locator('#auth-form')
            auth.get_by_label('Full name',exact=True).fill('Release Administrator')
            auth.get_by_label('Username',exact=True).fill('release.admin')
            auth.get_by_label('Password',exact=True).fill('Test-Only-Password-123')
            page.get_by_role('button',name='Create administrator').click()
            expect(page.get_by_role('heading',name='Overview',exact=True)).to_be_visible()
            page.get_by_role('button',name='Server settings',exact=True).click()
            config=page.locator('#settings-form')
            expect(page.get_by_label('Shareable LAN address',exact=True)).to_have_value('http://apk-builder.local:8080')
            config.get_by_label('GitHub owner or organization',exact=True).fill('fixture-organization')
            config.get_by_role('button',name='Save configuration').click()
            expect(page.get_by_text('Server configuration saved. New builds will use these settings.',exact=True)).to_be_visible()
            page.get_by_role('button',name='Team & access',exact=True).click()
            page.get_by_role('button',name='Add member',exact=True).click()
            member=page.locator('#user-form')
            member.get_by_label('Full name',exact=True).fill('Team Viewer')
            member.get_by_label('Username',exact=True).fill('team.viewer')
            member.get_by_label('Role',exact=True).select_option('viewer')
            member.locator('input[name=password]').fill('Viewer-Only-Password-123')
            member.get_by_role('button',name='Save account',exact=True).click()
            expect(page.get_by_text('Team Viewer',exact=True)).to_be_visible()
            page.get_by_role('button',name='Overview',exact=True).click()
            page.get_by_role('button',name='New build',exact=True).click()
            expect(page.locator('#build-form input[value=debug]')).to_be_checked()
            expect(page.locator('#build-form input[value=release]')).not_to_be_checked()
            page.screenshot(path=str(screens/'new-build.png'),full_page=True,animations='disabled')
            with page.expect_response(lambda r:r.url.endswith('/api/jobs') and r.request.method=='POST') as response:
                page.locator('#build-form').get_by_role('button',name='Add to build queue').click()
            assert response.value.status==201,response.value.text()
            assert response.value.json()['job']['build_types']==['debug']
            job_id=response.value.json()['job']['id']
            expect(page.locator('#job-dialog')).to_be_visible()
            runtime=Runtime(store)
            fixture=Path(__file__).resolve().parent/'server_fixture_worker.py'
            runtime.command=lambda jid:[sys.executable,str(fixture),str(store.root),jid,'success']
            runtime.execute(store.claim())
            expect(page.locator('#job-meta .status')).to_have_text('completed',timeout=10000)
            expect(page.locator('.job-download a')).to_be_visible()
            with page.expect_download() as item:
                page.locator('.job-download a').click()
            target=Path(folder)/'downloaded.apk'
            item.value.save_as(target)
            assert target.read_bytes()==b'ISOLATED-TEST-ARTIFACT'
            expect(page.locator('#job-log')).to_contain_text('Fixture console output')
            page.screenshot(path=str(screens/'job-complete.png'),full_page=True,animations='disabled')
            page.locator('#job-dialog [data-close]').first.click()
            page.get_by_role('button',name='Overview',exact=True).click()
            page.screenshot(path=str(screens/'overview.png'),full_page=True,animations='disabled')
            page.get_by_role('button',name='Artifacts',exact=True).click()
            expect(page.locator('.artifact-card')).to_be_visible()
            expect(page.locator('.artifact-card .button svg')).to_have_css('width','19px')
            page.screenshot(path=str(screens/'artifacts.png'),full_page=True,animations='disabled')
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(screens/'mobile.png'),full_page=True,animations='disabled')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Mobile overflow'
            page.get_by_role('button',name='Toggle navigation').click()
            page.get_by_role('button',name='Overview',exact=True).click()
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_role('button',name='Sign out').click()
            expect(page.get_by_role('heading',name='Welcome back')).to_be_visible()
            auth.get_by_label('Username',exact=True).fill('team.viewer')
            auth.get_by_label('Password',exact=True).fill('Viewer-Only-Password-123')
            page.get_by_role('button',name='Sign in to workspace').click()
            expect(page.get_by_role('heading',name='Overview',exact=True)).to_be_visible()
            expect(page.get_by_role('button',name='New build',exact=True)).to_be_hidden()
            expect(page.get_by_role('button',name='Server settings',exact=True)).to_be_hidden()
            assert page.request.get(url+'/api/users').status==403
            assert page.request.get(url+'/api/config').status==403
            browser.close()
        assert not errors,errors
    finally:
        http.close()
        http.task_dispatcher.shutdown()
print('Browser end-to-end passed: first admin, settings, member creation, queue submission, isolated build, live logs, APK download, mobile navigation, and viewer access controls.')
