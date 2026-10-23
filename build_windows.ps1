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

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File build_windows.ps1
  powershell -ExecutionPolicy Bypass -File build_windows.ps1 -CC "D:\ControlCenter_5.52.49.6_MBB" -NoInstaller
#>
[CmdletBinding()]
param(
    [string]$Python = "",          # python.exe to use (default: py -3, then python)
    [string]$CC = "",              # folder of the original Control Center package (UserFanTables, setup exe)
    [string]$Driver = "",          # folder with UWACPIDriver.inf/.sys/.cat
    [switch]$NoInstaller,          # skip Inno Setup even if it is installed
    [switch]$Public,               # do not bundle the OEM driver and factory fan tables (proprietary/)
    [switch]$Clean                 # remove .venv-win, build and dist first
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "XX  $m" -ForegroundColor Red; exit 1 }

$Version = (Select-String -Path "uwccd\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Say "UWCC Control Center $Version for Windows"

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
if ($Public) {
    Say "Public build: factory fan tables are not bundled (they are read from the EC)"
} elseif ($ccDir -and (Test-Path "$ccDir\UserFanTables")) {
    if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory $dataDir | Out-Null; $createdData = $true }
    Say "Factory fan tables: $ccDir\UserFanTables"
    Copy-Item -Recurse -Force "$ccDir\UserFanTables" "$dataDir\"
} elseif (-not (Test-Path "$dataDir\UserFanTables")) {
    Warn "UserFanTables not found - fan tables will be read from the EC"
}

# ---------------------------------------------------------------- PyInstaller
Say "PyInstaller"
& $vpy -m PyInstaller --noconfirm --clean --log-level WARN --distpath dist --workpath build windows\uwcc.spec
$rc = $LASTEXITCODE
if ($createdData) { Remove-Item -Recurse -Force $dataDir }
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
$drv = if ($Public) { $null } else { Find-Driver }
if ($Public) {
    Say "Public build: the OEM driver is not bundled (install.ps1 uses the driver of the original Control Center)"
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

$zipPath = Join-Path $Root "dist\open-uniwill-cc-windows-$Version-portable.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Say "Packing $(Split-Path $zipPath -Leaf)"
Compress-Archive -Path $out -DestinationPath $zipPath

if (-not $NoInstaller) {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue | ForEach-Object Source
    if (-not $iscc) {
        $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if ($iscc) {
        Say "Inno Setup: $iscc"
        & $iscc /Q "/DAppVersion=$Version" "/DSrcDir=$out" "/DOutDir=$Root\dist" windows\ControlCenter.iss
        if ($LASTEXITCODE) { Die "ISCC failed" }
    } else {
        Warn "Inno Setup 6 not found - setup.exe skipped (winget install JRSoftware.InnoSetup), the portable zip has install.ps1"
    }
}

Say "Done:"
Get-ChildItem "$Root\dist" -File | ForEach-Object { Write-Host ("    {0}  ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB)) }
Write-Host "    $out\  (uwccd.exe, ControlCenter.exe, uwccctl.exe)"
