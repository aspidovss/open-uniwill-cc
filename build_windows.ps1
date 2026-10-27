<#
.SYNOPSIS
  Builds the Windows version of UWCC Control Center.

.DESCRIPTION
  1. creates a virtual environment (.venv-win) and installs windows\requirements.txt;
  2. copies the factory fan tables (UserFanTables) from the original Control Center package, if found;
  3. runs PyInstaller (windows\uwcc.spec) -> dist\ControlCenter\ with
       uwccd.exe          service (runs as SYSTEM, talks to the EC through UWACPIDriver)
       ControlCenter.exe  tray application / GUI (hidden in the tray, starts with Windows)
       uwccctl.exe        console tool
  4. adds the OEM ACPI driver (UWACPIDriver.inf/.sys/.cat), install.ps1 / uninstall.ps1 and the README;
  5. packs dist\open-uniwill-cc-windows-<ver>-portable.zip;
  6. compiles dist\open-uniwill-cc-windows-<ver>-setup.exe when Inno Setup 6 (ISCC.exe) is installed.

  Two editions (-Edition both, the default):
    non-free  open-uniwill-cc-windows-<ver>-setup.exe / -portable.zip            OEM driver + WMI
    free      open-uniwill-cc-windows-<ver>-free-setup.exe / -free-portable.zip  WMI only: no OEM driver and no factory
              fan tables (proprietary/), distributed completely freely; the user can put the OEM driver into
              C:\ProgramData\UWCC\driver and install it from EC Manager.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File build_windows.ps1
  powershell -ExecutionPolicy Bypass -File build_windows.ps1 -CC "D:\ControlCenter_5.52.49.6_MBB" -NoInstaller
  powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Edition free
#>
[CmdletBinding()]
param(
    [string]$Python = "",          # python.exe to use (default: py -3, then python)
    [string]$CC = "",              # folder of the original Control Center package (UserFanTables, setup exe)
    [string]$Driver = "",          # folder with UWACPIDriver.inf/.sys/.cat
    [switch]$NoInstaller,          # skip Inno Setup even if it is installed
    [ValidateSet("both", "full", "free")]
    [string]$Edition = "both",     # full = OEM driver + WMI (non-free), free = WMI only (no proprietary files)
    [switch]$Public,               # same as -Edition free
    [switch]$Clean                 # remove .venv-win, build and dist first
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "XX  $m" -ForegroundColor Red; exit 1 }

if ($Public) { $Edition = "free" }
$BuildFull = $Edition -ne "free"
$BuildFree = $Edition -ne "full"

$Version = (Select-String -Path "uwccd\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$editions = @()
if ($BuildFull) { $editions += "non-free" }
if ($BuildFree) { $editions += "free" }
Say "UWCC Control Center $Version for Windows ($($editions -join ' + '))"

if ($Clean) {
    # programs started from dist\ (a test run of uwccd.exe / ControlCenter.exe, setup.exe) lock the folder
    Get-Process uwccd, ControlCenter, uwccctl -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$Root\dist\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    foreach ($d in ".venv-win", "build", "dist") {
        if (-not (Test-Path $d)) { continue }
        try { Remove-Item -Recurse -Force $d -ErrorAction Stop }
        catch { Die "Cannot remove $d - a file in it is in use (an Explorer window, a running setup.exe or program from dist\). Close it and run again." }
    }
}

# ---------------------------------------------------------------- Python
function Find-Python {
    if ($Python) { return @($Python) }
    foreach ($v in "-3.12", "-3.13", "-3.11", "-3") {
        try { & py $v -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { return @("py", $v) } } catch {}
    }
    foreach ($c in "python", "python3") {
        $p = Get-Command $c -ErrorAction SilentlyContinue
        if ($p -and $p.Source -notlike "*WindowsApps*") { return @($p.Source) }
    }
    return $null
}
$py = Find-Python
if (-not $py) { Die "Python 3.9+ (64-bit) not found. Install it from https://www.python.org/downloads/windows/ and re-run." }
$pyExe = $py[0]; $pyArgs = @(); if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }
$info = & $pyExe @pyArgs -c "import sys,struct;print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P')*8))"
Say "Python $info ($($py -join ' '))"
$ver, $bits = $info.Split(" ")
if ([version]$ver -lt [version]"3.9") { Die "Python 3.9 or newer is required" }
if ($bits -ne "64") { Die "64-bit Python is required (the ACPI driver and the service are x64)" }

