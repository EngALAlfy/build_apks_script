[CmdletBinding()]
param(
    [ValidateSet('Logon','Boot')][string]$StartupMode = 'Logon',
    [string]$ExecutablePath,
    [string]$DataDirectory = (Join-Path $env:LOCALAPPDATA 'APKBuilderServer'),
    [string]$BindAddress = '0.0.0.0',
    [string]$LanName = 'apk-builder',
    [string]$LanInterface = '',
    [switch]$NoMdns,
    [ValidateRange(1,65535)][int]$Port = 8080,
    [System.Management.Automation.PSCredential]$Credential,
    [switch]$StartNow
)
$ErrorActionPreference = 'Stop'
$apkTaskName = 'APK Builder Central Server'
$apkMarker = 'APKBuilder managed startup v1'
$apkRunAsUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if (-not $ExecutablePath) {
    $ExecutablePath = Join-Path $PSScriptRoot 'APK Build Server.exe'
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        $ExecutablePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\APK Build Server\APK Build Server.exe'
    }
}
$apkExecutable = (Resolve-Path -LiteralPath $ExecutablePath).ProviderPath
$apkRunner = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'run-server.ps1')).ProviderPath
$apkDataPath = [IO.Path]::GetFullPath($DataDirectory)
foreach ($apkArgument in @($apkExecutable,$apkRunner,$apkDataPath,$BindAddress,$LanName,$LanInterface)) {
    if ($apkArgument.Contains('"') -or $apkArgument.Contains("`r") -or $apkArgument.Contains("`n")) {
        throw 'Startup arguments cannot contain quote or newline characters.'
    }
}
$apkExistingTask = Get-ScheduledTask -TaskName $apkTaskName -ErrorAction SilentlyContinue
if ($apkExistingTask -and -not $apkExistingTask.Description.StartsWith($apkMarker)) {
    throw 'A task with this name already exists and is not managed by this installer.'
}
$apkActionArguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "' + $apkRunner + '" -ExecutablePath "' + $apkExecutable + '" -DataDirectory "' + $apkDataPath.TrimEnd('\') + '" -BindAddress "' + $BindAddress + '" -Port ' + $Port
$apkActionArguments += ' -LanName "' + $LanName + '"'
if ($LanInterface) { $apkActionArguments += ' -LanInterface "' + $LanInterface + '"' }
if ($NoMdns) { $apkActionArguments += ' -NoMdns' }
$apkPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $apkPowerShell -PathType Leaf)) { throw 'Windows PowerShell was not found at its standard system location.' }
$apkAction = New-ScheduledTaskAction -Execute $apkPowerShell -Argument $apkActionArguments -WorkingDirectory ([IO.Path]::GetDirectoryName($apkExecutable))
$apkSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
if ($StartupMode -eq 'Boot') {
    if (-not $Credential) {
        $Credential = Get-Credential -UserName $apkRunAsUser -Message 'Windows needs your existing Windows account password to run the build server before sign-in. This is separate from dashboard accounts. The password is not written to a script or log.'
    }
    if ($null -eq $Credential) { throw 'Startup installation cancelled. No changes were made.' }
    if ($Credential.UserName -ne $apkRunAsUser) {
        throw 'Use the current Windows account so the server retains its existing profile and Git credentials.'
    }
    $apkTrigger = New-ScheduledTaskTrigger -AtStartup
    $apkTrigger.Delay = 'PT30S'
    $apkPrincipal = New-ScheduledTaskPrincipal -UserId $apkRunAsUser -LogonType Password -RunLevel Limited
} else {
    $apkTrigger = New-ScheduledTaskTrigger -AtLogOn -User $apkRunAsUser
    $apkTrigger.Delay = 'PT15S'
    $apkPrincipal = New-ScheduledTaskPrincipal -UserId $apkRunAsUser -LogonType Interactive -RunLevel Limited
}
$apkTask = New-ScheduledTask -Action $apkAction -Trigger $apkTrigger -Principal $apkPrincipal -Settings $apkSettings -Description ($apkMarker + '; mode=' + $StartupMode + '; no browser; current Windows account.')
if ($StartupMode -eq 'Boot') {
    $apkPlainPassword = $Credential.GetNetworkCredential().Password
    try {
        Register-ScheduledTask -TaskName $apkTaskName -InputObject $apkTask -User $apkRunAsUser -Password $apkPlainPassword -Force | Out-Null
    } finally {
        $apkPlainPassword = $null
        $Credential = $null
    }
} else {
    Register-ScheduledTask -TaskName $apkTaskName -InputObject $apkTask -Force | Out-Null
}
if ($StartNow) { Start-ScheduledTask -TaskName $apkTaskName }
$apkInstalled = Get-ScheduledTask -TaskName $apkTaskName
[pscustomobject]@{ TaskName = $apkInstalled.TaskName; StartupMode = $StartupMode; RunAs = $apkInstalled.Principal.UserId; State = $apkInstalled.State; Browser = 'Disabled'; DataDirectory = $apkDataPath } | Format-List
