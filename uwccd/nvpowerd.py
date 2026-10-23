"""Is the NVIDIA service that runs Dynamic Boost there?  Without it the Dynamic Boost value in the profiles does
nothing: on Linux it is nvidia-powerd (systemd), on Windows the "NVIDIA Platform Controllers and Framework"
device driver (NVPCF) installed with the notebook graphics driver."""
import logging
import shutil
import subprocess
import sys
import time

log = logging.getLogger("uwccd.gpu")
_cache = (0.0, None)


def status(refresh=False):
    global _cache
    t, v = _cache
    if v is not None and not refresh and time.time() - t < 60:
        return v
    if sys.platform == "win32":
        v = _windows()
    else:
        v = _linux()
    _cache = (time.time(), v)
    return v


def _linux():
    if not shutil.which("systemctl"):
        return {"service": "nvidia-powerd", "present": False, "active": False, "can_enable": False}
    def sc(*a):
        return subprocess.run(["systemctl", *a, "nvidia-powerd.service"], capture_output=True, text=True,
                              timeout=5, check=False).stdout.strip()
    load = sc("show", "-p", "LoadState", "--value")
    present = load == "loaded"
    active = sc("is-active") == "active"
    return {"service": "nvidia-powerd", "present": present, "active": active, "can_enable": present and not active}


def _windows():
    from .win.winplat import powershell
    _rc, out, _err = powershell("Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
                     "Where-Object { $_.FriendlyName -like '*Platform Controllers*' } | "
                     "Select-Object -First 1 -ExpandProperty Status")
    out = out or ""
    present = bool(out.strip())
    return {"service": "NVIDIA Platform Controllers and Framework", "present": present,
            "active": out.strip() == "OK", "can_enable": False}


def enable():
    if sys.platform == "win32":
        raise NotImplementedError("install the NVIDIA notebook driver package (it contains the Platform Framework)")
    r = subprocess.run(["systemctl", "enable", "--now", "nvidia-powerd.service"], capture_output=True, text=True,
                       timeout=20, check=False)
    if r.returncode:
        raise OSError((r.stderr or r.stdout).strip() or "systemctl failed")
    log.info("nvidia-powerd enabled")
    return status(refresh=True)