$venv = Join-Path $Root ".venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Say "Creating virtual environment .venv-win"
    & $pyExe @pyArgs -m venv $venv
    if ($LASTEXITCODE) { Die "venv failed" }
}
$vpy = "$venv\Scripts\python.exe"
Say "Installing build dependencies"
& $vpy -m pip install --disable-pip-version-check -q --upgrade pip
& $vpy -m pip install --disable-pip-version-check -q -r windows\requirements.txt
if ($LASTEXITCODE) { Die "pip install failed" }

# ---------------------------------------------------------------- original Control Center package
$ccDirs = @()
if ($CC) { $ccDirs += $CC }
$ccDirs += "$Root\proprietary"
$ccDirs += Get-ChildItem -Path (Split-Path $Root -Parent), $Root -Directory -Filter "ControlCenter_*" -ErrorAction SilentlyContinue | ForEach-Object FullName
$ccDir = $ccDirs | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($ccDir) { Say "Original Control Center package: $ccDir" } else { Warn "ControlCenter_* package not found next to the project (use -CC)" }

$dataDir = Join-Path $Root "uwccd\data"
$createdData = $false
if (-not $BuildFull) {
    Say "Free build: factory fan tables are not bundled (they are read from the EC)"
} elseif ($ccDir -and (Test-Path "$ccDir\UserFanTables")) {
    if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory $dataDir | Out-Null; $createdData = $true }
    Say "Factory fan tables: $ccDir\UserFanTables"
    Copy-Item -Recurse -Force "$ccDir\UserFanTables" "$dataDir\"
} elseif (-not (Test-Path "$dataDir\UserFanTables")) {
    Warn "UserFanTables not found - fan tables will be read from the EC"
}

