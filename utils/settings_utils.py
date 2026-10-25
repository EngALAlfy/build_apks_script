"""Persist settings beside the application, without relying on cwd."""
import os
import re
from dotenv import dotenv_values, set_key
from utils.app_paths import SETTINGS_FILE

SECRET_KEYS = ('MEGA_PASSWORD', 'FTP_PASS', 'EMAIL_PASSWORD', 'DISCORD_WEBHOOK', 'SLACK_WEBHOOK', 'GIT_TOKEN')

def load_settings():
    return {**os.environ, **{k: v for k, v in dotenv_values(SETTINGS_FILE).items() if v is not None}}

def save_settings(settings):
    SETTINGS_FILE.touch(exist_ok=True)
    for key, value in settings.items():
        set_key(str(SETTINGS_FILE), key, str(value))
        os.environ[key] = str(value)

def redact(text):
    for key in SECRET_KEYS:
        secret = os.getenv(key, '')
        if secret:
            text = text.replace(secret, '[redacted]')
    text = re.sub(r'/api/webhooks/\d+/[^?\s/]+', '/api/webhooks/[redacted]', text)
    text = re.sub(r'https://hooks\.slack(?:-gov)?\.com/services/[^\s<>\x22\x27]+', '[Slack webhook redacted]', text)
    return re.sub(r'https://[^\s/@]+:[^\s/@]+@', 'https://[redacted]@', text)
