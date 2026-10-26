[CmdletBinding()]
param(
    [string]$TaskName = 'APK Builder Central Server',
    [string]$DataDirectory = (Join-Path $env:LOCALAPPDATA 'APKBuilderServer'),
    [ValidateRange(1,65535)][int]$Port = 8080
)
$ErrorActionPreference = 'Stop'
$apkTask = Get-ScheduledTask -TaskName $TaskName
if (-not $apkTask.Description.StartsWith('APKBuilder managed startup v1')) {
    throw 'This task is not managed by the APK Builder startup installer.'
}
$apkRecordPath = Join-Path $DataDirectory 'startup\managed-process.json'
Stop-ScheduledTask -TaskName $TaskName
try {
    if (Test-Path -LiteralPath $apkRecordPath) {
        $apkRecord = Get-Content -LiteralPath $apkRecordPath -Raw | ConvertFrom-Json
        $apkManaged = Get-Process -Id $apkRecord.ProcessId -ErrorAction SilentlyContinue
        if ($apkManaged) {
            if ($apkRecord.StartedAtUtc -is [DateTime]) {
                $apkExpectedStart = $apkRecord.StartedAtUtc.ToUniversalTime().Ticks
            } else {
                $apkExpectedStart = [DateTimeOffset]::Parse([string]$apkRecord.StartedAtUtc).UtcDateTime.Ticks
            }
            if ($apkManaged.Path -ne $apkRecord.ExecutablePath -or $apkManaged.StartTime.ToUniversalTime().Ticks -ne $apkExpectedStart) {
                throw 'Process identity changed; refusing to stop an unrelated process.'
            }
            & "$env:SystemRoot\System32\taskkill.exe" /PID $apkManaged.Id /T /F | Out-Null
            if (-not $apkManaged.WaitForExit(5000)) { throw 'The managed server did not stop in time.' }
        }
    }
} finally {
    Start-ScheduledTask -TaskName $TaskName
}
$apkDeadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $apkDeadline) {
    try {
        $apkHealth = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Port + '/health') -TimeoutSec 2
        if ($apkHealth.status -eq 'ok') {
            Write-Output ('Server restarted successfully. Dashboard: http://apk-builder.local:' + $Port)
            Write-Output 'Restart uses the installed EXE. Source changes require rebuilding and replacing that EXE. Refresh the dashboard with Ctrl+F5 after an update.'
            return
        }
    } catch { }
    Start-Sleep -Milliseconds 300
}
throw 'The startup task was started, but server health was not confirmed. Check startup/server-error.log in the data directory.'
