"""Which laptop platform this is, and what can be controlled — found at the start of the service, read only.

The window shows the result at the first start and again when it changes (setting detect_seen holds the signature
of what was shown), together with the vendor programs that run at the same time (Uniwill Control Center, Clevo Control Center 3, Leishen ControlCenter): two programs that both send
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


def _f(name, state, reason=None, *actions):
    """One line of "What can be controlled": [name, ok | try | no, why it is not ok, what to do about it]."""
    return [name, state, reason, list(actions)]


# reasons and what the window offers for them (the window explains each reason in a sentence):
#   writes_off       experimental module, its commands are off           -> allow (the setting of that module)
#   oem_missing      no OEM driver, WMI path not chosen (Windows)        -> driver (EC Manager)
#   wmi_consent      WMI path chosen, its warning not accepted           -> driver
#   wmi_no_profile   WMI path without a profile of this project          -> driver, selfcheck
#   unknown_project  a project the official service does not know        -> selfcheck, report
#   no_ramfan        the EC does not report fan control (RamFan 1.5)     -> report
#   not_found        nothing of this kind on this laptop                 -> (none)
#   no_platform      no interface for modes or fans                      -> report


def platform_of(svc):
    """{platform, level, name, signals, features, page}; level: tested / known / experimental / none."""
    signals = []
    ec_info = getattr(svc, "ec_info", None) or {}
    ec_active = ec_info.get("active")
    clevo, leishen = getattr(svc, "clevo", None), getattr(svc, "leishen", None)
    pf = getattr(svc, "pf", None)
    # A Uniwill EC that answers comes first: some Uniwill boards (e.g. MECHREVO Yaoshi X6AR55xY, project 0x1A)
    # also expose the Clevo WMI GUID ABBC0F6D, so the Clevo interface is "present" there too. Same rule as
    # altplat.alt_platform(): Clevo / Leishen only when there is no Uniwill EC.
    uniwill_ec = ec_active not in (None, "none") and pf is not None and bool(pf.project_raw)
    if not uniwill_ec and clevo is not None and clevo.present:
        signals.append(f"Control Center 3.0 / Clevo interface ({clevo.dchu.name})")
        w = clevo.writes_allowed()
        st, why = ("try", None) if w else ("no", "writes_off")
        act = () if w else ("allow",)
        feats = [_f("Monitoring", "ok"), _f("Power modes", st, why, *act), _f("Fans", st, why, *act),
                 _f("Keyboard backlight", st, why, *act)]
        return {"platform": "clevo", "level": "experimental", "name": "Control Center 3.0 / Clevo",
                "signals": signals, "features": feats, "page": "modes", "allow_key": "clevo_writes"}
    if not uniwill_ec and leishen is not None and leishen.present:
        info = leishen.info or {}
        signals.append(f"Leishen / Thunderobot WMI block RW_GMWMI ({leishen.wmi.name})")
        signals.append(f"firmware answers: {'RGB' if info.get('kb_rgb') else 'single-colour'} keyboard, "
                       f"{3 if info.get('fans3') else 2} fans, fan table {info.get('fan_table')}")
        w = leishen.writes_allowed()
        st, why = ("ok", None) if w else ("no", "writes_off")
        act = () if w else ("allow",)
        feats = [_f("Monitoring", "ok"), _f("Power modes", st, why, *act), _f("Fans", st, why, *act),
                 _f("Keyboard backlight", st, why, *act) if info.get("kb_rgb") else _f("Keyboard backlight", "no", "not_found"),
                 _f("Windows key, touchpad", st, why, *act),
                 _f("Mode key", "ok", None) if IS_WIN else _f("Mode key", "no", "not_found")]
        return {"platform": "leishen", "level": "experimental", "name": "Leishen / Thunderobot",
                "signals": signals, "features": feats, "page": "modes", "allow_key": "leishen_writes"}
    if uniwill_ec:
        signals.append(f"Uniwill embedded controller via {ec_active}, project {pf.project_name} (0x{pf.project_raw:X})")
        level = pf.support
        no_profile = False
        if ec_active == "wmi":
            try:
                from . import platformdb
                no_profile = bool(platformdb.summary(pf.project_raw).get("fallback"))
            except Exception:  # noqa: BLE001
                no_profile = False
            if no_profile:
                signals.append("WMI path without a profile of this project")
        if not svc.fan_control:
            ctl = ("no", "no_ramfan", "report")
        elif no_profile:
            ctl = ("no", "wmi_no_profile", "driver", "selfcheck")
        elif level == "experimental":
            ctl = ("try", "unknown_project", "selfcheck", "report")
        else:
            ctl = ("ok", None)
        kb = (svc.keyboard.status() or {}).get("kind") not in (None, "none")
        feats = [_f("Monitoring", "ok"), _f("Power modes", *ctl), _f("Fans", *ctl),
                 _f("Battery care", *(("no", "wmi_no_profile", "driver", "selfcheck") if no_profile else ("ok", None))),
                 _f("Keyboard backlight", "ok") if kb else _f("Keyboard backlight", "no", "not_found")]
        return {"platform": "uniwill", "level": level, "name": pf.display_name or pf.project_name,
                "signals": signals, "features": feats, "page": "modes"}
    reason = ec_info.get("reason")
    if reason in ("oem_missing", "wmi_consent") and IS_WIN:
        signals.append("the Uniwill embedded controller is not reachable yet: " + reason)
        why, act = reason, ("driver",)
    else:
        signals.append("no firmware interface for modes or fans was found")
        why, act = "no_platform", ("report",)
    return {"platform": "unknown", "level": "none", "name": "", "signals": signals,
            "features": [_f("Monitoring", "ok"), _f("Power modes", "no", why, *act), _f("Fans", "no", why, *act)],
            "page": "driver" if why != "no_platform" else "info"}


def signature(r):
    """What the window showed: when it changes (a driver installed, commands allowed), the window comes again."""
    feats = "".join((f[1] or "?")[0] for f in r.get("features") or [])
    return f"{r.get('platform')}:{r.get('level')}:{feats}"[:60]


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
        r["signature"] = signature(r)
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
