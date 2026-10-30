"""Liquid cooler curves (1.6.8): a fan curve and pump steps, one common set plus an optional set per laptop mode,
and named cooler profiles.

    fan curve   [[°C, %], ...]   2..17 points, temperatures rising, duty not falling; linear between points, flat
                                 before the first and after the last point
    pump steps  [[°C, V], ...]   1..4 steps "from this temperature on": 0 (off) / 7 / 8 / 11 V, not falling; below
                                 the first step the pump runs at the first voltage. 0 (off) only as the first level:
                                 e.g. [[0, 0], [40, 7], [70, 11]] starts the pump at 40 °C (it then runs at least the
                                 "pump idle" minimum run time). No 12 V on a curve.

    curves = {"common": {"fan": [...], "pump": [...]}, "office": None | {...}, "gaming": ..., "turbo": ..., "custom": ...}

"Automatic" uses "common"; "Follow the laptop" uses the set of the laptop's mode, or "common" when the mode has none.
"""
import copy
import re

MODE_KEYS = ("office", "gaming", "turbo", "custom")
LAPTOP_MODE_KEY = {0: "office", 1: "gaming", 2: "turbo", 3: "custom"}      # EC operating mode -> key
CURVE_KEYS = ("common",) + MODE_KEYS
PUMP_LEVELS = (0, 7, 8, 11)          # 0 = off (only below the first running step); the default running levels
ALL_VOLTAGES = (7, 8, 11, 12)        # all the cooler firmware knows (pump selector 2, 3, 0, 1); it cannot be asked
DEFAULT_RUNNING = (7, 8, 11)         # without "own pump limits": 12 V is not used (the OEM software never does)


def levels(running=None):
    """Pump levels allowed on a curve: off + the running voltages."""
    return (0,) + tuple(sorted(running or DEFAULT_RUNNING))


def clamp_voltage(v, running=None):
    """A running voltage outside the allowed ones -> the nearest allowed (the next higher one first)."""
    run = sorted(running or DEFAULT_RUNNING)
    if not v or v in run:
        return v
    higher = [x for x in run if x >= v]
    return higher[0] if higher else run[-1]


def clamp_set(cs, running=None):
    """A curve set with every pump step moved into the allowed voltages (steps that become equal are merged)."""
    out, last = [], None
    for t, v in cs["pump"]:
        v = clamp_voltage(v, running)
        if last is not None and v < last:
            v = last
        if out and out[-1][1] == v:
            continue
        out.append([t, v])
        last = v
    return {"fan": cs["fan"], "pump": out}


def clamp_curves(curves, running=None):
    c = full(curves)
    return {k: (clamp_set(v, running) if v else v) for k, v in c.items()}
MAX_FAN_POINTS = 17
MAX_PUMP_STEPS = 4

BUILTIN_PROFILES = {
    "quiet": {"name": "Quiet", "curves": {
        "common": {"fan": [[45, 20], [60, 25], [70, 40], [80, 60], [90, 85], [100, 100]],
                   "pump": [[0, 8], [80, 11]]}}},
    "balanced": {"name": "Balanced", "curves": {
        "common": {"fan": [[40, 25], [55, 30], [65, 45], [75, 65], [85, 85], [95, 100]],
                   "pump": [[0, 8], [70, 11]]}}},
    "performance": {"name": "Performance", "curves": {
        "common": {"fan": [[35, 40], [50, 50], [60, 65], [70, 80], [80, 100]],
                   "pump": [[0, 11]]}}},
}
DEFAULT_PROFILE = "balanced"
# "Follow the laptop" before 1.6.8: a fixed duty per laptop mode and the pump at 11 V — kept as flat per-mode curves
OLD_LAPTOP_FAN = {"office": 40, "gaming": 60, "turbo": 90, "custom": 90}


def flat(fan, pump=11):
    return {"fan": [[20, int(fan)], [100, int(fan)]], "pump": [[0, int(pump)]]}


def full(curves):
    """All keys present; missing per-mode sets are None."""
    out = {k: None for k in CURVE_KEYS}
    out.update(copy.deepcopy(curves or {}))
    if not out.get("common"):
        out["common"] = copy.deepcopy(BUILTIN_PROFILES[DEFAULT_PROFILE]["curves"]["common"])
    return out


