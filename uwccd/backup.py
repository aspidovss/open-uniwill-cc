"""Export / import of settings.

* fans      — fan tables (M1T1 … M4T5 and the tables of the Custom slots): our export, or tables of the original
              Control Center (UserFanTables\\M*T*.json, same format);
* profiles  — mode profiles (power limits, CPU / GPU temperature limits, Dynamic Boost, slot names): our export, or
              the original's UserPofiles\\Mode*_Profile*.json (same format);
* settings  — everything else (lighting, light bar, battery, switches, automation, app binding, liquid cooler,
              language …): settings.json of the service.

Files: {"format": "open-uniwill-cc", "kind": "fans" | "backup", "version", "project", "project_id", "created",
        "tables": {...}, "profiles": {...}, "option": {...}, "settings": {...}}
"""
import glob
import json
import logging
import os
import sys
import time

from . import __version__, store

log = logging.getLogger("uwccd.backup")

FORMAT = "open-uniwill-cc"
# settings that describe this installation rather than the user's preferences
SETTINGS_SKIP = {"fan_manager", "force_fan_control", "force_single_color"}
PROFILE_KEYS = {
    "CPU": ("PL1", "PL2", "PL4", "PL1_Enabled", "PL2_Enabled", "PL1_dc", "PL1_dc_Enabled", "PL2_dc", "PL2_dc_Enabled",
            "TccOffsetSwitch", "TccOffset"),
    "GPU": ("ConfigurableTGPSwitch", "ConfigurableTGPTarget", "DynamicBoostSwitch", "DynamicBoost",
            "TargetTemperatureSwitch", "TargetTemperature"),
    "FAN": ("FanSwitchSpeedEnabled", "FanSwitchSpeed"),
}


def export(svc, what="all", table=None):
    """what: fans | all; table: one fan table name (fans only)."""
    p = svc.power
    names = [table] if table else list(p.tables.tables)
    out = {"format": FORMAT, "kind": "fans" if what == "fans" else "backup", "version": __version__,
           "project": svc.pf.project_name, "project_id": f"0x{svc.pf.project_id:X}",
           "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "tables": {n: p.tables.tables[n] for n in names if p.tables.tables.get(n)}}
    if what != "fans":
        out["profiles"] = dict(p.profiles)
        out["option"] = {k: v for k, v in p.option.items() if k.endswith("ProfileIndex") or k == "OperatingMode"}
        out["settings"] = {k: v for k, v in svc.settings_store.d.items() if k not in SETTINGS_SKIP}
        out["liquid"] = dict(getattr(svc.liquid, "cfg", {}) or {})
    return out


def _classify(obj, into):
    """Sort one JSON object (ours or an original Control Center file) into tables / profiles."""
    if not isinstance(obj, dict):
        return
    if obj.get("format") == FORMAT:
        for sect in ("tables", "profiles", "option", "settings", "liquid"):
            if obj.get(sect):
                into.setdefault(sect, {}).update(obj[sect])
        for k in ("project", "project_id"):
            into.setdefault(k, obj.get(k))
        return
    name = str(obj.get("Name", ""))
    if isinstance(obj.get("CPU"), list) and len(obj["CPU"]) == 16:            # a fan table (M1T1.json …)
        into.setdefault("tables", {})[name] = obj
    elif isinstance(obj.get("CPU"), dict) and name.startswith("Mode"):       # a profile (Mode1_Profile1.json …)
        into.setdefault("profiles", {})[name] = obj
    elif isinstance(obj.get("files"), list):                                  # several files picked in the UI
        for f in obj["files"]:
            _classify(f, into)


def parse(data):
    into = {}
    _classify(data, into)
    return into


def import_data(svc, data, sections=("fans", "profiles"), check_project=True):
    """Returns a summary; raises ValueError for an unusable file. Settings need a service restart."""
    d = parse(data)
    p = svc.power
    if not any(d.get(k) for k in ("tables", "profiles", "settings", "liquid")):
        raise ValueError("no fan tables, profiles or settings found in the file")
    if check_project and d.get("project_id") and d["project_id"] != f"0x{svc.pf.project_id:X}":
        raise ValueError(f"the file was made on project {d.get('project')} ({d['project_id']}), this laptop is "
                         f"{svc.pf.project_name} (0x{svc.pf.project_id:X}). Fan curves and limits of another laptop can "
                         "overheat this one; import anyway only if you know they fit.")
    res = {"tables": [], "profiles": [], "skipped": [], "settings": False, "restart": False}
    if "fans" in sections:
        for name, t in (d.get("tables") or {}).items():
            if name not in p.tables.tables:
                res["skipped"].append(f"{name}: no such table here")
                continue
            try:
                p.update_table(name, {k: t[k] for k in ("CPU", "GPU", "FanControlRespective") if k in t})
                res["tables"].append(name)
            except (ValueError, KeyError, TypeError) as e:
                res["skipped"].append(f"{name}: {e}")
    if "profiles" in sections:
        for name, prof in (d.get("profiles") or {}).items():
            if name not in p.profiles:
                res["skipped"].append(f"{name}: no such profile here")
                continue
            body = {sect: {k: prof[sect][k] for k in keys if k in (prof.get(sect) or {})}
                    for sect, keys in PROFILE_KEYS.items() if isinstance(prof.get(sect), dict)}
            if name.startswith("Mode4") and prof.get("CustomizeName"):
                body["CustomizeName"] = prof["CustomizeName"]
            for attempt in (body, {k: v for k, v in body.items() if k != "GPU"}):   # GPU values may not fit here
                try:
                    p.update_profile(name, attempt)
                    res["profiles"].append(name if attempt is body else f"{name} (without GPU values)")
                    break
                except (ValueError, KeyError, TypeError) as e:
                    err = e
            else:
                res["skipped"].append(f"{name}: {err}")
    if "settings" in sections and (d.get("settings") or d.get("liquid")):
        st = svc.settings_store
        st.d.update({k: v for k, v in (d.get("settings") or {}).items() if k not in SETTINGS_SKIP})
        store.save_json(st.p, st.d)
        if d.get("liquid"):
            store.save_json(store.path("liquid.json"), d["liquid"])
        res["settings"] = res["restart"] = True
    log.info("import: %d tables, %d profiles, settings=%s, skipped %s", len(res["tables"]), len(res["profiles"]),
             res["settings"], res["skipped"])
    return res


def original_dir():
    """Folder of the original Control Center with the user's tables and profiles (Windows)."""
    if sys.platform != "win32":
        return None
    base = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "OEM", "Control Center",
                        "UniwillService", "MyControlCenter")
    return base if os.path.isdir(os.path.join(base, "UserPofiles")) else None


def read_original():
    base = original_dir()
    if not base:
        return None
    files = []
    for pat in (os.path.join(base, "UserPofiles", "Mode*_Profile*.json"), os.path.join(base, "UserFanTables", "M*T*.json")):
        for f in sorted(glob.glob(pat)):
            try:
                with open(f, encoding="utf-8-sig") as fh:
                    files.append(json.load(fh))
            except (OSError, ValueError) as e:
                log.warning("original file %s: %s", f, e)
    return {"files": files, "dir": base}
