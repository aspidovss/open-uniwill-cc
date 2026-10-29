"""Platform profiles: what the program knows about one laptop platform, as data (uwccd/platforms/*.json).

A profile holds
  * identity      — Uniwill project ID (EC 0x740) it applies to, models, tested EC / BIOS versions;
  * status        — verified (tested by the authors) | community (sent by users) | draft (own self-check) | unknown;
  * access        — the OEM driver and the WMI interface (class, method, instance, bit layout of the call);
  * wmi           — which functions work through WMI, polling, registers that are always written / never cached;
  * limits        — power limits used instead of the firmware table SMRW (not reachable through WMI);
  * notes         — what is special about this platform.

Built-in profiles ship with the program; profiles the user imports or makes with the self-check live in
<data>/platforms/ and win over a built-in one of the same project (shown as "changed by the user").
Changing them needs administrator rights (admin.py). Hard caps (CAPS) cannot be exceeded by any profile or
ec_wmi.json; for a project that has a built-in verified profile the power limits may only go down.
"""
import copy
import glob
import json
import logging
import os
import re

from . import store

log = logging.getLogger("uwccd.platforms")

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platforms")
GENERIC_ID = "generic-uniwill"
STATUSES = ("verified", "community", "draft", "unknown")
SCHEMA = 1

# Hard caps: no profile, import or ec_wmi.json may go above them.
# Raised in 1.6.6 by a report of a Mechrevo Yaoshi (Core Ultra 9 275HX, RTX 5080): PL1 210 W, cTGP +70 W over the
# default 80 W (150 W in all); DynamicBoostCpuTdp 255 is the firmware's "no value".
CAPS = {"PL1": 250, "PL2": 250, "PL4": 300, "TccOffset": 63, "DefaultTGP": 200, "ConfigurableTGP": 100,
        "DynamicBoost": 50, "TargetTemperature": 100, "DynamicBoostCpuTdp": 255}
# for a project with a verified built-in profile these may only be lowered (TccOffset: a larger offset is cooler)
NOT_ABOVE_BUILTIN = ("PL1", "PL2", "PL4", "DefaultTGP", "ConfigurableTGP", "DynamicBoost", "DynamicBoostCpuTdp",
                     "TargetTemperature")
LIMIT_KEYS = tuple(CAPS)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")


