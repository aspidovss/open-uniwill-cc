<#
.SYNOPSIS
  Removes UWCC Control Center installed with install.ps1.

  powershell -ExecutionPolicy Bypass -File uninstall.ps1 [-InstallDir ...] [-RemoveData] [-RemoveDriver]

  The EC gets fan control back, the original GCUService (if present) is re-enabled.
  -RemoveData   also delete %ProgramData%\UWCC (settings, profiles, logs)
  -RemoveDriver also remove UWACPIDriver (do not use if the original Control Center is still installed)
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:ProgramFiles\UWCC Control Center",
    [switch]$RemoveData,
    [switch]$RemoveDriver
)
$ErrorActionPreference = "Continue"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $a = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-InstallDir", "`"$InstallDir`"")
    if ($RemoveData) { $a += "-RemoveData" }
    if ($RemoveDriver) { $a += "-RemoveDriver" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $a
    exit
}
function Say($m) { Write-Host "==> $m" -ForegroundColor Cyan }

Say "Closing the tray application"
Get-Process ControlCenter -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$InstallDir*" } | Stop-Process -Force

if (Get-Service uwccd -ErrorAction SilentlyContinue) {
    Say "Stopping the service"
    Stop-Service uwccd -Force
    Start-Sleep 1
}
if (Test-Path "$InstallDir\uwccctl.exe") {
    Say "Giving fan control back to the EC"
    & "$InstallDir\uwccctl.exe" release
}
if (Get-Service uwccd -ErrorAction SilentlyContinue) {
    & sc.exe delete uwccd | Out-Null
}

Remove-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "UWCC Control Center" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name "UWCC Control Center" -ErrorAction SilentlyContinue
Remove-Item "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\UWCC Control Center.lnk" -ErrorAction SilentlyContinue
$mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
$np = ($mp -split ";" | Where-Object { $_ -and $_.TrimEnd('\') -ne $InstallDir.TrimEnd('\') }) -join ";"
if ($np -ne $mp) { [Environment]::SetEnvironmentVariable("Path", $np, "Machine") }

if ($RemoveDriver -and (Get-Service UWACPIDriver -ErrorAction SilentlyContinue)) {
    Say "Removing UWACPIDriver"
    $pub = (& pnputil.exe /enum-drivers) -join "`n" -split "`n`n" | Where-Object { $_ -match "uwacpidriver.inf" } |
        ForEach-Object { if ($_ -match "(oem\d+\.inf)") { $Matches[1] } }
    foreach ($p in $pub) { & pnputil.exe /delete-driver $p /uninstall /force }
}

foreach ($name in "GCUService", "GCUBridge") {
    if (Get-Service $name -ErrorAction SilentlyContinue) {
        Say "Re-enabling the original $name"
        Set-Service $name -StartupType Automatic
        Start-Service $name -ErrorAction SilentlyContinue
    }
}

if ($RemoveData -and (Test-Path "$env:ProgramData\UWCC")) {
    Say "Removing $env:ProgramData\UWCC"
    Remove-Item -Recurse -Force "$env:ProgramData\UWCC"
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path $InstallDir) {
    Say "Removing $InstallDir"
    if ($here.TrimEnd('\') -eq $InstallDir.TrimEnd('\')) {
        # this script is inside the folder: delete it after we exit
        Start-Process cmd.exe -WindowStyle Hidden -ArgumentList "/c timeout /t 2 >nul & rmdir /s /q `"$InstallDir`""
    } else {
        Remove-Item -Recurse -Force $InstallDir
    }
}
Say "Uninstalled."
