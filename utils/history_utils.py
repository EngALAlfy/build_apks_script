import json
import os
from datetime import datetime

HISTORY_FILE = 'build_history.json'

def get_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def add_entry(project_key, project_name, build_type, global_time, local_path, urls, mega_handles=None, discord_message_ids=None):
    history = get_history()
    entry = {
        "id": datetime.now().strftime('%Y%m%d%H%M%S%f'),
        "timestamp": datetime.now().isoformat(),
        "project_key": project_key,
        "project_name": project_name,
        "build_type": build_type,
        "global_time": global_time,
        "local_path": local_path,
        "urls": urls, # {mega: url, ftp: url}
        "mega_handles": mega_handles or {}, # {mega: handle}
        "discord_message_ids": discord_message_ids or [] # [msg_id1, msg_id2]
    }
    history.insert(0, entry) # Newest first
    # Keep only last 100 entries
    save_history(history[:100])
    return entry["id"]

def remove_entry(entry_id):
    history = get_history()
    history = [e for e in history if e["id"] != entry_id]
    save_history(history)