def _load(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            p = json.load(f)
        if isinstance(p, dict) and p.get("id"):
            return p
    except (OSError, ValueError) as e:
        log.warning("platform profile %s: %s", path, e)
    return None


def builtin():
    out = {}
    for f in sorted(glob.glob(os.path.join(BUILTIN_DIR, "*.json"))):
        p = _load(f)
        if p:
            out[p["id"]] = p
    return out


def user_dir():
    return store.path("platforms")


def user():
    out = {}
    for f in sorted(glob.glob(os.path.join(user_dir(), "*.json"))):
        p = _load(f)
        if p:
            out[p["id"]] = p
    return out


def _projects(p):
    out = []
    for x in ((p.get("match") or {}).get("project") or []):
        try:
            out.append(int(str(x), 16))
        except ValueError:
            pass
    return out


def _find(profiles, project):
    if project is None:
        return None
    return next((p for p in profiles.values() if project in _projects(p)), None)


def builtin_for(project):
    return _find(builtin(), project)


def match(project):
    """-> {"profile", "source": builtin | user, "modified": a user profile replaces a built-in one, "builtin"}"""
    b = builtin()
    base = _find(b, project)
    u = _find(user(), project)
    if u:
        return {"profile": u, "source": "user", "modified": base is not None, "builtin": base}
    if base:
        return {"profile": base, "source": "builtin", "modified": False, "builtin": base}
    return {"profile": b.get(GENERIC_ID) or {"id": GENERIC_ID, "status": "unknown", "name": "Unknown laptop"},
            "source": "builtin", "modified": False, "builtin": None, "fallback": True}


def summary(project):
    m = match(project)
    p = m["profile"]
    return {"id": p.get("id"), "name": p.get("name"), "status": p.get("status", "unknown"), "source": m["source"],
            "modified": m["modified"], "fallback": bool(m.get("fallback")), "tested": p.get("tested"),
            "notes": p.get("notes"), "project": None if project is None else f"0x{project:02X}",
            "limits": p.get("limits"), "access": p.get("access")}


# -- validation -----------------------------------------------------------------------------------------
def check_limits(vals, project=None, where="limits"):
    """Hard caps; for a project with a verified built-in profile the values may only go down. -> cleaned dict"""
    if not isinstance(vals, dict):
        raise ValueError(f"{where}: an object expected")
    out = {}
    for k, v in vals.items():
        if k not in CAPS:
            raise ValueError(f"{where}: unknown key {k}")
        v = int(v)
        if not 0 <= v <= CAPS[k]:
            raise ValueError(f"{where}.{k}: 0..{CAPS[k]}")
        out[k] = v
    if project is not None:
        b = builtin_for(project)
        bl = (b or {}).get("limits") if (b or {}).get("status") == "verified" else None
        for k in NOT_ABOVE_BUILTIN:
            if bl and k in out and k in bl and out[k] > bl[k]:
                raise ValueError(f"{where}.{k}: at most {bl[k]} on this platform (factory value)")
    if out and not out.get("PL4"):
        raise ValueError(f"{where}: PL4 is required")
    return out


def validate(p):
    """Check an imported / generated profile. Raises ValueError; returns the cleaned profile."""
    from .ecaccess import validate as validate_wmi
    if not isinstance(p, dict):
        raise ValueError("profile must be a JSON object")
    pid = str(p.get("id", ""))
    if not ID_RE.match(pid):
        raise ValueError("id: lowercase letters, digits, . _ - (up to 48)")
    out = {"schema": SCHEMA, "id": pid, "name": str(p.get("name") or pid)[:120],
           "vendor": str(p.get("vendor") or "")[:40]}
    st = p.get("status", "draft")
    if st not in STATUSES:
        raise ValueError("status: " + " | ".join(STATUSES))
    out["status"] = "community" if st == "verified" else st          # "verified" only for built-in profiles
    projects = []
    for x in ((p.get("match") or {}).get("project") or []):
        v = int(str(x), 16)
        if not 0 <= v <= 0xFF:
            raise ValueError("match.project: 0x00..0xFF")
        projects.append(f"0x{v:02X}")
    if not projects:
        raise ValueError("match.project: at least one project ID")
    out["match"] = {"project": projects}
    if p.get("tested"):
        t = p["tested"]
        out["tested"] = {k: ([str(x)[:40] for x in t[k]][:10] if isinstance(t.get(k), list) else str(t[k])[:60])
                         for k in ("ec", "bios", "date", "by") if k in t}
    acc = p.get("access") or {}
    out["access"] = {}
    if isinstance(acc.get("oem"), dict):
        o = acc["oem"]
        out["access"]["oem"] = {"driver": str(o.get("driver", "UWACPIDriver"))[:40], "smrw": bool(o.get("smrw", True)),
                                "pwup": bool(o.get("pwup", True))}
    if isinstance(acc.get("wmi"), dict):
        w = acc["wmi"]
        enc = w.get("encoding") or {}
        e = {"read_flag_bit": int(enc.get("read_flag_bit", 40)), "value_shift": int(enc.get("value_shift", 16)),
             "read_mask": int(enc.get("read_mask", 255))}
        if not 16 <= e["read_flag_bit"] <= 60 or not 8 <= e["value_shift"] <= 40 or not 1 <= e["read_mask"] <= 0xFFFF:
            raise ValueError("access.wmi.encoding: read_flag_bit 16..60, value_shift 8..40, read_mask 1..65535")
        for k in ("namespace", "class", "method"):
            if k in w and not re.match(r"^[A-Za-z0-9_\\]{1,64}$", str(w[k])):
                raise ValueError(f"access.wmi.{k}: letters, digits, _ and \\ only")
        out["access"]["wmi"] = {"namespace": str(w.get("namespace", "root\\WMI")), "class": str(w.get("class", "AcpiTest_MULong")),
                                "method": str(w.get("method", "GetSetULong")), "instance": str(w.get("instance", "1_1"))[:32],
                                "encoding": e, "firmware": [str(x)[:8] for x in (w.get("firmware") or [])][:16],
                                "smrw": bool(w.get("smrw", False)), "pwup": False}
    if p.get("wmi"):
        out["wmi"] = validate_wmi({k: v for k, v in p["wmi"].items() if k != "limits"})
    if p.get("limits"):
        lim = None
        for pr in projects:
            lim = check_limits(p["limits"], int(pr, 16))
        out["limits"] = lim
    if isinstance(p.get("notes"), dict):
        out["notes"] = {lang: [str(x)[:600] for x in (v if isinstance(v, list) else [v])][:10]
                        for lang, v in p["notes"].items() if lang in ("en", "ru")}
    if isinstance(p.get("evidence"), dict):
        out["evidence"] = {str(k)[:40]: str(v)[:300] for k, v in list(p["evidence"].items())[:40]}
    return out


def save_user(p):
    clean = validate(p)
    os.makedirs(user_dir(), exist_ok=True)
    for old_id, old in user().items():          # one user profile per project
        if set(_projects(old)) & set(_projects(clean)) and old_id != clean["id"]:
            os.remove(os.path.join(user_dir(), old_id + ".json"))
    store.save_json(os.path.join(user_dir(), clean["id"] + ".json"), clean)
    log.warning("platform profile %s saved (%s)", clean["id"], clean["status"])
    return clean


def reset_user(project):
    """Remove the user's profile for the project (the built-in one applies again)."""
    removed = []
    for pid, p in user().items():
        if project in _projects(p):
            os.remove(os.path.join(user_dir(), pid + ".json"))
            removed.append(pid)
    return removed


def export(project):
    return copy.deepcopy(match(project)["profile"])
