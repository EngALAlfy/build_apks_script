#!/usr/bin/env bash
# Rebuild the server EXE and deploy it to the startup task (Git Bash on Windows).
# Usage: scripts/deploy-server.sh [--force] [--no-build]
#   --force     restart even if builds are queued/running (they will be interrupted)
#   --no-build  redeploy the existing dist/APK Build Server.exe
set -euo pipefail

TASK_NAME="${TASK_NAME:-APK Builder Central Server}"
PORT="${PORT:-8080}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$LOCALAPPDATA/APKBuilderServer}"
FORCE=0; BUILD=1
for arg in "$@"; do
  case "$arg" in --force) FORCE=1 ;; --no-build) BUILD=0 ;; *) echo "Unknown option: $arg" >&2; exit 2 ;; esac
done

PY="${PYTHON:-python}"
cd "$ROOT"

# 1. Refuse to interrupt active builds unless forced.
if [[ -f "$DATA_DIR/server.sqlite3" && $FORCE -eq 0 ]]; then
  active=$("$PY" -I - "$DATA_DIR/server.sqlite3" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
print(db.execute("select count(*) from jobs where status in ('queued','running','cancel_requested','deleting')").fetchone()[0])
PYEOF
)
  if [[ "$active" != "0" ]]; then
    echo "$active build(s) are queued or running. Wait for them, or re-run with --force." >&2
    exit 1
  fi
fi

# 2. Tests, then build.
if [[ $BUILD -eq 1 ]]; then
  echo "== Running tests"; "$PY" -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -4
  echo "== Building EXE"; "$PY" -m PyInstaller --noconfirm --clean server.spec >/dev/null
fi
NEW="$ROOT/dist/APK Build Server.exe"
[[ -f "$NEW" ]] || { echo "Missing $NEW" >&2; exit 1; }

# 3. Find the registered executable, stop the task, replace it, start again, wait for health.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
  \$ErrorActionPreference = 'Stop'
  \$task = Get-ScheduledTask -TaskName '$TASK_NAME'
  if (-not \$task.Description.StartsWith('APKBuilder managed startup v1')) { throw 'Task is not managed by the APK Builder installer.' }
  if (\$task.Actions[0].Arguments -notmatch '-ExecutablePath \"([^\"]+)\"') { throw 'Cannot find the registered executable.' }
  \$target = \$Matches[1]
  Stop-ScheduledTask -TaskName '$TASK_NAME'
  Get-Process | Where-Object { \$_.Path -eq \$target } | ForEach-Object { & taskkill /PID \$_.Id /T /F | Out-Null }
  Start-Sleep -Seconds 2
  Copy-Item -LiteralPath '$(cygpath -w "$NEW")' -Destination \$target -Force
  Start-ScheduledTask -TaskName '$TASK_NAME'
  \$deadline = (Get-Date).AddSeconds(40)
  while ((Get-Date) -lt \$deadline) {
    try { if ((Invoke-RestMethod 'http://127.0.0.1:$PORT/health' -TimeoutSec 2).status -eq 'ok') { Write-Output \"Deployed to \$target. Server is healthy.\"; exit 0 } } catch { Start-Sleep -Milliseconds 500 }
  }
  throw 'Server did not become healthy. Check startup/server-error.log in the data directory.'
"
echo "Done. Refresh the dashboard with Ctrl+F5."
