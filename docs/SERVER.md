# Central LAN build server

APK Builder can run as a central service on one Windows PC. Teammates use a browser to sign in, queue builds, follow logs, and download APK/AAB files. Only the server PC needs Git, Flutter, Android build tooling, and repository access.

## Start the server

### Windows executable

Launch **APK Build Server.exe** on the host PC. Its console prints the local dashboard and available LAN addresses, and the local dashboard opens in your browser. Keep the process running and the PC powered on, awake, and connected to the network.

No `.env`, Python installation, or companion configuration file is required. The application creates its data directory in `%LOCALAPPDATA%\APKBuilderServer` for the Windows account running the server. The executable includes dashboard assets and the Python runtime; Git, Flutter, and the Android SDK remain external tools.

### Run from source

From the repository root:

```powershell
python -m pip install -r requirements-server.txt
python server_main.py
```

Optional arguments:

```powershell
python server_main.py --host 0.0.0.0 --port 8080 --no-browser
python server_main.py --host 127.0.0.1 --port 8080 --data-dir D:/APKBuildServerData
```

The default listener is `0.0.0.0:8080`, which accepts connections on the host's network interfaces. `0.0.0.0` is a bind address: open the printed localhost or LAN URL in a browser. Binding to `127.0.0.1` limits access to this PC.

## First administrator and server setup

1. On the server PC, open `http://localhost:8080`.
2. Create the first administrator with your own username and a password of at least 12 characters. There are no default credentials. Initial administrator creation is allowed only from a loopback connection using a localhost/loopback host name; LAN visitors cannot claim the first account.
3. Open **Server settings** and enter the GitHub owner/organization and default branch. Save configuration. Source workspaces and output directories are managed by the server.
4. Authenticate Git as the Windows account running the server, including private repository access. Ensure Git, Flutter, Java/Android tooling, required SDKs, and signing configuration work for that account. Interactive Git prompts are disabled in build workers.
5. Configure optional MEGA/FTP delivery and Slack/Discord/email notifications if required. Direct LAN downloads work without any cloud provider.
6. Open **Team & access**, create accounts, select roles and permitted projects, and share account credentials privately with each teammate.
7. Share the printed LAN URL, for example `http://192.168.1.50:8080`. Each client needs only a modern browser and network access to that PC.

For LAN access, the host firewall must permit the selected TCP port on the intended private network. If Windows asks about network access, the PC owner should choose the intended network profile. This project does not change firewall rules, power settings, router settings, or create a Windows service automatically. No router port forwarding is required for clients on the same LAN. A DHCP reservation or stable host name keeps the shared address consistent.

## Roles and project permissions

| Role | Capabilities |
| --- | --- |
| Administrator | All projects, builds, downloads, cancellations, server settings, account management, and audit events. |
| Builder | Submit builds for permitted projects, view permitted jobs/logs, download permitted artifacts, and cancel their own builds. |
| Viewer | Browse permitted jobs/logs and download permitted artifacts. Cannot submit/cancel builds or manage settings/accounts. |

Job details and logs require access to every project in that job. Individual artifacts are accessible when the user has access to their project. Mixed-project jobs can therefore be hidden from a user while a permitted artifact remains downloadable. Administrators always have access to all projects.

Account changes revoke the account's existing sessions. Disabling an account blocks further access immediately. Queued work is checked again at dispatch; revoked build access prevents execution. A running build remains under administrator control and can be cancelled. The app prevents removing your own administrator access and requires at least one active administrator.

There is no public registration, anonymous artifact access, or shared default password. Accounts are local to this server rather than Windows/Active Directory accounts.

## Build workflow

1. Select **New build** and choose projects, formats, and branch.
2. Submit the request. The server validates the selected projects, formats, permissions, branch, tools, and integration configuration.
3. A durable FIFO queue starts one build at a time. Each account may have up to ten pending builds; the queue accepts up to 100 waiting requests.
4. Each build runs in its own OS process with a private configuration snapshot, Git checkout root, and artifact output root. Client requests cannot supply commands, repository URLs, arbitrary paths, or build-tool arguments.
5. Open the build for live log output and stage/progress information. The dashboard polls every 2.5 seconds while visible. You can close your browser without stopping the build.
6. Collected APK/AAB files enter the artifact library immediately. Downloads require authentication and project permission, include SHA-256 metadata, and use the stored artifact ID rather than a client-supplied path.
7. After a completed/failed/cancelled/interrupted build, **Build again** opens the same selection in a new build form. Submission uses the current server settings and a new workspace.

Branches and application choices come from the configured repository owner and the project catalog in `bin/constants.py`. Every build uses a fresh single-branch clone. Set up required per-user Git/Flutter/Gradle configuration on the server; per-repository untracked signing files are not copied from the old desktop workspace. Update the project catalog in code and rebuild to add applications in this version.

