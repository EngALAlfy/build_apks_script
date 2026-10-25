"""Slack incoming-webhook adapter; no workspace tokens or SDK required."""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests

from bin.constants import projects


def valid_webhook_url(value):
    """Restrict credentials to Slack's HTTPS incoming-webhook endpoints."""
    return bool(re.fullmatch(
        r'https://hooks\.slack(?:-gov)?\.com/services/'
        r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+', value or ''))


def _escape(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_payload(project, build_type, file_urls, session, artifact_path=None):
    """Use plain-text metadata and validated links; never include local folders."""
    name = projects.get(project, project)
    title = f'{name} / {build_type.upper()} ready'
    fields = [
        {'type': 'plain_text', 'text': f'Project\n{name}'},
        {'type': 'plain_text', 'text': f'Format\n{build_type.upper()}'},
        {'type': 'plain_text', 'text': f'Branch\n{os.getenv("GIT_BRANCH", "main")}'},
        {'type': 'plain_text', 'text': f'Session\n{session}'},
    ]
    links = []
    for service, url in file_urls.items():
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.username or parsed.password:
            continue
        # Slack link targets must not contain raw markup delimiters or whitespace.
        if any(c.isspace() or c in '<>|' for c in url):
            continue
        links.append(f'<{_escape(url)}|Download from {_escape(service.upper())}>')
    if not links:
        raise ValueError('Slack requires at least one valid HTTP or HTTPS download link.')
    blocks = [
        {'type': 'header', 'text': {'type': 'plain_text', 'text': title[:150]}},
        {'type': 'section', 'fields': fields},
        {'type': 'section', 'text': {'type': 'mrkdwn', 'text': '\n'.join(links)}},
    ]
    if artifact_path:
        blocks.append({'type': 'context', 'elements': [
            {'type': 'plain_text', 'text': f'Artifact: {Path(artifact_path).name}'[:2000]}]})
    return {'text': _escape(title), 'blocks': blocks, 'unfurl_links': False, 'unfurl_media': False}


def send_to_slack(project, build_type, file_urls, session, artifact_path=None):
    """Return True only for Slack's HTTP 200 / ok acknowledgement.

    A timeout has an unknown delivery outcome. Do not retry automatically or print
    request exceptions, since they can contain the secret webhook URL.
    """
    if os.getenv('SLACK_ENABLED', 'false').lower() != 'true':
        return None
    webhook = os.getenv('SLACK_WEBHOOK', '').strip()
    if not valid_webhook_url(webhook):
        print('Slack notification failed: configure a valid Slack incoming webhook URL.')
        return False
    try:
        payload = build_payload(project, build_type, file_urls, session, artifact_path)
        response = requests.post(webhook, json=payload, timeout=(5, 20), allow_redirects=False)
    except requests.Timeout:
        print('Slack notification timed out. Delivery is unknown; check the channel before retrying.')
        return False
    except requests.RequestException:
        print('Slack notification failed: connection or HTTP transport error. Check connectivity and webhook configuration.')
        return False
    except ValueError as exc:
        print(f'Slack notification failed: {exc}')
        return False
    if response.status_code == 200 and response.text.strip() == 'ok':
        print(f'[{projects.get(project, project)}][{build_type}] Slack notification sent.')
        return True
    if response.status_code == 429:
        print('Slack rate limit reached. No automatic retry was attempted; check the channel before retrying.')
    else:
        print(f'Slack notification rejected (HTTP {response.status_code}). Check the webhook, channel, and workspace permissions.')
    return False
