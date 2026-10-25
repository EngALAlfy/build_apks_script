"""Stable application paths, independent of subprocess working directories."""
import sys
from pathlib import Path

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
SETTINGS_FILE = APP_DIR / ".env"
HISTORY_FILE = APP_DIR / "build_history.json"
