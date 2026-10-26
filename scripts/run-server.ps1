[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExecutablePath,
    [Parameter(Mandatory = $true)][string]$DataDirectory,
    [string]$BindAddress = '0.0.0.0',
    [string]$LanName = 'apk-builder',
    [string]$LanInterface = '',
    [switch]$NoMdns,
    [ValidateRange(1,65535)][int]$Port = 8080
)
$ErrorActionPreference = 'Stop'
$apkExecutable = (Resolve-Path -LiteralPath $ExecutablePath).ProviderPath
$apkDataPath = [IO.Path]::GetFullPath($DataDirectory)
foreach ($apkArgument in @($apkExecutable,$apkDataPath,$BindAddress,$LanName,$LanInterface)) {
    if ($apkArgument.Contains('"') -or $apkArgument.Contains("`r") -or $apkArgument.Contains("`n")) { throw 'Startup arguments cannot contain quotes or newlines.' }
}
$apkLogPath = Join-Path $apkDataPath 'startup'
New-Item -ItemType Directory -Path $apkLogPath -Force | Out-Null
$apkStatusLog = Join-Path $apkLogPath 'supervisor.log'
$apkProcessRecord = Join-Path $apkLogPath 'managed-process.json'

function Write-ApkStatus([string]$Message) {
    if ((Test-Path -LiteralPath $apkStatusLog) -and (Get-Item -LiteralPath $apkStatusLog).Length -gt 1MB) {
        Move-Item -LiteralPath $apkStatusLog -Destination ($apkStatusLog + '.previous') -Force
    }
    Add-Content -LiteralPath $apkStatusLog -Value ((Get-Date -Format o) + ' ' + $Message) -Encoding UTF8
}

function Test-ApkServerLock {
    $apkProbe = $null
    try {
        $apkProbe = [IO.File]::Open((Join-Path $apkDataPath 'server.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
        $apkProbe.Lock(0,1)
        $apkProbe.Unlock(0,1)
        return $false
    } catch [IO.IOException] {
        return $true
    } finally {
        if ($null -ne $apkProbe) { $apkProbe.Dispose() }
    }
}

Write-ApkStatus 'Startup supervisor started. Browser launch is disabled.'
$apkWaitingReported = $false
while ($true) {
    try {
        if (Test-ApkServerLock) {
            if (-not $apkWaitingReported) {
                Write-ApkStatus 'An existing server owns this data directory. Waiting without interrupting it.'
                $apkWaitingReported = $true
            }
            Start-Sleep -Seconds 5
            continue
        }
        $apkWaitingReported = $false
        $apkArgumentLine = '--no-browser --host "' + $BindAddress + '" --port ' + $Port + ' --data-dir "' + $apkDataPath.TrimEnd('\') + '"'
        if ($NoMdns) { $apkArgumentLine += ' --no-mdns' } else { $apkArgumentLine += ' --lan-name "' + $LanName + '"' }
        if ($LanInterface) { $apkArgumentLine += ' --lan-interface "' + $LanInterface + '"' }
        $apkServerProcess = Start-Process -FilePath $apkExecutable -ArgumentList $apkArgumentLine -WorkingDirectory ([IO.Path]::GetDirectoryName($apkExecutable)) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $apkLogPath 'server-output.log') -RedirectStandardError (Join-Path $apkLogPath 'server-error.log')
        @{ ProcessId = $apkServerProcess.Id; ExecutablePath = $apkExecutable; StartedAtUtc = $apkServerProcess.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $apkProcessRecord -Encoding UTF8
        Write-ApkStatus ('Server launched in the background. PID=' + $apkServerProcess.Id)
        $apkServerProcess.WaitForExit()
        $apkServerProcess.Refresh()
        Write-ApkStatus ('Server stopped. Exit code=' + $apkServerProcess.ExitCode + '. Retrying in 10 seconds.')
        if (Test-Path -LiteralPath $apkProcessRecord) { Remove-Item -LiteralPath $apkProcessRecord }
    } catch {
        Write-ApkStatus ('Startup failed: ' + $_.Exception.GetType().Name + '. Retrying in 10 seconds.')
    }
    Start-Sleep -Seconds 10
}
