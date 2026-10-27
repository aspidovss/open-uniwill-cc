# Getting the OEM driver

**English** · [Русский](OEM-driver.ru.md)

The manufacturer's ACPI driver `UWACPIDriver` (files `UWACPIDriver.inf`, `UWACPIDriver.sys`, `uwacpidriver.cat`)
gives the program the full speed and two firmware methods WMI cannot reach (`PWUP`, `SMRW`) — see
[WMI-vs-Driver.md](WMI-vs-Driver.md).

- The **non-free** build already contains it.
- The **free** build does not contain it and is distributed completely freely; it works through WMI until you add the
  driver.

The driver is **not MIT**: use it only if you have the right to (for example, your laptop shipped with the
manufacturer's Control Center). By installing it you confirm that.

## 1. From this laptop — one button

If the manufacturer's Control Center is or was installed, Windows keeps the driver in its driver store.

*EC Manager → Get the driver from this system* copies the three files into `C:\ProgramData\UWCC\driver`
(command line: `uwccctl ec fetch-driver`, as administrator). Then *Install the OEM driver*.

## 2. From the repository

[`proprietary/driver`](https://github.com/aspidovss/open-uniwill-cc/tree/main/proprietary/driver) — version
17.53.43.609 from Control Center 5.52.49.6, unmodified ([licence](https://github.com/aspidovss/open-uniwill-cc/blob/main/proprietary/LICENSE)).
Download the three files into `C:\ProgramData\UWCC\driver`, then *EC Manager → Install the OEM driver*.

## 3. By hand

PowerShell as administrator. Paste each command as **one line** — some consoles reorder the lines of a multi-line paste.

Is the driver in the driver store?

```powershell
pnputil /enum-drivers | Select-String -Context 1,4 uwacpidriver
```

Copy it from there:

```powershell
$src = Get-ChildItem C:\Windows\System32\DriverStore\FileRepository -Directory -Filter "uwacpidriver.inf_amd64_*" | Sort-Object LastWriteTime | Select-Object -Last 1; if (-not $src) { throw "uwacpidriver not found in the driver store" }; New-Item -ItemType Directory -Force C:\ProgramData\UWCC\driver | Out-Null; Copy-Item "$($src.FullName)\uwacpidriver.*" C:\ProgramData\UWCC\driver\; Get-ChildItem C:\ProgramData\UWCC\driver
```

Or take it out of the manufacturer's Control Center installer (`ControlCenter_*.exe` from the laptop's support page)
with [innoextract](https://constexpr.org/innoextract/):

```powershell
innoextract -d cc -I ZipFiles/UWACPIDriver.zip .\ControlCenter_5.52.49.6_MBB.exe
```

```powershell
$zip = Get-ChildItem cc -Recurse -Filter UWACPIDriver.zip | Select-Object -First 1; if (-not $zip) { throw "UWACPIDriver.zip not found" }; Expand-Archive $zip.FullName cc\drv -Force; New-Item -ItemType Directory -Force C:\ProgramData\UWCC\driver | Out-Null; Get-ChildItem cc\drv -Recurse -Include *.inf,*.sys,*.cat | Copy-Item -Destination C:\ProgramData\UWCC\driver\; Get-ChildItem C:\ProgramData\UWCC\driver
```

## Check before installing

Before `pnputil` installs the driver, the program checks the package — in EC Manager, the installer, `install.ps1`
and the self-check; by hand: `uwccctl ec check-driver` or `uwccctl driver-verify FOLDER` (no service needed).

| Check | Problem → result |
|---|---|
| the three files are there, sizes are plausible | missing → **not installed** |
| the INF is the `UWACPIDriver` for `ACPI\INOU0000`, amd64 | another device → **not installed** |
| the signatures of the catalog and the driver are valid (Windows) | not valid / not checked → needs *I still want to use this driver and understand the risk* |
| SHA-256 is a known version (17.53.43.609) | unknown version → warning, needs the same confirmation |

Command line: `uwccctl ec install-driver --accept-risks` is the same confirmation. Exit codes of `driver-verify`:
0 ok, 10 unknown version, 11 signature problem, 12 unusable.
