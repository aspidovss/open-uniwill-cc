"""Windows counterparts of the small Linux helpers (DMI, PCI vendors, processes, webcam, WMI)."""
import logging
import os
import subprocess
import threading
import winreg

log = logging.getLogger("uwccd.win")

CREATE_NO_WINDOW = 0x08000000
_BIOS_KEY = r"HARDWARE\DESCRIPTION\System\BIOS"
_DMI_MAP = {"sys_vendor": "SystemManufacturer", "product_name": "SystemProductName",
            "board_name": "BaseBoardProduct", "bios_version": "BIOSVersion", "bios_date": "BIOSReleaseDate"}
DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def _reg(path, name, default=None, root=winreg.HKEY_LOCAL_MACHINE):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return default


def dmi(field):
    if field == "ec_firmware_release":
        a, b = _reg(_BIOS_KEY, "ECFirmwareMajorRelease"), _reg(_BIOS_KEY, "ECFirmwareMinorRelease")
        return f"{a}.{b}" if a is not None and a != 0xFF else ""
    v = _reg(_BIOS_KEY, _DMI_MAP.get(field, field), "")
    return str(v).strip() if v is not None else ""


def display_vendors():
    """PCI vendor ids ('0x10de', ...) of the installed display adapters."""
    out = set()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DISPLAY_CLASS) as cls:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(cls, i)
                except OSError:
                    break
                i += 1
                mid = (_reg(DISPLAY_CLASS + "\\" + sub, "MatchingDeviceId", "") or "").lower()
                if "ven_" in mid:
                    out.add("0x" + mid.split("ven_")[1][:4])
    except OSError:
        pass
    return out


def cpu_vendor():
    return _reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "VendorIdentifier", "") or ""


def cpu_model():
    return (_reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString", "") or "").strip()


def process_names():
    import psutil
    names = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower()
        if n:
            names.add(n)
            if n.endswith(".exe"):
                names.add(n[:-4])
    return names


def powershell(script, timeout=20):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW, check=False)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


# -- webcam: the built-in camera as a PnP device (Camera / Image class) -------------------------------------
_CAM = "Get-PnpDevice -Class Camera,Image -ErrorAction SilentlyContinue | Where-Object { $_.Present }"
_cam_cache = {"t": 0.0, "v": None}


def webcam_state():
    import time
    if time.time() - _cam_cache["t"] < 30:
        return _cam_cache["v"]
    try:
        rc, out, _ = powershell(_CAM + " | ForEach-Object { $_.Status }")
        states = [x.strip() for x in out.splitlines() if x.strip()]
        v = None if rc or not states else all(s == "OK" for s in states)
    except (OSError, subprocess.SubprocessError):
        v = None
    _cam_cache.update(t=time.time(), v=v)
    return v


def set_webcam(on):
    verb = "Enable-PnpDevice" if on else "Disable-PnpDevice"
    rc, _, err = powershell(f"{_CAM} | {verb} -Confirm:$false")
    _cam_cache["t"] = 0
    if rc:
        raise OSError(err or f"{verb} failed")


# -- WMI ---------------------------------------------------------------------------------------------------
_wmi_local = threading.local()


def wmi(namespace=r"root\cimv2"):
    """Per-thread WMI connection (COM objects are apartment-bound)."""
    import pythoncom
    import win32com.client
    cache = getattr(_wmi_local, "c", None)
    if cache is None:
        pythoncom.CoInitialize()
        cache = _wmi_local.c = {}
    if namespace not in cache:
        cache[namespace] = win32com.client.GetObject(f"winmgmts:{{impersonationLevel=impersonate}}!\\\\.\\{namespace}")
    return cache[namespace]


def wmi_query(query, namespace=r"root\cimv2"):
    try:
        return list(wmi(namespace).ExecQuery(query))
    except Exception as e:  # noqa: BLE001
        log.debug("WMI %s: %s", query, e)
        return []


def acl_users_read(path):
    """Let local users read the API token (the Linux build uses group uwcc for the same purpose)."""
    subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", "*S-1-5-18:F", "*S-1-5-32-544:F", "*S-1-5-32-545:R"],
                   capture_output=True, creationflags=CREATE_NO_WINDOW, check=False)


def data_root():
    return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UWCC")