def check_set(s, where="curve", running=None):
    if not isinstance(s, dict):
        raise ValueError(f"{where}: an object with fan and pump expected")
    fan = s.get("fan")
    if not isinstance(fan, list) or not 2 <= len(fan) <= MAX_FAN_POINTS:
        raise ValueError(f"{where}: fan curve needs 2..{MAX_FAN_POINTS} points")
    out_f, last_t, last_d = [], -1, -1
    for p in fan:
        t, d = int(p[0]), int(p[1])
        if not 0 <= t <= 100 or not 0 <= d <= 100:
            raise ValueError(f"{where}: fan point {t} °C / {d} %: 0..100 °C, 0..100 %")
        if t <= last_t:
            raise ValueError(f"{where}: fan curve temperatures must rise")
        if d < last_d:
            raise ValueError(f"{where}: fan duty must not fall with the temperature")
        out_f.append([t, d])
        last_t, last_d = t, d
    pump = s.get("pump")
    if not isinstance(pump, list) or not 1 <= len(pump) <= MAX_PUMP_STEPS:
        raise ValueError(f"{where}: pump curve needs 1..{MAX_PUMP_STEPS} steps")
    out_p, last_t, last_v = [], -1, 0
    for p in pump:
        t, v = int(p[0]), int(p[1])
        if not 0 <= t <= 100:
            raise ValueError(f"{where}: pump step at {t} °C: 0..100 °C")
        allowed = levels(running)
        if v not in allowed:
            raise ValueError(f"{where}: pump voltage " + " / ".join("off (0)" if x == 0 else f"{x}" for x in allowed)
                             + " V (own pump limits change the list)")
        if t <= last_t:
            raise ValueError(f"{where}: pump step temperatures must rise")
        if v < last_v:
            raise ValueError(f"{where}: pump voltage must not fall with the temperature")
        if v == 0 and out_p:
            raise ValueError(f"{where}: the pump can be off only below its first running step")
        out_p.append([t, v])
        last_t, last_v = t, v
    return {"fan": out_f, "pump": out_p}


def check_curves(curves, base=None, running=None):
    """Merge a partial {key: set | None} into base (validated). "common" cannot be None."""
    out = full(base)
    if not isinstance(curves, dict):
        raise ValueError("curves: an object expected")
    for k, v in curves.items():
        if k not in CURVE_KEYS:
            raise ValueError(f"curves: unknown key {k} ({', '.join(CURVE_KEYS)})")
        if v is None:
            if k == "common":
                raise ValueError("the common curve cannot be removed")
            out[k] = None
        else:
            out[k] = check_set(v, k, running)
    return out


def fan_at(curve, t):
    pts = curve["fan"]
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
        if t <= t1:
            return round(d0 + (d1 - d0) * (t - t0) / (t1 - t0))
    return pts[-1][1]


def pump_index(curve, t):
    """Index of the pump step for temperature t (0 below the first step)."""
    i = 0
    for k, (t0, _v) in enumerate(curve["pump"]):
        if t >= t0:
            i = k
    return i


def is_flat(curve):
    return len({d for _t, d in curve["fan"]}) == 1 and len({v for _t, v in curve["pump"]}) == 1


def for_mode(curves, laptop_mode):
    """(key, set) used in "Follow the laptop" for the laptop's operating mode."""
    key = LAPTOP_MODE_KEY.get(laptop_mode)
    c = full(curves)
    if key and c.get(key):
        return key, c[key]
    return "common", c["common"]


def from_tiers(tiers):
    """Tiers of 1.6.7 and older -> a curve set that behaves the same (steps become 1 °C ramps)."""
    fan, pump, start = [], [], 0
    for i, tr in enumerate(tiers):
        below = min(int(tr["below"]), 101)
        f = int(tr["fan"])
        p = int(tr["pump"]) or 7                 # "off" is not on a curve (pump idle stops it)
        p = 11 if p == 12 else p                 # 12 V is not on a curve
        lo = max(start, 20)
        hi = min(below - 1, 100)
        if hi < lo:
            continue
        if not fan or fan[-1][0] < lo:
            fan.append([lo, f])
        if hi > lo:
            fan.append([hi, f])
        if not pump or pump[-1][1] != p:
            pump.append([lo, p])
        start = below
    fan = fan[:MAX_FAN_POINTS]
    for k in range(1, len(fan)):                 # the duty may not fall on a curve
        fan[k][1] = max(fan[k][1], fan[k - 1][1])
    for k in range(1, len(pump)):
        pump[k][1] = max(pump[k][1], pump[k - 1][1], key=PUMP_LEVELS.index)
    pump = [p for k, p in enumerate(pump) if k == 0 or p[1] != pump[k - 1][1]][:MAX_PUMP_STEPS]
    if len(fan) < 2:
        fan = [[20, fan[0][1] if fan else 50], [100, fan[0][1] if fan else 50]]
    return check_set({"fan": fan, "pump": pump or [[0, 8]]}, "tiers")


