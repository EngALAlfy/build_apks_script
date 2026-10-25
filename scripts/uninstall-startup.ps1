[CmdletBinding()]
param([string]$DataDirectory = (Join-Path $env:LOCALAPPDATA 'APKBuilderServer'))
$ErrorActionPreference = 'Stop'
$apkTaskName = 'APK Builder Central Server'
$apkTask = Get-ScheduledTask -TaskName $apkTaskName -ErrorAction SilentlyContinue
if ($apkTask) {
    if (-not $apkTask.Description.StartsWith('APKBuilder managed startup v1')) { throw 'This task is not managed by the APK Builder startup installer.' }
    Stop-ScheduledTask -TaskName $apkTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $apkTaskName -Confirm:$false
}
$apkRecordPath = Join-Path $DataDirectory 'startup\managed-process.json'
if (Test-Path -LiteralPath $apkRecordPath) {
    $apkRecord = Get-Content -LiteralPath $apkRecordPath -Raw | ConvertFrom-Json
    $apkManaged = Get-Process -Id $apkRecord.ProcessId -ErrorAction SilentlyContinue
    if ($apkManaged -and $apkManaged.Path -eq $apkRecord.ExecutablePath -and $apkManaged.StartTime.ToUniversalTime().ToString('o') -eq $apkRecord.StartedAtUtc) {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $apkManaged.Id /T /F | Out-Null
    }
    Remove-Item -LiteralPath $apkRecordPath
}
Write-Output 'APK Builder automatic startup removed. Accounts, settings, queue, and artifacts were kept.'