# ---------------------------------------------------------------- build stamp
# shown as "1.4.2 - build 2026-10-23 - a1b2c3d" in the window, the log and uwccctl version
$commit = ""
try { $commit = "$(& git rev-parse --short HEAD 2>$null)".Trim() } catch { $commit = "" }
$buildDate = Get-Date -Format "yyyy-MM-dd"
$commitPy = if ($commit) { "`"$commit`"" } else { "None" }
Set-Content -Path "uwccd\_build.py" -Encoding ASCII -Value "BUILD = {`"date`": `"$buildDate`", `"commit`": $commitPy}"
Say "Build $Version / $buildDate / $(if ($commit) { $commit } else { 'no git' })"

# ---------------------------------------------------------------- PyInstaller
Say "PyInstaller"
& $vpy -m PyInstaller --noconfirm --clean --log-level WARN --distpath dist --workpath build windows\uwcc.spec
$rc = $LASTEXITCODE
if ($createdData) { Remove-Item -Recurse -Force $dataDir }
Remove-Item -Force "uwccd\_build.py" -ErrorAction SilentlyContinue
if ($rc) { Die "PyInstaller failed" }
$out = Join-Path $Root "dist\ControlCenter"
foreach ($e in "uwccd.exe", "ControlCenter.exe", "uwccctl.exe") {
    if (-not (Test-Path "$out\$e")) { Die "$e was not built" }
}

# ---------------------------------------------------------------- OEM ACPI driver
function Find-Driver {
    $cands = @()
    if ($Driver) { $cands += $Driver }
    $cands += "$Root\proprietary\driver", "$Root\windows\driver"
    if ($ccDir) { $cands += "$ccDir\UWACPIDriver", "$ccDir\driver", $ccDir }
    foreach ($c in $cands) {
        if (-not (Test-Path $c)) { continue }
        $inf = Get-ChildItem -Path $c -Recurse -Filter "UWACPIDriver.inf" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($inf) { return $inf.DirectoryName }
    }
    # last resort: unpack it from the original setup with innoextract (https://constexpr.org/innoextract/)
    $setup = if ($ccDir) { Get-ChildItem -Path $ccDir -Filter "ControlCenter*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 }
    $ie = Get-Command innoextract -ErrorAction SilentlyContinue
    if ($setup -and $ie) {
        $tmp = Join-Path $Root "build\cc-extract"
        if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
        Say "Extracting UWACPIDriver from $($setup.Name)"
        & $ie.Source -s -d $tmp -I "ZipFiles/UWACPIDriver.zip" $setup.FullName | Out-Null
        $zip = Get-ChildItem -Path $tmp -Recurse -Filter "UWACPIDriver.zip" | Select-Object -First 1
        if ($zip) {
            Expand-Archive -Force $zip.FullName "$tmp\drv"
            $inf = Get-ChildItem -Path "$tmp\drv" -Recurse -Filter "UWACPIDriver.inf" | Select-Object -First 1
            if ($inf) { return $inf.DirectoryName }
        }
    }
    return $null
}
$drv = if ($BuildFull) { Find-Driver } else { $null }
if (-not $BuildFull) {
    Say "Free build: the OEM driver is not bundled (the user can put it into C:\ProgramData\UWCC\driver)"
} elseif ($drv) {
    Say "ACPI driver: $drv"
    New-Item -ItemType Directory -Force "$out\driver" | Out-Null
    Copy-Item -Force "$drv\UWACPIDriver.inf", "$drv\UWACPIDriver.sys" "$out\driver\"
    Get-ChildItem $drv -Filter "*.cat" | Copy-Item -Destination "$out\driver\" -Force
    if (Test-Path "$Root\proprietary\LICENSE") { Copy-Item -Force "$Root\proprietary\LICENSE" "$out\driver\LICENSE.txt" }
} else {
    Warn "UWACPIDriver not found - the installer will rely on the driver installed by the original Control Center"
}

# ---------------------------------------------------------------- extras, zip, installer
Copy-Item -Force windows\install.ps1, windows\uninstall.ps1 $out
Copy-Item -Force README.windows.md "$out\README.md"
Copy-Item -Force windows\icon.ico $out
foreach ($f in "LICENSE", "NOTICE.md", "THIRD_PARTY_LICENSES.txt") { if (Test-Path $f) { Copy-Item -Force $f $out } }
Set-Content -Path "$out\VERSION" -Value $Version -Encoding ASCII
Set-Content -Path "$out\EDITION" -Value "full" -Encoding ASCII

# ---------------------------------------------------------------- free edition: the same programs without proprietary files
$freeOut = Join-Path $Root "dist\ControlCenter-free"
if ($BuildFree) {
    Say "Free edition: $freeOut"
    if (Test-Path $freeOut) { Remove-Item -Recurse -Force $freeOut }
    Copy-Item -Recurse $out $freeOut
    foreach ($p in "driver", "_internal\uwccd\data", "uwccd\data") {
        if (Test-Path "$freeOut\$p") { Remove-Item -Recurse -Force "$freeOut\$p" }
    }
    Set-Content -Path "$freeOut\EDITION" -Value "free" -Encoding ASCII
    Copy-Item -Force windows\driver-folder-README.txt "$freeOut\OEM-DRIVER-README.txt"
    $left = Get-ChildItem -Path $freeOut -Recurse -Include "UWACPIDriver*" -ErrorAction SilentlyContinue
    if ($left) { Die "Free edition still contains proprietary files: $($left.FullName -join ', ')" }
}

function Pack($src, $name) {
    $zip = Join-Path $Root "dist\$name"
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Say "Packing $name"
    Compress-Archive -Path $src -DestinationPath $zip
}
if ($BuildFull) { Pack $out "open-uniwill-cc-windows-$Version-portable.zip" }
if ($BuildFree) { Pack $freeOut "open-uniwill-cc-windows-$Version-free-portable.zip" }

if (-not $NoInstaller) {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue | ForEach-Object Source
    if (-not $iscc) {
        $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if ($iscc) {
        Say "Inno Setup: $iscc"
        if ($BuildFull) {
            & $iscc /Q "/DAppVersion=$Version" "/DSrcDir=$out" "/DOutDir=$Root\dist" windows\ControlCenter.iss
            if ($LASTEXITCODE) { Die "ISCC failed (non-free)" }
        }
        if ($BuildFree) {
            & $iscc /Q "/DAppVersion=$Version" "/DSrcDir=$freeOut" "/DOutDir=$Root\dist" "/DFree" windows\ControlCenter.iss
            if ($LASTEXITCODE) { Die "ISCC failed (free)" }
        }
    } else {
        Warn "Inno Setup 6 not found - setup.exe skipped (winget install JRSoftware.InnoSetup), the portable zip has install.ps1"
    }
}

Say "Done:"
Get-ChildItem "$Root\dist" -File | ForEach-Object { Write-Host ("    {0}  ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB)) }
if ($BuildFull) { Write-Host "    $out\  (non-free: uwccd.exe, ControlCenter.exe, uwccctl.exe, OEM driver)" }
if ($BuildFree) { Write-Host "    $freeOut\  (free: no OEM driver, no factory fan tables)" }
