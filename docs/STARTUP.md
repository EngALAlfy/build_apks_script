# Automatic Windows startup

Dashboard accounts and the Windows run-as account serve different purposes. Teammates keep their own administrator/builder/viewer dashboard accounts. Windows uses the host account to run Git, Flutter, and the server and read its existing configuration. The installer uses your existing Windows account; it does not create a new account or change dashboard users.

## Start after Windows sign-in

Run from the project directory:

```powershell
.\scripts\install-startup.ps1 -StartupMode Logon -StartNow
```

This registers **APK Builder Central Server** in Task Scheduler for the current user, with a 15-second logon delay. No Windows password is required. It starts after that account signs in, not before sign-in, and stops when the account signs out. Existing saved Git credentials and the server profile stay under the same Windows identity.

## Start at boot, before anyone signs in

```powershell
.\scripts\install-startup.ps1 -StartupMode Boot -StartNow
```

Windows prompts locally for the current Windows account password, then registers the task with a 30-second boot delay and password logon. Enter the Windows password in that local prompt, not a dashboard password and not in a chat. Windows Task Scheduler manages the credentials; the installer does not put the password in files, logs, or command-line arguments. This mode may require an elevated PowerShell window and the account's permission to run batch tasks. A Windows Hello PIN is not the account password. Update the task credentials if the Windows password changes.

The password-backed task is needed for unattended operation with the same profile and access to network/Git credentials. The installer deliberately avoids a passwordless S4U task because that mode does not provide normal access to network resources or encrypted credentials. See Microsoft's [task logon types](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype) and [startup/logon triggers](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger).

## Background behavior

- Neither the supervisor nor server opens a visible window or browser. The server always receives `--no-browser`.
- The supervisor waits if another server already owns the same data directory; it does not stop the manually started instance. When that instance stops, the supervisor takes over.
- If its server exits, the supervisor restarts it after ten seconds. Task Scheduler also retries a failed supervisor up to three times.
- Only one task instance runs, there is no automatic 72-hour execution limit, and switching to battery does not stop the task. The installer does not change Windows sleep or power settings.
- Server accounts, configuration, queue, and artifacts stay in `%LOCALAPPDATA%\APKBuilderServer` unless a data directory is supplied.
- Startup diagnostics go in `startup/supervisor.log`, `startup/server-output.log`, and `startup/server-error.log` under the server data directory. Output/error logs describe the latest launch; the supervisor log rotates at 1 MB.

Keep the installed executable and runner script at their registered paths. The installer can also run beside the EXE when the release folder contains `install-startup.ps1`, `run-server.ps1`, and `uninstall-startup.ps1`.

## Restart the running server

Wait for active builds to finish, then run from the project directory:

```powershell
.\scripts\restart-server.ps1
```

From any PowerShell directory:

```powershell
& "D:\BuildAPKsSystem\build_apks_script\scripts\restart-server.ps1"
```

The helper stops the managed task and any verified remaining server process, starts the same registered task again, and checks local server health. It keeps all accounts, settings, queue entries, and artifacts, and does not open a browser. Restarting during a build interrupts that build. A pre-existing manually started server is not terminated by this helper. The release folder also contains a copy of `restart-server.ps1`.

## Check, start, stop, or uninstall

```powershell
Get-ScheduledTask -TaskName 'APK Builder Central Server'
Get-ScheduledTaskInfo -TaskName 'APK Builder Central Server'
Start-ScheduledTask -TaskName 'APK Builder Central Server'
# Remove automatic startup and stop only the server launched by its supervisor:
.\scripts\uninstall-startup.ps1
```

Uninstalling leaves dashboard accounts, settings, queue, logs, and artifact files intact. A pre-existing manually started server is not stopped. A reboot was not required to install the task; use `-StartNow` for immediate background supervision.

For runtime verification without changing startup tasks or user data, run `python tests/startup_smoke.py`. It launches an isolated supervisor on localhost and checks restart behavior. The test does not perform builds or send notifications.
