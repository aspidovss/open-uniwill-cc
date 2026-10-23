"""Firmware and OEM-software parts of the diagnostic report (what a study of a new laptop needs).

Read-only, like the rest of the report. The items follow what researchers of other Uniwill platforms collect
(ACPI tables, the OEM registry with the feature flags of the official program, its services and settings files):

  acpi           ACPI tables (DSDT, SSDT, ...) without MSDM / SLIC, which hold the Windows licence key
  firmware       ACPI / WMI devices of the EC interface (INOU0000, UNIW, PNP0C14), their drivers, WMI classes
  oem_registry   HKLM\\SOFTWARE\\OEM complete, plus the feature flags decoded (ItemSupport, Support, MySetting, ...)
  oem_software   services, packages, scheduled tasks and file versions of the official Control Center
  oem_files      settings, tables, profiles and logs of the official program (text files only) + a list of all files
  oem_files_full the same folders complete, programs included (large, off by default)
  power          power plans (Windows) / power profiles and CPU frequency policy (Linux)
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

EXCLUDED_ACPI = {"MSDM", "SLIC"}
TEXT_EXT = {".txt", ".log", ".json", ".ini", ".xml", ".cfg", ".config", ".reg", ".csv", ".yaml", ".yml", ".md"}
BIN_EXT = {".exe", ".dll", ".sys"}
OEM_NAMES = r"GCUBridge|GCUService|Uniwill|AISTONE|AiStone|GamingCenter|Gaming Center|ControlCenter|Control Center|Mechrevo|CCU"
LOG_DAYS = 14
TEXT_FILE_MAX = 4 << 20          # one text file
TEXT_TOTAL_MAX = 40 << 20        # all copied text files
FULL_TOTAL_MAX = 400 << 20       # oem_files_full

# Boards known to run the official Uniwill service 1.0.2.x / 1.2.x (public tester lists of other projects).
# Only a hint for whoever reads the report; support depends on the EC, not on the name.
OTHER_KNOWN_BOARDS = {
    "GM5HG0A": "Mechrevo Yilong15Pro", "GM6IR0C": "Mechrevo JiguangX", "GM6BG0X": "Mechrevo Jiaolong16K",
    "GM6PX7X": "Mechrevo Kuangshi16 Super", "GM6IX9B": "Mechrevo Yaoshi16Super", "GX6HG0U-F": "Huan 16 Air",
    "HYDROC-16": "HYDROC-16 G2", "X6AR5xxY": "XMG NEO (E25)",
    "CANGLONG Series-X6xR55xY": "Mechrevo Canglong", "CANGLONG Series-X8xR55xP-B2": "Mechrevo Canglong",
    "JIAOLONG Series-X6DR55xx-B2": "Mechrevo Jiaolong", "JIAOLONG Series-X6xR55xK": "Mechrevo Jiaolong",
    "KUANGSHI-JIGUANG Series-X6xx55xW-B2": "Mechrevo Kuangshi", "KUANGSHI-JIGUANG Series-X6xx55xx-B2": "Mechrevo Kuangshi",
    "KUANGSHI-JIGUANG Series-X6xx57TW": "Mechrevo Jiguang", "YAOSHI Series-X6AR55xY": "Mechrevo Yaoshi",
    "YAOSHI Series-XxAF55xx": "Mechrevo Yaoshi",
}
# CustomizeTarget = the middle number of the official program's version (5.<target>.x.y)
CUSTOMIZE_TARGETS = {52: "MAIBENBEN", 56: "MECHREVO", 49: "Huan / Thunderobot", 23: "HYDROC"}


def _ps(script, timeout=60):
    """PowerShell with UTF-8 output (Chinese / Cyrillic folder and product names survive)."""
    pre = "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); $ErrorActionPreference = 'SilentlyContinue'; "
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", pre + script],
                       capture_output=True, timeout=timeout, creationflags=0x08000000, check=False)
    return r.stdout.decode("utf-8", "replace").strip()


def _ps_json(script, timeout=60):
    out = _ps(script + " | ConvertTo-Json -Depth 6 -Compress", timeout)
    if not out:
        return []
    v = json.loads(out)
    return v if isinstance(v, list) else [v]


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
        return (r.stdout or r.stderr).decode("oem" if sys.platform == "win32" else "utf-8", "replace")   # console code page
    except (OSError, subprocess.SubprocessError) as e:
        return f"({e})"


# ---------------------------------------------------------------- ACPI tables
def acpi_tables():
    """-> (summary, {zip path: bytes})"""
    files, rows = {}, []
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        prov = 0x41435049                                     # 'ACPI'
        size = k32.EnumSystemFirmwareTables(prov, None, 0)
        buf = (ctypes.c_ubyte * size)()
        k32.EnumSystemFirmwareTables(prov, buf, size)
        ids = [int.from_bytes(bytes(buf[i:i + 4]), "little") for i in range(0, size, 4)]
        ids.append(int.from_bytes(b"DSDT", "little"))          # not listed (the FADT points to it)
        seen = {}
        for tid in ids:
            sig = tid.to_bytes(4, "little").decode("ascii", "replace")
            if sig in EXCLUDED_ACPI or sig in seen:
                continue
            n = k32.GetSystemFirmwareTable(prov, tid, None, 0)
            if not n:
                continue
            t = (ctypes.c_ubyte * n)()
            k32.GetSystemFirmwareTable(prov, tid, t, n)
            seen[sig] = bytes(t)
        tables = seen.items()
    else:
        tables = []
        for p in sorted(glob.glob("/sys/firmware/acpi/tables/*")):
            name = os.path.basename(p)
            if os.path.isdir(p) or name[:4] in EXCLUDED_ACPI:
                continue
            try:
                with open(p, "rb") as f:
                    tables.append((name, f.read()))
            except OSError as e:
                rows.append({"table": name, "error": str(e)})
    for name, data in tables:
        ext = "aml" if name[:4] in ("DSDT", "SSDT") else "bin"
        files[f"acpi/{name}.{ext}"] = data
        rows.append({"table": name, "size": len(data), "oem_id": data[10:16].decode("ascii", "replace").strip(),
                     "oem_table_id": data[16:24].decode("ascii", "replace").strip(),
                     "revision": data[8] if len(data) > 8 else None})
    return {"tables": rows, "excluded": sorted(EXCLUDED_ACPI)}, files


# ---------------------------------------------------------------- firmware devices
def firmware_info():
    if sys.platform == "win32":
        flt = r"$_.DeviceID -match '^ACPI\\(INOU|UNIW|PNP0C14)' -or $_.Name -match 'Uniwill|Tongfang|AISTONE|Control Center|Gaming Center'"
        out = {
            "devices": _ps_json(f"Get-CimInstance Win32_PnPEntity | Where-Object {{ {flt} }} | "
                                "Select-Object Name, DeviceID, PNPClass, Status, ConfigManagerErrorCode"),
            "drivers": _ps_json(r"Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceID -match '^ACPI\\(INOU|UNIW|PNP0C14)' "
                                r"-or $_.InfName -match 'uwacpi' -or $_.DeviceName -match 'Uniwill|ACPIDriver' } | "
                                "Select-Object DeviceName, DeviceID, DriverVersion, DriverProviderName, InfName, IsSigned, Signer"),
            "wmi_classes": _ps_json("@(foreach ($c in 'MICommonInterface','HID_EVENT20','AcpiTest_MULong','WmiMonitorBrightnessMethods') "
                                    "{ $x = Get-CimClass -Namespace root\\WMI -ClassName $c; [pscustomobject]@{ class = $c; exists = [bool]$x; "
                                    "methods = @($x.CimClassMethods | ForEach-Object Name); properties = @($x.CimClassProperties | ForEach-Object Name) } })"),
            "drivers_all": _run(["pnputil", "/enum-drivers"], timeout=60),
        }
        return out
    devs = []
    for p in sorted(glob.glob("/sys/bus/acpi/devices/*")):
        n = os.path.basename(p)
        if re.match(r"(INOU|UNIW|PNP0C14|PNP0C09)", n):
            devs.append({"device": n, "hid": _readf(os.path.join(p, "hid")), "status": _readf(os.path.join(p, "status")),
                         "path": _readf(os.path.join(p, "path"))})
    wmi = [{"guid": os.path.basename(p), "driver": os.path.basename(os.path.realpath(os.path.join(p, "driver")))
            if os.path.exists(os.path.join(p, "driver")) else None} for p in sorted(glob.glob("/sys/bus/wmi/devices/*"))]
    return {"devices": devs, "wmi_guids": wmi,
            "modules": [ln.split()[0] for ln in (_readf("/proc/modules") or "").splitlines()
                        if re.match(r"(uwcc|acpi_call|wmi|uniwill|tuxedo|clevo|nvidia_wmi)", ln)]}


def _readf(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return None


# ---------------------------------------------------------------- OEM registry (Windows)
def oem_registry():
    if sys.platform != "win32":
        return {"available": False, "reason": "Windows only"}
    import winreg
    kinds = {winreg.REG_DWORD: "DWord", winreg.REG_QWORD: "QWord", winreg.REG_SZ: "String", winreg.REG_EXPAND_SZ: "ExpandString",
             winreg.REG_MULTI_SZ: "MultiString", winreg.REG_BINARY: "Binary"}
    items = []

    def walk(root, rname, path, view=0):
        try:
            k = winreg.OpenKey(root, path, 0, winreg.KEY_READ | view)
        except OSError:
            return
        with k:
            i = 0
            while True:
                try:
                    n, v, t = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                items.append({"key": f"{rname}\\{path}", "name": n, "kind": kinds.get(t, str(t)),
                              "value": v.hex(" ") if isinstance(v, bytes) else v})
            i = 0
            subs = []
            while True:
                try:
                    subs.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
        for s in subs:
            walk(root, rname, f"{path}\\{s}", view)

    walk(winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SOFTWARE\OEM", winreg.KEY_WOW64_64KEY)
    walk(winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SOFTWARE\WOW6432Node\OEM")
    flags = {}
    for it in items:
        m = re.search(r"\\GamingCenter2(?:\\(ItemSupport|Support|SMAPCTable|BatteryProtection2|TpDetect|MySetting(?:\\[^\\]+)?))?$", it["key"])
        if m:
            flags.setdefault(m.group(1) or "GamingCenter2", {})[it["name"]] = it["value"]
    gc = flags.get("GamingCenter2", {})
    ct = gc.get("CustomizeTarget")
    return {"values": items, "feature_flags": flags,
            "official_program": {"AppVersion": gc.get("AppVersion"), "AppSubVersion": gc.get("AppSubVersion"),
                                 "CustomizeTarget": ct, "brand": CUSTOMIZE_TARGETS.get(ct) if isinstance(ct, int) else None,
                                 "ProjectID": gc.get("ProjectID"), "BridgeType": gc.get("BridgeType")}}


# ---------------------------------------------------------------- OEM software (Windows)
def _file_record(path):
    rec = {"path": path, "exists": os.path.exists(path)}
    if not rec["exists"]:
        return rec
    rec["size"] = os.path.getsize(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    rec["sha256"] = h.hexdigest()
    return rec


def _win_services():
    """OEM services from the registry (WMI's Win32_Service can take over a minute as LocalSystem)."""
    import winreg
    starts = {0: "Boot", 1: "System", 2: "Auto", 3: "Manual", 4: "Disabled"}
    out = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services") as root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, name) as k:
                    vals = {}
                    for v in ("ImagePath", "DisplayName", "Start", "ObjectName", "Type"):
                        try:
                            vals[v] = winreg.QueryValueEx(k, v)[0]
                        except OSError:
                            vals[v] = None
            except OSError:
                continue
            path, disp = str(vals["ImagePath"] or ""), str(vals["DisplayName"] or "")
            if not (re.search(OEM_NAMES + "|uwccd", name + " " + disp) or re.search(r"\\OEM\\", path, re.I)):
                continue
            if not isinstance(vals["Type"], int) or not vals["Type"] & 0x30:        # Win32 services, not drivers
                continue
            state = None
            try:
                import win32serviceutil
                state = {1: "Stopped", 2: "StartPending", 3: "StopPending", 4: "Running"}.get(
                    win32serviceutil.QueryServiceStatus(name)[1])
            except Exception:  # noqa: BLE001
                pass
            out.append({"Name": name, "DisplayName": disp, "State": state, "StartMode": starts.get(vals["Start"], vals["Start"]),
                        "StartName": vals["ObjectName"], "PathName": path})
    return out


def oem_software():
    if sys.platform != "win32":
        return {"available": False, "reason": "Windows only"}
    services = _win_services()
    exes = set()
    for s in services:
        m = re.match(r'^\s*"?([^"]+?\.exe)', s.get("PathName") or "", re.I)
        if m:
            exes.add(m.group(1))
            d = os.path.dirname(m.group(1))
            exes.update(glob.glob(os.path.join(d, "MyControlCenter", "*.exe")))
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    exes.update(glob.glob(os.path.join(pf, "OEM", "*", "*", "MyControlCenter", "GCUService.exe")))
    recs = [_file_record(e) for e in sorted(exes)]
    paths = ",".join("'" + r["path"].replace("'", "''") + "'" for r in recs if r["exists"])
    info = {}
    if paths:                                   # one PowerShell for all files: versions and signatures
        for x in _ps_json(f"@(foreach ($p in @({paths})) {{ $f = Get-Item -LiteralPath $p; $g = Get-AuthenticodeSignature -LiteralPath $p; "
                          "[pscustomobject]@{ Path = $p; FileVersion = $f.VersionInfo.FileVersion; ProductVersion = $f.VersionInfo.ProductVersion; "
                          "Signer = $g.SignerCertificate.Subject; SignatureStatus = [string]$g.Status } })"):
            info[str(x.get("Path", "")).lower()] = {k: v for k, v in x.items() if k != "Path"}
    versions = [{**r, **info.get(r["path"].lower(), {})} for r in recs]
    return {
        "services": services, "binaries": versions,
        "packages": _ps_json(f"Get-AppxPackage -AllUsers | Where-Object {{ $_.Name -match '{OEM_NAMES}' -or $_.Publisher -match 'AISTONE' }} | "
                             "Select-Object Name, @{n='Version';e={$_.Version.ToString()}}, Publisher, PackageFullName"),
        "installed": _ps_json("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*', "
                              "'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' | "
                              f"Where-Object {{ $_.DisplayName -match '{OEM_NAMES}|open-uniwill' -or $_.Publisher -match 'AISTONE|Uniwill|Mechrevo' }} | "
                              "Select-Object DisplayName, DisplayVersion, Publisher, InstallLocation"),
        "scheduled_tasks": _ps_json(f"Get-ScheduledTask | Where-Object {{ ($_.TaskName + ' ' + (($_.Actions | ForEach-Object {{ $_.Execute + ' ' + $_.Arguments }}) -join ' ')) "
                                    f"-match '{OEM_NAMES}|\\\\OEM\\\\' }} | Select-Object TaskPath, TaskName, State, Author, "
                                    "@{n='Actions';e={($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' | '}}"),
    }


# ---------------------------------------------------------------- OEM files
def _oem_roots():
    if sys.platform != "win32":
        return []
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    roots = [(os.path.join(pf, "OEM"), "ProgramFiles-OEM"), (os.path.join(pd, "OEM"), "ProgramData-OEM"),
             (os.path.join(pd, "CCU_Gallery"), "ProgramData-CCU_Gallery"), (os.path.join(pd, "ControlCenter"), "ProgramData-ControlCenter")]
    return [(r, n) for r, n in roots if os.path.isdir(r)]


def oem_files(full=False, redact=lambda t: t):
    """-> (summary, {zip path: bytes}). Text files are redacted; binaries only with full=True."""
    files, listing, total, skipped = {}, [], 0, []
    cutoff = time.time() - LOG_DAYS * 86400
    limit = FULL_TOTAL_MAX if full else TEXT_TOTAL_MAX
    for root, alias in _oem_roots():
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if not os.path.islink(os.path.join(d, x))]
            for n in names:
                p = os.path.join(d, n)
                rel = os.path.relpath(p, root).replace("\\", "/")
                ext = os.path.splitext(n)[1].lower()
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                rec = {"path": f"{alias}/{rel}", "size": st.st_size, "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))}
                if ext in BIN_EXT:
                    rec["sha256"] = _file_record(p).get("sha256")
                listing.append(rec)
                is_text = ext in TEXT_EXT
                if is_text and ext in (".txt", ".log") and st.st_mtime < cutoff:
                    continue
                if not (is_text or full):
                    continue
                if (is_text and st.st_size > TEXT_FILE_MAX) or total + st.st_size > limit:
                    skipped.append(rec["path"])
                    continue
                try:
                    with open(p, "rb") as f:
                        data = f.read()
                except OSError as e:
                    skipped.append(f"{rec['path']} ({e})")
                    continue
                if is_text:
                    data = _redact_bytes(data, redact)
                files[f"oem/{alias}/{rel}"] = data
                total += len(data)
    return {"roots": [a for _, a in _oem_roots()], "files": listing, "copied_bytes": total,
            "skipped": skipped, "full": full, "log_days": LOG_DAYS}, files


def _redact_bytes(data, redact):
    """Redact a text file keeping its encoding: UTF-16 / UTF-8 by BOM or validity, otherwise Latin-1 (GBK logs)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    else:
        try:
            data.decode("utf-8")
            enc = "utf-8"
        except UnicodeDecodeError:
            enc = "latin-1"
    try:
        return redact(data.decode(enc)).encode(enc if enc != "utf-16" else "utf-16")
    except (UnicodeError, ValueError):
        return data


# ---------------------------------------------------------------- power
def power_info():
    if sys.platform == "win32":
        return {"list": _run(["powercfg", "/list"]), "active": _run(["powercfg", "/getactivescheme"]),
                "settings": _run(["powercfg", "/qh"], timeout=60)}
    cpu0 = "/sys/devices/system/cpu/cpu0/cpufreq/"
    return {"power_profile": _run(["powerprofilesctl", "get"]).strip(),
            "governor": _readf(cpu0 + "scaling_governor"), "driver": _readf(cpu0 + "scaling_driver"),
            "epp": _readf(cpu0 + "energy_performance_preference"),
            "platform_profile": _readf("/sys/firmware/acpi/platform_profile"),
            "platform_profile_choices": _readf("/sys/firmware/acpi/platform_profile_choices")}


def board_hint(board_name):
    b = (board_name or "").strip()
    return {"board": b, "known_elsewhere": OTHER_KNOWN_BOARDS.get(b)}