def migrate(cfg, default_tiers, stored=True):
    """liquid.json of 1.6.7 or older (stored): tiers -> common curve; the old "Follow the laptop" duties -> flat
    per-mode curves, so nothing changes after the update. A new install (no liquid.json) starts with the Balanced
    profile and no per-mode curves."""
    if cfg.get("curves"):
        cfg["curves"] = full(cfg["curves"])
        return False
    tiers = cfg.get("tiers")
    if not stored or not tiers:
        common = copy.deepcopy(BUILTIN_PROFILES[DEFAULT_PROFILE]["curves"]["common"])
        cfg["profile"] = DEFAULT_PROFILE
    else:
        try:
            common = from_tiers(tiers)
        except (ValueError, KeyError, TypeError):
            common = copy.deepcopy(BUILTIN_PROFILES[DEFAULT_PROFILE]["curves"]["common"])
        cfg["profile"] = None
    curves = {"common": common}
    if stored:
        for k, f in OLD_LAPTOP_FAN.items():
            curves[k] = flat(f, 11)
        cfg["profile"] = None
    cfg["curves"] = full(curves)
    return True


# -- named cooler profiles -------------------------------------------------------------------------------
ID_RE = re.compile(r"[^a-z0-9]+")


def profiles(cfg):
    """Built-in and user profiles, built-in first."""
    out = [{"id": k, "name": v["name"], "builtin": True, "curves": full(v["curves"])} for k, v in BUILTIN_PROFILES.items()]
    out += [{"id": p["id"], "name": p["name"], "builtin": False, "curves": full(p["curves"])}
            for p in cfg.get("profiles") or []]
    return out


def find(cfg, pid):
    for p in profiles(cfg):
        if p["id"] == pid:
            return p
    raise KeyError(f"cooler profile {pid}")


def modified(cfg):
    pid = cfg.get("profile")
    if not pid:
        return True
    try:
        return find(cfg, pid)["curves"] != full(cfg.get("curves"))
    except KeyError:
        return True


def profile_action(cfg, b):
    """apply / save / copy / remove / rename -> changes cfg in place, returns the profile id concerned."""
    a = str(b.get("action", ""))
    user = cfg.setdefault("profiles", [])
    if a == "apply":
        p = find(cfg, str(b["id"]))
        cfg["curves"] = copy.deepcopy(p["curves"])
        cfg["profile"] = p["id"]
        return p["id"]
    if a == "copy":
        name = str(b.get("name") or "").strip()[:40]
        if not name:
            raise ValueError("a name is needed")
        if len(user) >= 20:
            raise ValueError("at most 20 own cooler profiles")
        base = ID_RE.sub("-", name.lower()).strip("-") or "profile"
        pid, n = base, 2
        ids = {p["id"] for p in profiles(cfg)}
        while pid in ids:
            pid, n = f"{base}-{n}", n + 1
        user.append({"id": pid, "name": name, "curves": full(cfg.get("curves"))})
        cfg["profile"] = pid
        return pid
    pid = str(b.get("id", ""))
    if pid in BUILTIN_PROFILES:
        raise ValueError("a built-in profile cannot be changed — copy it")
    p = next((x for x in user if x["id"] == pid), None)
    if p is None:
        raise KeyError(f"cooler profile {pid}")
    if a == "save":
        p["curves"] = full(cfg.get("curves"))
        cfg["profile"] = pid
    elif a == "remove":
        user.remove(p)
        if cfg.get("profile") == pid:
            cfg["profile"] = None
    elif a == "rename":
        name = str(b.get("name") or "").strip()[:40]
        if not name:
            raise ValueError("a name is needed")
        p["name"] = name
    else:
        raise KeyError(f"action {a}")
    return pid
