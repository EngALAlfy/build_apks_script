"""Stable application paths, independent of subprocess working directories."""
import sys
import os
from pathlib import Path

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def user_data_dir():
    if os.name == 'nt':
        base = Path(os.getenv('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        base = Path(os.getenv('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'APKBuilder'


DATA_DIR = user_data_dir()
SETTINGS_FILE = DATA_DIR / 'settings.json'
HISTORY_FILE = DATA_DIR / 'build_history.json'
LEGACY_SETTINGS_FILE = APP_DIR / '.env'
LEGACY_HISTORY_FILE = APP_DIR / 'build_history.json'
