"""Artifact cleanup retains history when any requested deletion fails."""
from pathlib import Path
from utils import history_utils


def delete_artifact(entry_id, output_root):
    entry = next((e for e in history_utils.get_history() if e.get('id') == entry_id), None)
    if entry is None:
        raise ValueError('The artifact record no longer exists.')
    errors = []
    local = entry.get('local_path')
    if local and Path(local).exists():
        target = Path(local).resolve()
        if not output_root or not target.is_relative_to(Path(output_root).resolve()) or target == Path(output_root).resolve():
            raise ValueError('The artifact is outside the configured artifact directory. Local deletion was refused.')
        if target.suffix.lower() not in ('.apk', '.aab') or not target.is_file():
            raise ValueError('Only APK and App Bundle files can be deleted.')
        try:
            target.unlink()
        except OSError as exc:
            errors.append(f'Local file: {exc}')
    handles = dict(entry.get('mega_handles', {}))
    if handles.get('mega'):
        from modules.upload_module import delete_from_mega
        if delete_from_mega(handles['mega']):
            handles.pop('mega')
        else:
            errors.append('MEGA deletion failed. Check the account and connection, then retry.')
    remaining_messages = []
    if entry.get('discord_message_ids'):
        from modules.send_module import delete_from_discord
        for message in entry['discord_message_ids']:
            if not delete_from_discord(message):
                remaining_messages.append(message)
                errors.append(f'Discord message {message} could not be removed.')
    if errors:
        history_utils.update_entry(entry_id, mega_handles=handles, discord_message_ids=remaining_messages)
    else:
        history_utils.remove_entry(entry_id)
    return errors
