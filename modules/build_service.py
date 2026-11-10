"""UI-independent coordinator. Workers publish events; only Tk consumes them."""
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue
from threading import Thread
from pathlib import Path
from modules import build_project_module
from modules.process_runner import BuildCancelled, check_cancelled, cancel
from utils import history_utils
import bin.constants as constants

SERVICE_FIELDS = {
    'MEGA': ('MEGA_USERNAME', 'MEGA_PASSWORD'),
    'FTP': ('FTP_HOST', 'FTP_USER', 'FTP_PASS', 'FTP_BASE_URL'),
    'DISCORD': ('DISCORD_WEBHOOK',),
    'SLACK': ('SLACK_WEBHOOK',),
    'EMAIL': ('EMAILS', 'SMTP_HOST', 'SMTP_PORT', 'EMAIL_USER', 'EMAIL_PASSWORD'),
}

@dataclass(frozen=True)
class BuildPlan:
    projects: tuple
    build_types: tuple
    settings: dict
    tenants: dict = field(default_factory=dict)

    @property
    def units(self):
        """(project, tenant) pairs; tenant is None for projects without flavors."""
        return [(p, t) for p in self.projects for t in (self.tenants.get(p) or [None])]

    def validate(self):
        errors = []
        if not self.projects:
            errors.append('Select at least one project.')
        if not self.build_types:
            errors.append('Select at least one build format.')
        if any(p not in constants.projects for p in self.projects):
            errors.append('The project selection contains an unknown repository.')
        for project, picked in self.tenants.items():
            known = constants.project_tenants.get(project, [])
            if project not in self.projects or any(t not in known for t in picked):
                errors.append('The tenant selection contains an unknown tenant.')
        for project in self.projects:
            if constants.project_tenants.get(project) and not self.tenants.get(project):
                errors.append(f'Choose at least one tenant for {constants.projects.get(project, project)}.')
        if any(t not in constants.tasks for t in self.build_types):
            errors.append('The build selection contains an unknown format.')
        for key, title in [('GIT_WORKSPACE', 'Source workspace'), ('RESULT_WORKSPACE', 'Artifact directory')]:
            value = self.settings.get(key, '').strip()
            if not value:
                errors.append(f'{title} is required.')
            elif Path(value).exists() and not Path(value).is_dir():
                errors.append(f'{title} must be a directory.')
        branch = self.settings.get('GIT_BRANCH', '').strip()
        if branch and (branch.startswith('-') or any(c in branch for c in ' ~^:?*[\\') or '..' in branch):
            errors.append('Enter a valid Git branch name.')
        owner = self.settings.get('GIT_USER', '').strip()
        if owner and (owner.startswith('-') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in owner)):
            errors.append('GitHub owner must be a username or organization name.')
        if self.settings.get('GIT_WORKSPACE'):
            try:
                import json
                sources = json.loads(self.settings.get('PROJECT_SOURCES') or '{}')
            except ValueError:
                sources = {}
            for p in self.projects:
                if not owner and not sources.get(p, {}).get('url') and not (Path(self.settings['GIT_WORKSPACE']) / p / '.git').exists():
                    errors.append(f'Set the GitHub repository URL for {constants.projects.get(p, p)} in Projects.')
        if any(self.settings.get(k + '_ENABLED') == 'true' for k in ('DISCORD', 'EMAIL', 'SLACK')) and not any(
                self.settings.get(k + '_ENABLED') == 'true' for k in ('MEGA', 'FTP')):
            errors.append('Enable MEGA or FTP delivery to send notification download links.')
        for executable in ('git', 'flutter') + (('dart',) if any(self.tenants.values()) else ()):
            if not shutil.which(executable):
                errors.append(f'{executable.title()} was not found on PATH.')
        for service, fields in SERVICE_FIELDS.items():
            if self.settings.get(service + '_ENABLED') == 'true':
                missing = [f for f in fields if not self.settings.get(f, '').strip()]
                if missing:
                    errors.append(f'{service}: missing ' + ', '.join(missing))
        if self.settings.get('SLACK_ENABLED') == 'true' and self.settings.get('SLACK_WEBHOOK', '').strip():
            from modules.slack_module import valid_webhook_url
            if not valid_webhook_url(self.settings['SLACK_WEBHOOK'].strip()):
                errors.append('Slack requires an HTTPS incoming webhook URL on hooks.slack.com or hooks.slack-gov.com.')
        if self.settings.get('EMAIL_ENABLED') == 'true':
            try:
                if not 1 <= int(self.settings.get('SMTP_PORT', '')) <= 65535:
                    raise ValueError
            except ValueError:
                errors.append('SMTP port must be a number between 1 and 65535.')
        return errors

