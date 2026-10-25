# Standalone executable and configuration

## Build and distribute one file

From the project directory:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm main.spec
```

The output is `dist/APK Builder.exe`. Copy that executable to the destination computer. Python, application packages, and CustomTkinter assets are bundled. No `.env`, `.env.example`, JSON file, or application folder needs to accompany it.

Git and the Flutter SDK are external build tools and must still be installed and available on `PATH`. Private repositories require Git authentication on that computer. The executable does not contain your account credentials or existing configuration.

## First launch

1. Launch the executable from any folder.
2. Enter the source workspace, artifact directory, GitHub owner, and branch in **Build settings**.
3. Configure any required delivery and notification providers in **Distribution**.
4. Save settings. The app creates its user profile directory automatically.
5. Select projects and formats, validate setup, and start a build.

Saving settings or starting a build persists the configuration. Merely editing a field does not save it. Moving or updating the executable preserves configuration for the same Windows user because storage is independent of the executable folder.

## Storage locations

| Data | Windows path | Created when |
| --- | --- | --- |
| Configuration | `%LOCALAPPDATA%\APKBuilder\settings.json` | Settings are first saved or a build starts |
| Artifact history | `%LOCALAPPDATA%\APKBuilder\build_history.json` | Artifact history is first changed |
| APK/AAB files | The artifact directory selected in the app | A build collects output |

If `LOCALAPPDATA` is unavailable, the Windows fallback is the user's `AppData\Local` directory. Source runs use the same profile as the executable. Non-Windows source runs use `$XDG_DATA_HOME/APKBuilder`, or `~/.local/share/APKBuilder` when that variable is absent.

The app does not write settings or history beside the executable. This supports installation folders that are not writable by the current user. PyInstaller may use a temporary extraction directory for the bundled runtime; that is separate from persistent settings.

## Existing installations

Existing `.env` and `build_history.json` files remain compatible through read-only migration:

- If the profile settings file is absent, the app can load an existing `.env` beside the source entry point or executable. The next save writes its values into the profile JSON. It leaves the original `.env` unchanged.
- Once profile settings exist, the app uses them instead of the adjacent `.env`. Clearing a saved field therefore does not restore an old legacy value.
- If profile history is absent, existing adjacent history is read. The next history update copies the current records into the profile history file and leaves the old file unchanged.
- No legacy file is needed for a fresh installation. You can enter all settings in the UI.

Precedence is saved profile settings, otherwise legacy `.env` settings, over process environment variables. With neither configuration file, the app uses available environment variables and UI defaults.

## Privacy and backups

Configuration JSON contains the credentials you enter as plain strings. Keep it private. Password and webhook fields are masked in the UI, and known secrets are redacted in Console/exported logs. Settings and history are never added to the PyInstaller package.

To move configuration to another Windows account or computer, configure it in the UI there, or privately copy the profile files into that user's profile directory. Local artifact paths and build-tool installation paths may need updating. Keep backups of profile files if you need to recover settings or history.

Malformed saved configuration is reported instead of silently overwritten. Repair or restore the JSON from a backup before saving again. For a deliberate reset, close the app and rename the profile settings file yourself; an adjacent legacy `.env` will be imported again if present.

## Verification

```powershell
python -m unittest discover -s tests -v
python tests/gui_smoke.py
```

`tests/test_settings_storage.py` verifies fresh startup with no files, profile-only writes, reloads, legacy imports, malformed JSON, atomic-write failure recovery, and storage that does not depend on the executable location. Tests use temporary directories and do not alter real user settings.
