"""Atomic, thread-safe artifact history."""
import json
import os
import tempfile
from datetime import datetime
from threading import RLock
from uuid import uuid4
from utils.app_paths import HISTORY_FILE

_lock = RLock()

def get_history():
    with _lock:
        try:
            with open(HISTORY_FILE, encoding='utf-8') as stream:
                data = json.load(stream)
            if not isinstance(data, list) or any(not isinstance(e, dict) for e in data):
                raise ValueError('Build history must be a list of records.')
            return data
        except FileNotFoundError:
            return []

def save_history(history):
    with _lock:
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(HISTORY_FILE)), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(history, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, HISTORY_FILE)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

def add_entry(project_key, project_name, build_type, global_time, local_path, urls,
              mega_handles=None, discord_message_ids=None):
    with _lock:
        entry = dict(id=uuid4().hex, timestamp=datetime.now().isoformat(), project_key=project_key,
                     project_name=project_name, build_type=build_type, global_time=global_time,
                     local_path=local_path, urls=urls, mega_handles=mega_handles or {},
                     discord_message_ids=discord_message_ids or [])
        save_history([entry, *get_history()][:500])
        return entry['id']

def update_entry(entry_id, **updates):
    with _lock:
        history = get_history()
        for entry in history:
            if entry['id'] == entry_id:
                entry.update(updates)
                break
        save_history(history)

def remove_entry(entry_id):
    with _lock:
        save_history([e for e in get_history() if e['id'] != entry_id])
