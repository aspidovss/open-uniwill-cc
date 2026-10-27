"""How the service reaches the embedded controller on Windows: OEM driver, WMI (beta) or nothing yet.

Setting "ec_backend":
    "auto" — OEM driver UWACPIDriver.sys; WMI only when the driver is missing and the user agreed (default)
    "oem"  — OEM driver only
    "wmi"  — Windows built-in WMI only (open implementation, not recommended, beta)
WMI is used only after the user accepted the warning in the window ("wmi_consent" = WMI_CONSENT_VERSION).
Without any path the service runs on NullEC: the window explains why and offers the choices.

ec_wmi.json — what works through WMI and how slow it may be. The factory values come from the platform profile of
the laptop (platformdb, uwccd/platforms/*.json); the user's copy in the data folder overrides them and can be edited
in the window (EC Manager, administrator rights), imported and exported.
"""
import copy
import logging
import os
import sys

from . import edition, platformdb, store
from .ec import ECError, MockEC, MockWmiEC, NullEC, open_ec

log = logging.getLogger("uwccd.ecaccess")
IS_WIN = sys.platform == "win32"

WMI_CONSENT_VERSION = 1
BACKENDS = ("auto", "oem", "wmi")
DOCS_URL = "https://github.com/aspidovss/open-uniwill-cc/tree/main/docs/EC"
CONFIG_FILE = "ec_wmi.json"

# Features of the window that depend on the EC. "on" — works, "slow" — works but takes seconds,
# "off" — greyed out. "locked" ones cannot be switched on through WMI (the firmware method is missing).
# What is on by default for a laptop comes from its platform profile (platformdb, uwccd/platforms/*.json).
FEATURES = {
    "modes":          {"locked": False},
    "fan_boost":      {"locked": False},
    "power_limits":   {"locked": False},
    "gpu_power":      {"locked": False},
    "super_performance": {"locked": False},
    "fan_tables":     {"locked": False},
    "fan_monitor":    {"locked": False},
    "battery":        {"locked": False},
    "switches":       {"locked": False},
    "lightbar_ec":    {"locked": False},
    "lc_ec":          {"locked": False},
    "power_boost_lc": {"locked": True},     # PWUP — OEM driver only
}
FEATURE_STATES = ("on", "slow", "off")

