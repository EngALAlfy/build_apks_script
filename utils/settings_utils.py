"""Per-user settings with read-only compatibility for legacy .env files."""
import json
import os
import re
import tempfile
from dotenv import dotenv_values
from utils.app_paths import SETTINGS_FILE, LEGACY_SETTINGS_FILE

SECRET_KEYS = ('MEGA_PASSWORD', 'FTP_PASS', 'EMAIL_PASSWORD', 'DISCORD_WEBHOOK', 'SLACK_WEBHOOK', 'GIT_TOKEN')

def _stored_settings():
    if SETTINGS_FILE.exists():
        with SETTINGS_FILE.open(encoding='utf-8') as stream:
            settings = json.load(stream)
        if not isinstance(settings, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in settings.items()):
            raise ValueError(f'Invalid settings file: {SETTINGS_FILE}. Expected string keys and values.')
        return settings
    if LEGACY_SETTINGS_FILE.is_file():
        return {k: v for k, v in dotenv_values(LEGACY_SETTINGS_FILE).items() if v is not None}
    return {}


def load_settings():
    return {**os.environ, **_stored_settings()}

def save_settings(settings):
    values = {**_stored_settings(), **{key: str(value) for key, value in settings.items()}}
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=SETTINGS_FILE.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(values, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, SETTINGS_FILE)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    os.environ.update(values)

def redact(text):
    for key in SECRET_KEYS:
        secret = os.getenv(key, '')
        if secret:
            text = text.replace(secret, '[redacted]')
    text = re.sub(r'/api/webhooks/\d+/[^?\s/]+', '/api/webhooks/[redacted]', text)
    text = re.sub(r'https://hooks\.slack(?:-gov)?\.com/services/[^\s<>\x22\x27]+', '[Slack webhook redacted]', text)
    return re.sub(r'https://[^\s/@]+:[^\s/@]+@', 'https://[redacted]@', text)