class BuildService:
    def __init__(self):
        self.events = Queue()
        self.worker = None

    @property
    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def emit(self, kind, **data):
        self.events.put((kind, data))

    def start(self, plan):
        if self.running:
            return False
        errors = plan.validate()
        if errors:
            raise ValueError('\n'.join(errors))
        constants.stop_requested = False
        self.worker = Thread(target=self._run, args=(plan,), daemon=True)
        self.worker.start()
        return True

    def stop(self):
        Thread(target=cancel, daemon=True).start()

    def delete_artifact(self, entry_id, output_root):
        if self.running:
            return False
        def work():
            try:
                from modules.artifact_service import delete_artifact
                errors = delete_artifact(entry_id, output_root)
            except Exception as exc:
                errors = [str(exc)]
            self.emit('maintenance_finished', errors=errors)
        self.worker = Thread(target=work, daemon=True)
        self.worker.start()
        return True

    def _run(self, plan):
        os.environ.update(plan.settings)
        os.environ['BUILD_TYPES'] = ','.join(plan.build_types)
        stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
        completed, failures, warnings = 0, [], []
        try:
            units = plan.units
            for index, (project, tenant) in enumerate(units):
                check_cancelled()
                label = f'{project} · {tenant}' if tenant else project
                title = f'{constants.projects[project]} · {tenant}' if tenant else constants.projects[project]
                self.emit('project', project=label, state='Running', progress=index / len(units))
                upload_key = f'{project}-{tenant}' if tenant else project
                entries = {}
                def record(kind, artifact):
                    nonlocal completed
                    entries[kind] = history_utils.add_entry(project, title, kind, stamp, artifact, {})
                    completed += 1
                    self.emit('artifact', path=artifact, count=completed)
                try:
                    artifacts = build_project_module.build_project(
                        project, stamp,
                        lambda stage: self.emit('stage', project=label, stage=stage), record, **({'tenant': tenant} if tenant else {}))
                    check_cancelled()
                    if any(plan.settings.get(k + '_ENABLED') == 'true' for k in ('MEGA', 'FTP')):
                        self.emit('stage', project=label, stage='Distributing artifacts')
                        try:
                            from modules import upload_module
                            results = upload_module.mass_upload([(upload_key, artifacts)], stamp).get(upload_key, {})
                            from modules import send_module
                            for kind, artifact in artifacts.items():
                                check_cancelled()
                                data = results.get(kind, {})
                                urls = data.get('urls', {})
                                meta = data.get('metadata', {})
                                expected = [s.lower() for s in ('MEGA', 'FTP') if plan.settings.get(s + '_ENABLED') == 'true']
                                if any(s not in urls for s in expected):
                                    warnings.append(f'{title} / {kind}: distribution incomplete')
                                # Persist upload handles before attempting notifications.
                                history_utils.update_entry(entries[kind], urls=urls,
                                    mega_handles={'mega': meta['mega_handle']} if meta.get('mega_handle') else {})
                                if urls:
                                    if plan.settings.get('SLACK_ENABLED') == 'true':
                                        from modules.slack_module import send_to_slack
                                        slack_ok = send_to_slack(upload_key, kind, urls, stamp, artifact)
                                        history_utils.update_entry(entries[kind], slack_notified=bool(slack_ok))
                                        if not slack_ok:
                                            warnings.append(f'{project} / {kind}: Slack notification was not acknowledged; check Console and the Slack channel before retrying')
                                    message = send_module.send_to_discord(f'{label} [{kind}]', urls, stamp, str(Path(artifact).parent))
                                    if plan.settings.get('DISCORD_ENABLED') == 'true' and not message:
                                        warnings.append(f'{project}: Discord notification failed')
                                    email_ok = send_module.send_to_email(f'{label} [{kind}]', urls, stamp, str(Path(artifact).parent))
                                    if plan.settings.get('EMAIL_ENABLED') == 'true' and not email_ok:
                                        warnings.append(f'{project}: email notification failed')
                                    history_utils.update_entry(entries[kind], discord_message_ids=[message] if message else [])
                        except BuildCancelled:
                            raise
                        except Exception as exc:
                            warnings.append(f'{project}: distribution failed: {exc}')
                            print(warnings[-1])
                    self.emit('project', project=label, state='Complete', progress=(index + 1) / len(units))
                except BuildCancelled:
                    raise
                except Exception as exc:
                    failures.append(f'{title}: {exc}')
                    print(f'BUILD FAILED: {failures[-1]}')
                    self.emit('project', project=label, state='Failed', progress=(index + 1) / len(units))
            self.emit('finished', state='Failed' if failures else ('Warning' if warnings else 'Complete'),
                      count=completed, errors=failures, warnings=warnings)
        except BuildCancelled:
            self.emit('finished', state='Cancelled', count=completed, errors=[], warnings=warnings)
        except Exception as exc:
            self.emit('finished', state='Failed', count=completed, errors=[str(exc)], warnings=warnings)