# generic WMI settings; the platform profile and then the user's ec_wmi.json override them
WMI_BASE = {
    "version": 1,
    "instance": "1_1",
    "timeout_s": 5,
    "poll": {"cache_ms": 4000, "monitor_s": 5, "status_s": 15},
    "always_write": ["0x767", "0xF5D-0xF5F", "0x7C7"],
    "no_cache": ["0xF5D-0xF5F"],
    "features": {k: "off" for k in FEATURES},
    "limits": {},
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def user_config():
    return store.load_json(store.path(CONFIG_FILE), {}) or {}


def factory(project=None):
    """Settings of the platform profile for the project (generic profile when the project is unknown)."""
    prof = platformdb.match(project)["profile"]
    w = prof.get("wmi") or {}
    cfg = _merge(WMI_BASE, {k: v for k, v in w.items()
                            if k in ("poll", "always_write", "no_cache", "features", "timeout_s", "instance")})
    acc = (prof.get("access") or {}).get("wmi") or {}
    if acc.get("instance"):
        cfg["instance"] = acc["instance"]
    cfg["wmi"] = {k: acc[k] for k in ("namespace", "class", "method", "encoding") if k in acc}
    cfg["limits"] = {f"0x{project:02X}": dict(prof["limits"])} if prof.get("limits") and project is not None else {}
    return cfg


def config(project=None):
    """Platform profile settings with the user's overrides; locked features stay off; hard caps hold."""
    cfg = _merge(factory(project), user_config())
    for k, f in FEATURES.items():
        if f["locked"]:
            cfg["features"][k] = "off"
        elif cfg["features"].get(k) not in FEATURE_STATES:
            cfg["features"][k] = "off"
    for pid, vals in list((cfg.get("limits") or {}).items()):
        try:
            cfg["limits"][pid] = {k: min(int(v), platformdb.CAPS[k]) for k, v in (vals or {}).items() if k in platformdb.CAPS}
        except (TypeError, ValueError):
            cfg["limits"].pop(pid, None)
    return cfg


def validate(cfg):
    """Check an imported / edited config; returns the cleaned user part. Raises ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("config must be a JSON object")
    out = {}
    for k, v in cfg.items():
        if k == "version":
            continue
        if k == "instance":
            out[k] = str(v)[:32]
        elif k == "timeout_s":
            v = float(v)
            if not 1 <= v <= 30:
                raise ValueError("timeout_s: 1..30")
            out[k] = v
        elif k == "poll":
            p = {}
            for pk, (lo, hi) in {"cache_ms": (0, 60000), "monitor_s": (1, 60), "status_s": (2, 300)}.items():
                if pk in v:
                    n = float(v[pk])
                    if not lo <= n <= hi:
                        raise ValueError(f"poll.{pk}: {lo}..{hi}")
                    p[pk] = n
            out[k] = p
        elif k in ("always_write", "no_cache"):
            from .ec import _hexset
            _hexset(v)                       # raises ValueError on a bad address
            out[k] = [str(x) for x in v]
        elif k in ("wmi", "encoding"):
            continue                         # comes from the platform profile, not editable here
        elif k == "features":
            f = {}
            for fk, fv in v.items():
                if fk not in FEATURES:
                    raise ValueError(f"unknown feature {fk}")
                if fv not in FEATURE_STATES:
                    raise ValueError(f"features.{fk}: on | slow | off")
                f[fk] = "off" if FEATURES[fk]["locked"] else fv
            out[k] = f
        elif k == "limits":
            lim = {}
            for pid, vals in (v or {}).items():
                proj = int(pid, 16)
                lim[f"0x{proj:02X}"] = platformdb.check_limits(vals, proj, f"limits.{pid}")
            out[k] = lim
        else:
            raise ValueError(f"unknown key {k}")
    return out


def save_user_config(cfg):
    clean = validate(cfg)
    clean["version"] = WMI_BASE["version"]
    store.save_json(store.path(CONFIG_FILE), clean)
    return clean


def reset_user_config():
    try:
        os.remove(store.path(CONFIG_FILE))
    except FileNotFoundError:
        pass


def _project_of(ec):
    try:
        return ec.read(0x740)
    except Exception:  # noqa: BLE001
        return None


def _wmi_cfg(project):
    cfg = config(project)
    lim = cfg.get("limits", {})
    cfg["limits"] = next((v for k, v in lim.items() if project is not None and int(k, 16) == project), None)
    return cfg


def apply_installer_choice(settings):
    """The Windows installer leaves its choice (auto / oem / wmi) in ec_backend.install; apply it once."""
    p = store.path("ec_backend.install")
    try:
        with open(p, encoding="utf-8-sig") as f:
            v = f.read().strip().lower()
    except OSError:
        return
    if v in BACKENDS:
        settings.set("ec_backend", v)
        log.info("EC path from the installer: %s", v)
    try:
        os.remove(p)
    except OSError:
        pass


def open_backend(settings, mock=False, prefer=None):
    """Returns (ec, info). info: backend setting, active path, reason when there is no EC access."""
    apply_installer_choice(settings)
    setting = settings.get("ec_backend", "auto")
    if setting not in BACKENDS:
        setting = "auto"
    consent = settings.get("wmi_consent", 0) == WMI_CONSENT_VERSION
    info = {"setting": setting, "active": None, "reason": None, "oem_present": None, "oem_error": None,
            "wmi_error": None, "consent": consent}
    if not IS_WIN and not mock:                       # Linux: kernel module / acpi_call, nothing to choose
        ec = open_ec(prefer)
        info.update(active="native", oem_present=None)
        return ec, info

    def oem():
        if mock:
            if os.environ.get("UWCC_MOCK_OEM", "1") == "0":
                raise ECError("mock: OEM driver missing")
            return MockEC()
        from .win.acpidrv import WinAcpiDriverEC
        return WinAcpiDriverEC()

    def wmi():
        hint = settings.get("ec_project")             # the project of the last start: its profile's WMI layout
        if mock:
            if os.environ.get("UWCC_MOCK_WMI", "1") == "0":
                raise ECError("mock: no WMI interface")
            ec = MockWmiEC(_wmi_cfg(hint))
        else:
            from .win.wmiec import WinWmiEC
            ec = WinWmiEC(_wmi_cfg(hint))
        project = _project_of(ec)                     # limits / features depend on the project read through WMI
        ec.configure(_wmi_cfg(project))
        ec.project = project
        return ec

    if setting in ("auto", "oem"):
        try:
            ec = oem()
            info.update(active="oem", oem_present=True)
            log.info("EC path: OEM driver")
            return ec, info
        except Exception as e:  # noqa: BLE001
            info.update(oem_present=False, oem_error=str(e))
            log.warning("OEM driver UWACPIDriver not available: %s", e)
    if setting == "oem" or (setting == "auto" and not consent):
        info.update(active="none", reason="oem_missing")
        return NullEC(), info
    if not consent:
        info.update(active="none", reason="wmi_consent")
        log.warning("WMI path selected but the warning was not accepted yet")
        return NullEC(), info
    try:
        ec = wmi()
        info.update(active="wmi")
        if info["oem_present"] is None:
            try:
                oem().close()
                info["oem_present"] = True
            except Exception:  # noqa: BLE001
                info["oem_present"] = False
        log.warning("EC path: WMI (beta, slow; no SMRW / PWUP)")
        return ec, info
    except Exception as e:  # noqa: BLE001
        info.update(active="none", reason="wmi_failed", wmi_error=str(e))
        log.error("WMI EC path failed: %s", e)
        return NullEC(), info


def oem_driver_dirs():
    """Where an OEM driver package (UWACPIDriver.inf / .sys / .cat) is looked for:
    %ProgramData%\\UWCC\\driver — the place recommended for the free build (the user puts the manufacturer's files there),
    then the driver folder of the installed program (non-free build)."""
    pd = os.environ.get("ProgramData", r"C:\ProgramData") if IS_WIN else os.path.dirname(store.DATA_DIR)
    dirs = [os.path.join(pd, "UWCC", "driver")]
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(os.path.dirname(sys.executable), "driver"))
    return dirs


def oem_driver_package():
    for d in oem_driver_dirs():
        try:
            files = os.listdir(d)
        except OSError:
            continue
        low = {f.lower(): f for f in files}            # the Windows driver store keeps lower-case names
        if "uwacpidriver.inf" in low:
            return {"dir": d, "inf": os.path.join(d, low["uwacpidriver.inf"]), "sys": "uwacpidriver.sys" in low,
                    "cat": any(f.endswith(".cat") for f in low)}
    return None


def install_oem_driver(mock=False):
    """pnputil /add-driver UWACPIDriver.inf /install (the service runs as SYSTEM)."""
    pkg = oem_driver_package()
    if not pkg:
        raise LookupError("no OEM driver package: put UWACPIDriver.inf, .sys and .cat into " + oem_driver_dirs()[0])
    if not pkg["sys"]:
        raise LookupError("UWACPIDriver.sys is missing next to UWACPIDriver.inf in " + pkg["dir"])
    if mock or not IS_WIN:
        log.warning("OEM driver install simulated: %s", pkg["inf"])
        return {"installed": True, "simulated": True, "dir": pkg["dir"], "output": ""}
    import subprocess
    from .win.winplat import CREATE_NO_WINDOW
    r = subprocess.run([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "pnputil.exe"),
                        "/add-driver", pkg["inf"], "/install"], capture_output=True, text=True, timeout=120,
                       creationflags=CREATE_NO_WINDOW, check=False)
    out = (r.stdout or "") + (r.stderr or "")
    log.warning("OEM driver install from %s: rc=%d %s", pkg["dir"], r.returncode, out.strip()[-300:])
    if r.returncode not in (0, 3010):                    # 3010: installed, reboot required
        raise RuntimeError(f"pnputil failed ({r.returncode}): {out.strip()[-300:]}")
    return {"installed": True, "reboot": r.returncode == 3010, "dir": pkg["dir"], "output": out.strip()[-1000:]}


def oem_driver_info():
    """Installed OEM driver: present / version (Windows driver store), for EC Manager."""
    if not IS_WIN:
        return None
    try:
        from .win.winplat import wmi_query
        rows = wmi_query("SELECT DeviceName, DriverVersion, DriverDate, DriverProviderName, InfName "
                         "FROM Win32_PnPSignedDriver WHERE DeviceID LIKE 'ACPI\\\\INOU0000%'")
        if not rows:
            return {"installed": False}
        r = rows[0]
        return {"installed": True, "name": r.DeviceName, "version": r.DriverVersion,
                "date": str(r.DriverDate or "")[:8], "provider": r.DriverProviderName, "inf": r.InfName}
    except Exception as e:  # noqa: BLE001
        log.debug("driver info: %s", e)
        return None


def monitoring(settings, active):
    """Monitoring switches of EC Manager -> "full" | "light" (temperatures only, rarely) | "off"."""
    if settings.get("monitor_off_all", False):
        return "off"
    if (active == "oem" and settings.get("monitor_off_oem", False)) or \
            (active == "wmi" and settings.get("monitor_off_wmi", False)):
        return "light"
    return "full"


def status(svc):
    info = dict(svc.ec_info)
    st = svc.settings_store
    info["consent"] = st.get("wmi_consent", 0) == WMI_CONSENT_VERSION      # live: changed in the window
    info["setting"] = st.get("ec_backend", "auto") if st.get("ec_backend", "auto") in BACKENDS else "auto"
    pid = svc.pf.project_raw if info.get("active") not in ("none",) else st.get("ec_project")
    cfg = config(pid)
    feats = {k: "on" for k in FEATURES}
    if info.get("active") == "wmi":
        feats = dict(cfg["features"])
    elif info.get("active") == "none":
        feats = {k: "off" for k in FEATURES}
    ec = svc.ec
    stats = getattr(ec, "stats", None)
    plat = platformdb.summary(pid)
    return {
        **info,
        "windows": IS_WIN or svc.mock,
        "consent_version": WMI_CONSENT_VERSION,
        "tested": (plat["status"] == "verified") if pid is not None else None,
        "tested_names": platformdb.builtin().get("uniwill-0x10", {}).get("name", ""),
        "platform": plat,
        "docs": DOCS_URL,
        "features": feats,
        "feature_list": [{"key": k, "locked": v["locked"], "wmi_default": factory(pid)["features"].get(k, "off")}
                         for k, v in FEATURES.items()],
        "config": cfg,
        "user_config": user_config(),
        "caps": platformdb.CAPS,
        "stats": dict(stats) if stats else None,
        "instance": getattr(ec, "instance_name", None),
        "driver": getattr(svc, "oem_driver", None),
        "edition": edition(),
        "driver_dir": oem_driver_dirs()[0],
        "driver_package": oem_driver_package(),
        "monitoring": {"level": monitoring(st, info.get("active")),
                       "off_oem": bool(st.get("monitor_off_oem", False)), "off_wmi": bool(st.get("monitor_off_wmi", False)),
                       "off_all": bool(st.get("monitor_off_all", False))},
        "admin": svc.admin.status() if getattr(svc, "admin", None) else None,
        "selfcheck": svc.selfcheck.summary() if getattr(svc, "selfcheck", None) else None,
    }
