<#
.SYNOPSIS
  Installs OUCC (Open Uniwill Control Center) from the portable folder (alternative to setup.exe).

  powershell -ExecutionPolicy Bypass -File install.ps1 [-InstallDir "C:\Program Files\OUCC"] [-KeepOEM]

  * replaces an earlier installation (setup.exe or install.ps1, also the old name "UWCC Control Center" from before
    1.8.2.6) in another folder; the settings in C:\ProgramData\UWCC are kept;
  * copies the program to -InstallDir and registers it in Settings -> Apps (uninstall runs uninstall.ps1);
  * stops and disables the original GCUService (two programs must not drive the same EC), unless -KeepOEM;
  * installs the OEM ACPI driver (driver\UWACPIDriver.inf) when it is not present yet;
  * registers and starts the "uwccd" service (LocalSystem, automatic start, restart on failure);
  * adds ControlCenter.exe to autostart for all users (it starts hidden in the tray) and a Start menu shortcut;
  * starts the tray application for the current user.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:ProgramFiles\OUCC",
    [switch]$KeepOEM
)
$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $a = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"", "-InstallDir", "`"$InstallDir`"")
    if ($KeepOEM) { $a += "-KeepOEM" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $a
    exit
}

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }

$Src = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$Src\uwccd.exe")) { Write-Host "uwccd.exe not found next to install.ps1" -ForegroundColor Red; exit 1 }
$Svc = "uwccd"
$RunKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
$RunName = "OUCC"
$OldName = "UWCC Control Center"
$AppsKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
$InnoKey = "$AppsKey\{6B0E1F43-5C1D-4F0B-9E43-55A1C0C7D7A1}_is1"
$PortableKey = "$AppsKey\OUCC-portable"
function Same($a, $b) { $a -and $b -and ($a.TrimEnd('\') -ieq $b.TrimEnd('\')) }
function Ours($d) { $d -and (Test-Path "$d\uwccd.exe") -and (Test-Path "$d\ControlCenter.exe") }

# --- stop a running copy
Get-Process ControlCenter -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*UWCC*" -or $_.Path -like "$InstallDir*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
if (Get-Service $Svc -ErrorAction SilentlyContinue) {
    Say "Stopping the existing service"
    Stop-Service $Svc -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
}

# --- an earlier installation in another folder (1.8.2.6): files, PATH, autostart, shortcuts, Apps entry
$old = @()
foreach ($k in $InnoKey, $PortableKey) {
    $d = (Get-ItemProperty $k -ErrorAction SilentlyContinue).InstallLocation
    if ($d) { $old += $d }
}
$img = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$Svc" -ErrorAction SilentlyContinue).ImagePath
if ($img -and $img -match '"?([^"]+\.exe)') { $old += (Split-Path $Matches[1]) }
$old += "$env:ProgramFiles\$OldName"
$old = $old | Where-Object { Ours $_ } | ForEach-Object { $_.TrimEnd('\') } | Sort-Object -Unique
$mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
foreach ($d in $old) {
    $mp = ($mp -split ";" | Where-Object { $_ -and -not (Same $_ $d) }) -join ";"
    if (-not (Same $d $InstallDir) -and -not (Same $d $Src)) {
        Say "Removing the earlier installation in $d (settings are kept)"
        Get-Process ControlCenter -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$d*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
        if (Same (Get-ItemProperty $InnoKey -ErrorAction SilentlyContinue).InstallLocation $d) { Remove-Item $InnoKey -Recurse -Force }
    }
}
[Environment]::SetEnvironmentVariable("Path", $mp, "Machine")
Remove-ItemProperty -Path $RunKey -Name $OldName -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name $OldName -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name $OldName -ErrorAction SilentlyContinue
Remove-Item "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\$OldName.lnk", "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\$OldName" -Recurse -Force -ErrorAction SilentlyContinue

# --- original Control Center
if (-not $KeepOEM) {
    foreach ($name in "GCUService", "GCUBridge") {
        $s = Get-Service $name -ErrorAction SilentlyContinue
        if ($s) {
            Say "Disabling the original $name"
            Stop-Service $name -Force -ErrorAction SilentlyContinue
            Set-Service $name -StartupType Disabled
        }
    }
    Get-Process -Name "ControlCenter*", "GCUBridge*" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -notlike "*UWCC*" -and $_.Path -notlike "$InstallDir*" -and $_.Path -notlike "$Src*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

# --- files
if ((Resolve-Path $Src).Path.TrimEnd('\') -ne $InstallDir.TrimEnd('\')) {
    Say "Copying to $InstallDir"
    New-Item -ItemType Directory -Force $InstallDir | Out-Null
    Copy-Item -Recurse -Force "$Src\*" $InstallDir
}

# --- ACPI driver (the free edition has none: the user may put it into C:\ProgramData\UWCC\driver)
$userDrv = Join-Path $env:ProgramData "UWCC\driver"
if (-not (Test-Path $userDrv)) { New-Item -ItemType Directory -Force $userDrv | Out-Null }
if ((Test-Path "$Src\OEM-DRIVER-README.txt") -and -not (Test-Path "$userDrv\README.txt")) {
    Copy-Item -Force "$Src\OEM-DRIVER-README.txt" "$userDrv\README.txt"
}
$inf = @("$InstallDir\driver\UWACPIDriver.inf", "$userDrv\UWACPIDriver.inf") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (Get-Service UWACPIDriver -ErrorAction SilentlyContinue) {
    Say "ACPI driver already installed"
} elseif ($inf) {
    # minimal check before pnputil: files, INF for ACPI\INOU0000, signature, known SHA-256
    & "$InstallDir\uwccctl.exe" driver-verify (Split-Path $inf)
    $rc = $LASTEXITCODE
    $go = $rc -eq 0
    if ($rc -eq 10 -or $rc -eq 11) {
        Warn "The driver check found problems (see above)."
        $go = (Read-Host "I still want to use this driver and understand the risk - install it? (yes/no)") -eq "yes"
    } elseif ($rc -ne 0) {
        Warn "The driver package cannot be used - not installed, the program uses WMI"
    }
    if ($go) {
        Say "Installing the ACPI driver (ACPI\INOU0000) from $(Split-Path $inf)"
        & pnputil.exe /add-driver $inf /install
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 3010) { Warn "pnputil exit code $LASTEXITCODE" }
    }
} elseif ((Test-Path "$Src\EDITION") -and ((Get-Content "$Src\EDITION") -eq "free")) {
    Warn "Free build: no OEM driver inside. Recommended: put UWACPIDriver.inf/.sys/.cat into $userDrv and install it in EC Manager (the program uses WMI until then)"
} else {
    Warn "UWACPIDriver is not installed and driver\ is missing - install the original Control Center driver first"
}

# --- service
$exe = "$InstallDir\uwccd.exe"
if (Get-Service $Svc -ErrorAction SilentlyContinue) {
    & sc.exe config $Svc binPath= "`"$exe`"" start= auto DisplayName= "OUCC service" | Out-Null
} else {
    Say "Registering the service"
    & sc.exe create $Svc binPath= "`"$exe`"" start= auto DisplayName= "OUCC service" | Out-Null
}
& sc.exe description $Svc "Open Uniwill Control Center: performance modes, fans, keyboard lighting, battery and liquid cooler for Uniwill/Tongfang laptops." | Out-Null
& sc.exe failure $Svc reset= 86400 actions= restart/5000/restart/10000/restart/30000 | Out-Null
Say "Starting the service"
Start-Service $Svc

# --- autostart + shortcuts
Set-ItemProperty -Path $RunKey -Name $RunName -Value "`"$InstallDir\ControlCenter.exe`""
$lnkDir = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
$sh = New-Object -ComObject WScript.Shell
$l = $sh.CreateShortcut("$lnkDir\OUCC.lnk")
$l.TargetPath = "$InstallDir\ControlCenter.exe"; $l.Arguments = "--open"; $l.WorkingDirectory = $InstallDir
$l.IconLocation = "$InstallDir\ControlCenter.exe,0"; $l.Save()

# PATH for uwccctl
$mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
if (($mp -split ";") -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable("Path", "$mp;$InstallDir", "Machine")
}

# --- Settings -> Apps: an entry whose "Uninstall" runs uninstall.ps1 from the installed folder
$ver = if (Test-Path "$InstallDir\VERSION") { (Get-Content "$InstallDir\VERSION" -TotalCount 1).Trim() } else { "" }
New-Item -Path $PortableKey -Force | Out-Null
$u = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`" -InstallDir `"$InstallDir`""
foreach ($kv in @{ DisplayName = "OUCC (Open Uniwill Control Center)"; DisplayVersion = $ver; Publisher = "open-uniwill-cc";
                   InstallLocation = $InstallDir; DisplayIcon = "$InstallDir\ControlCenter.exe"; UninstallString = $u;
                   URLInfoAbout = "https://github.com/aspidovss/open-uniwill-cc" }.GetEnumerator()) {
    Set-ItemProperty -Path $PortableKey -Name $kv.Key -Value $kv.Value
}
Set-ItemProperty -Path $PortableKey -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -Path $PortableKey -Name NoRepair -Value 1 -Type DWord

# --- tray for the current user, not elevated (explorer starts it with the user's normal token)
Start-Process explorer.exe "`"$InstallDir\ControlCenter.exe`""

Start-Sleep 3
& "$InstallDir\uwccctl.exe" status
Say "Installed. The icon is in the notification area; open the window from the tray or the Start menu."
