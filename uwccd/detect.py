"""Which laptop platform this is, and what can be controlled — found at the start of the service, read only.

The window shows the result once, at the first start (setting detect_seen), together with the vendor programs that run
at the same time (Uniwill Control Center, Clevo Control Center 3, Leishen ControlCenter): two programs that both send
commands to the firmware undo each other's settings, so the window offers to close them.

Signals, from cheap to exact:
  * the laptop (DMI vendor, model, board);
  * the firmware interfaces the modules found: Uniwill EC (access path and project ID), Control Center 3.0 / Clevo
    (CLV0001 / DCHU), Leishen / Thunderobot (WMI block RW_GMWMI) — each module checks its own with read commands only;
  * vendor programs running now (Windows).
"""
import logging
import os
import re
import subprocess
import sys
import threading

log = logging.getLogger("uwccd.detect")

IS_WIN = sys.platform == "win32"

# vendor programs that also drive the firmware: name, regex on the executable path (lower case)
VENDOR_APPS = (
    ("Leishen ControlCenter", r"\\leishen\\"),
    ("Uniwill Control Center", r"\\mycontrolcenter\\|\\gcuservice\.exe$|\\gcubridge\.exe$"),
    ("Clevo Control Center 3", r"\\clevo\\|\\control center 3|\\controlcenter3"),
)
# our own files never count (the tray app is ControlCenter.exe too)
OWN_RE = r"\\uwcc control center\\|\\open-uniwill-cc\\|\\uwccd\.exe$|\\uwccctl\.exe$"


def vendor_processes():
    """[{pid, name, path, app}] of vendor control programs running now (Windows; [] elsewhere)."""
    if not IS_WIN:
        return []
    try:
        from .win import winplat
        rows = winplat.wmi_query("SELECT ProcessId, Name, ExecutablePath FROM Win32_Process")
    except Exception as e:  # noqa: BLE001
        log.debug("process list: %s", e)
        return []
    own = os.path.dirname(os.path.abspath(sys.executable)).lower()
    out = []
    for r in rows:
        path = (getattr(r, "ExecutablePath", None) or "").lower()
        if not path or path.startswith(own) or re.search(OWN_RE, path):
            continue
        for app, rx in VENDOR_APPS:
            if re.search(rx, path):
                out.append({"pid": int(r.ProcessId), "name": r.Name, "path": r.ExecutablePath, "app": app})
                break
    return out


def close_processes(pids, allowed):
    """Ends the vendor programs (only processes from the last list); returns the pids that were ended."""
    done = []
    for pid in pids:
        if pid not in allowed:
            continue
        try:
            r = subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False, timeout=15)
            if r.returncode == 0:
                done.append(pid)
            else:
                log.warning("taskkill %s: %s", pid, (r.stdout + r.stderr).strip())
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("taskkill %s: %s", pid, e)
    if done:
        log.info("vendor programs closed: %s", done)
    return done


def _laptop():
    from .hw import dmi
    return {"vendor": dmi("sys_vendor"), "model": dmi("product_name"), "board": dmi("board_name"),
            "bios": dmi("bios_version")}


def platform_of(svc):
    """{platform, level, name, signals, features}; level: tested / known / experimental / none."""
    signals, feats = [], []
    ec_active = (getattr(svc, "ec_info", None) or {}).get("active")
    clevo, leishen = getattr(svc, "clevo", None), getattr(svc, "leishen", None)
    if clevo is not None and clevo.present:
        signals.append(f"Control Center 3.0 / Clevo interface ({clevo.dchu.name})")
        feats = [("Monitoring", "ok"), ("Power modes", "try"), ("Fans", "try"), ("Keyboard backlight", "try")]
        return {"platform": "clevo", "level": "experimental", "name": "Control Center 3.0 / Clevo",
                "signals": signals, "features": feats, "page": "clevo"}
    if leishen is not None and leishen.present:
        info = leishen.info or {}
        signals.append(f"Leishen / Thunderobot WMI block RW_GMWMI ({leishen.wmi.name})")
        signals.append(f"firmware answers: {'RGB' if info.get('kb_rgb') else 'single-colour'} keyboard, "
                       f"{3 if info.get('fans3') else 2} fans, fan table {info.get('fan_table')}")
        feats = [("Monitoring", "ok"), ("Power modes", "ok"), ("Fans", "ok"),
                 ("Keyboard backlight", "ok" if info.get("kb_rgb") else "no"), ("Windows key, touchpad", "ok"),
                 ("Mode key", "ok" if IS_WIN else "no")]
        return {"platform": "leishen", "level": "experimental", "name": "Leishen / Thunderobot",
                "signals": signals, "features": feats, "page": "leishen"}
    pf = getattr(svc, "pf", None)
    if ec_active not in (None, "none") and pf is not None and pf.project_raw:
        signals.append(f"Uniwill embedded controller via {ec_active}, project {pf.project_name} (0x{pf.project_raw:X})")
        ok = "ok" if svc.fan_control else "no"
        feats = [("Monitoring", "ok"), ("Power modes", ok), ("Fans", ok), ("Battery care", "ok"),
                 ("Keyboard backlight", "ok" if (svc.keyboard.status() or {}).get("kind") not in (None, "none") else "no")]
        return {"platform": "uniwill", "level": pf.support, "name": pf.display_name or pf.project_name,
                "signals": signals, "features": feats, "page": "modes"}
    signals.append("no firmware interface for modes or fans was found")
    return {"platform": "unknown", "level": "none", "name": "", "signals": signals,
            "features": [("Monitoring", "ok"), ("Power modes", "no"), ("Fans", "no")], "page": "monitor"}


class Detector:
    """Runs once at the start (in a thread: the process list takes a moment on Windows)."""

    def __init__(self, svc):
        self.svc = svc
        self.result = None
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="detect").start()

    def run(self):
        try:
            r = {**platform_of(self.svc), "laptop": _laptop(), "vendor_apps": vendor_processes()}
        except Exception as e:  # noqa: BLE001
            log.warning("platform detection: %s", e)
            r = {"platform": "unknown", "level": "none", "signals": [str(e)], "features": [], "vendor_apps": []}
        with self.lock:
            self.result = r
        log.info("platform: %s (%s)%s", r.get("platform"), r.get("level"),
                 "; vendor programs running: " + ", ".join(sorted({a["app"] for a in r["vendor_apps"]}))
                 if r.get("vendor_apps") else "")
        self.svc.emit("detect", {})
        return r

    def status(self):
        with self.lock:
            r = dict(self.result or {"pending": True})
        r["seen"] = self.svc.settings_store.get("detect_seen")
        return r

    def close(self, pids):
        allowed = {a["pid"] for a in (self.result or {}).get("vendor_apps", [])}
        done = close_processes([int(p) for p in pids], allowed)
        self.run()                                           # the list again, without the closed programs
        return done
