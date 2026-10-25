# APK Builder

A Windows desktop release workspace for building and distributing multiple Flutter applications.

## Run

Use Python 3.11 or newer with Git and the Flutter SDK available on `PATH`.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Copy `.env.example` to `.env`, or enter settings in the app and save them. Settings and artifact history live beside `main.py` (or beside the executable when packaged). Existing `.env` settings remain compatible. Credentials are stored locally in `.env`; keep that file private and out of source control.

Private repository access uses Git Credential Manager. Authenticate Git before starting a build. `GIT_USER` is the GitHub username or organization owning the repositories; legacy token-bearing clone URLs are no longer created.

## Release workflow

1. Configure the source workspace, artifact directory, GitHub owner, and branch in **Build settings**.
2. Select applications and formats in **Build workspace**. Debug APK, release APK, and release App Bundle are supported.
3. Optionally enable MEGA or FTP delivery in **Distribution**. Email and Discord notifications require a delivery channel so they can include download links.
4. Validate setup, then start the build. Follow each project's stage or inspect live output in **Console**. Export a redacted log when troubleshooting.
5. Open **Artifacts** for searchable history, local folders, and delivery links. Local files enter history immediately after collection, even if later steps fail.

`Ctrl+Enter` starts a build; `Ctrl+S` saves settings. Configuration is locked during builds. Cancellation terminates active Git/Flutter process trees on Windows and checks between stages; FTP checks during transfer. An in-flight MEGA request or notification must finish before cancellation can complete.

Existing repositories must have a clean working tree. Updates fetch the selected branch, check it out, and merge with `--ff-only`. Local changes and diverged branches cause an actionable failure; the builder does not reset or discard work. Localization runs only when `flutter_intl.enabled` is set in `pubspec.yaml`. The builder does not add packages to project manifests.

Artifacts are grouped by unique session and project and retain the pubspec version in their filenames. App Bundles retain `.aab` when uploaded. Projects run sequentially; up to three artifact uploads can run concurrently.

## Artifact maintenance

**Forget record** only removes the history entry. **Delete artifact** confirms before removing the local APK/AAB, tracked MEGA file, and tracked Discord messages. Local deletion is restricted to the configured artifact directory. Partial cleanup retains history and remaining remote handles for retry. FTP files require separate removal on the server, as stated in the confirmation.

History retains the latest 500 records, and the UI shows up to 100 search results at a time. Console output is capped to keep long sessions responsive. Corrupt history is reported rather than silently overwritten.

## Architecture

- `bin/gui.py`: CustomTkinter view and main-thread event consumer. Background workers never access widgets. The view drains queued logs and structured build events on a timer.
- `modules/build_service.py`: validated build plans, single-run coordination, project isolation, artifact recording, distribution, and explicit completion/failure/cancellation outcomes.
- `modules/process_runner.py`: shared streamed subprocess execution, explicit working directories, and cancellation.
- `modules/build_project_module.py`: repository synchronization, dependency resolution, localization, build, and collection for one project.
- `modules/git_module.py`, `flutter_module.py`, `file_module.py`: source, build-tool, and filesystem adapters.
- `modules/upload_module.py`, `send_module.py`: optional delivery and notification adapters. The MEGA SDK loads only when used.
- `modules/artifact_service.py`: scoped cleanup and retry-safe partial deletion.
- `utils/history_utils.py`: locked read-modify-write operations and atomic replacement to avoid truncated history.
- `utils/app_paths.py`, `settings_utils.py`: stable paths, configuration persistence, and credential redaction.

One build coordinator owns execution. Settings are captured at start and applied to the legacy environment-based adapters while UI configuration is locked. This keeps current integrations compatible without introducing concurrent environment changes.

## Verify

```powershell
python -m compileall -q bin modules utils main.py
python -m unittest discover -s tests -v
python tests/gui_smoke.py
```

Regression tests isolate history and use temporary repositories, artifacts, and mocked delivery services. The GUI smoke test opens a temporary desktop window with isolated settings and exercises a simulated background build. Neither test sends notifications or uploads files. Live Flutter compilation and cloud delivery require the installed SDK, accessible repositories, and real service credentials.

## Packaging

```powershell
python -m pip install pyinstaller
python -m PyInstaller main.spec
```

The package excludes `.env` and build history. Distribute credentials separately. The generated application is a desktop window; the integrated Console carries process output.