## Queue durability, cancellation, and shutdown

SQLite stores queue entries before the API acknowledges a submission. Settings are captured with each request, so administrator changes affect new submissions rather than changing queued builds halfway through.

A queued cancellation marks the job cancelled immediately. A running cancellation is observed by its worker and terminates active Git/Flutter processes. The scheduler allows a ten-second cancellation grace period, then terminates the worker process tree if necessary. Already collected artifacts remain available. External notifications or uploads already delivered are not recalled.

Press **Ctrl+C** in the server console for a graceful stop. Waiting jobs remain queued. If the process or PC stops abruptly, the next startup marks previously running jobs **interrupted** rather than retrying them silently; waiting jobs remain queued. Submit **Build again** to retry interrupted work. Windows worker job objects close with the server to avoid leaving build child processes running after the host exits.

Only one server process may own a data directory. Do not start multiple HTTP worker processes or multiple copies against the same data directory. Waitress supplies concurrent HTTP threads, while the scheduler owns exactly one build worker. This design supports small teams on a single build PC; it is not a distributed worker cluster.

## Storage and backups

```text
%LOCALAPPDATA%/APKBuilderServer/
  server.sqlite3           users, hashed passwords, sessions, queue, config, artifacts, audit
  server.sqlite3-wal       SQLite write-ahead log while running
  logs/<job-id>.log         redacted build output (20 MB cap per worker)
  workspaces/<job-id>/      isolated source checkouts
  artifacts/<job-id>/       collected APK/AAB files
  history/<job-id>.json     worker distribution and artifact metadata
  server.lock              process ownership lock
```

The old desktop app remains available and keeps its separate `%LOCALAPPDATA%/APKBuilder` profile. Desktop configuration is not automatically imported into the server. This prevents enabling external delivery channels or copying machine-specific workspace paths without administrator configuration.

Server configuration and queued configuration snapshots contain configured integration secrets in the local database. Protect the server data directory and backups. APIs return only secret-presence flags; blank secret fields preserve saved values, and explicit clear checkboxes remove them for future jobs. Old queued snapshots retain the values captured when submitted. Passwords use Werkzeug scrypt hashes. Browser sessions use expiring opaque cookies stored as hashes, CSRF tokens, HttpOnly and SameSite cookie attributes, and immediate server-side revocation.

Back up while the server is stopped, or use SQLite's backup facility; copying only the database while a WAL file is active can miss recent state. Keep artifact files with the database if download history must remain usable. Source workspaces, artifact files, job rows, and audit history are retained; there is no automatic disk-retention cleanup in this version. Monitor free space and manage old data during a maintenance window.

## HTTP and HTTPS

Workers isolate job configuration, source folders, and outputs; they are not an operating-system security sandbox. Build only trusted repository code under a dedicated server account with the permissions and credentials it needs.

The default endpoint is HTTP for a trusted local network. HTTP does not encrypt passwords, session cookies, logs, or downloaded artifacts on the wire. Use an HTTPS reverse proxy for networks where transport confidentiality is required. Bind the server to loopback behind that proxy and start it with `--secure-cookies` so cookies are sent only over HTTPS. Do not use `--secure-cookies` with plain HTTP or sign-in cannot persist.

The app does not enable CORS or trust forwarded-client headers. A proxy should preserve the external Host header and forward requests on the same hostname/origin. Bootstrap setup should still be performed directly through the local loopback dashboard before using a proxy. For background/service operation, use `--no-browser` and run under the Windows account that owns the configured Git/Flutter environment. This release does not install a service or configure TLS for you.

The production HTTP server is Waitress, following the Flask [Windows deployment guidance](https://flask.palletsprojects.com/en/stable/deploying/waitress/). Browser header and cookie protections follow Flask's [security guidance](https://flask.palletsprojects.com/en/stable/web-security/).

## Build the server EXE

```powershell
python -m pip install -r requirements-server.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm server.spec
```

The result is `dist/APK Build Server.exe`. Distribute only that executable to the host PC. Clients do not run it. The desktop executable is still built separately using `main.spec`.

## Verify

```powershell
python -m unittest discover -s tests -v
python tests/gui_smoke.py
# Optional browser test tooling, separate from runtime dependencies:
python -m pip install playwright
python tests/server_browser_smoke.py
# After building the executable:
python tests/server_exe_smoke.py "dist/APK Build Server.exe"
```

The browser smoke test uses installed Microsoft Edge and an isolated localhost server with temporary accounts. It creates a simulated build artifact, verifies a real download, and tests viewer controls. Subprocess tests run a fixture worker with a cancellable child process. They do not clone user repositories, perform Flutter builds, upload artifacts, or post to Slack/Discord/email.

Production Flutter compilation, code signing, real provider credentials, and connectivity from another physical LAN device require verification in your network environment.
