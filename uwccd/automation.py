"""Service-side automation that goes beyond the OEM program (ideas from Control Center X V5 / OpenRevo):

  * Sampler      — one monitor snapshot every 2 s shared by all UI clients, plus the sensor history
                   (temperatures, load, CPU package / GPU power, fans, liquid cooler) in three resolutions:
                   every 2 s for 15 min, every 5 s for an hour, per-minute averages for 24 h (kept on disk);
  * overheat     — notify when the CPU or GPU stays at/above a limit for 30 s (at most once in 10 min),
                   optionally switch Fan Boost on if it is still hot 30 s after the notice;
  * power source — switch the operating mode when the charger is plugged in / unplugged, turn the keyboard
                   backlight off on battery, follow the mode with power-profiles-daemon.
"""
import collections
import csv
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time

from . import lc_curves as LCV

log = logging.getLogger("uwccd.auto")

HOLD = 30            # s above the limit before a notice
REPEAT = 600         # s between two notices for the same sensor
HISTORY_STEP = 5     # s
HISTORY_LEN = 720    # one hour
FINE_LEN = 450       # 15 min of 2 s samples
DAY_STEP = 60        # s, one averaged point per minute
DAY_LEN = 1440       # 24 h
DAY_SAVE = 600       # s between writes of the 24 h history to disk
LAST_KEYS = ("pl1", "pl2", "pl4", "gpl")      # limits: the last value of the minute, not an average
DEFAULT_MAX_KB = 2048  # size limit of the 24 h history file (EC Manager → Monitoring)
RANGES = {60: "fine", 300: "fine", 900: "fine", 3600: "history", 86400: "day"}

DEFAULTS = {
    "alerts": True, "cpu_alert": 95, "gpu_alert": 87, "overheat_boost": False,
    "mode_on_ac": "keep", "mode_on_battery": "keep", "kb_off_on_battery": False, "ppd_sync": False,
    # the other way round: the system power profile (Windows power mode / power-profiles-daemon) -> the laptop's mode
    "ppd_follow": False, "ppd_modes": {"power-saver": 0, "balanced": "keep", "performance": 2},
}
SYS_PROFILES = ("power-saver", "balanced", "performance")


def setting(st, key):
    v = st.get(key)
    return DEFAULTS[key] if v is None else v


class Sampler(threading.Thread):
    def __init__(self, svc):
        super().__init__(daemon=True, name="sampler")
        self.svc = svc
        self.stop = threading.Event()
        self.latest = None
        self.history = collections.deque(maxlen=HISTORY_LEN)
        self.fine = collections.deque(maxlen=FINE_LEN)
        self.day = collections.deque(maxlen=DAY_LEN)
        self._minute = []                    # fine points of the current minute
        self._last_hist = 0.0
        self._last_save = time.time()
        self._load_day()
        self.hot = {"cpu": {"since": None, "notified": 0.0, "boosted": False},
                    "gpu": {"since": None, "notified": 0.0, "boosted": False}}
        self.lock = threading.Lock()
        self._wake = threading.Event()

    def snapshot(self):
        with self.lock:
            lvl = self.level()
            if lvl != "full":
                return self.latest if (self.latest or {}).get("monitoring") == lvl else {"t": time.time(), "monitoring": lvl}
            if self.latest is None or self.latest.get("monitoring") != "full":
                self._sample()
            return self.latest

    def level(self):
        try:
            return self.svc.monitor_level()
        except Exception:  # noqa: BLE001
            return "full"

    def _sample(self):
        m = self.svc.monitor.snapshot()
        m["cpu"]["power_w"] = self.svc.monitor.rapl.watts()
        m["monitoring"] = "full"
        self.latest = m

    def _sample_light(self):
        """Monitoring off for this EC path: only the temperatures (no EC access) for the cooler and the alerts."""
        mon = self.svc.monitor
        gpu = None
        if self.svc.pf.nv_gpu:
            nv = mon.nvidia() or {}
            gpu = {"temp": nv.get("temp")} if nv else None
        self.latest = {"t": time.time(), "monitoring": "light", "cpu": {"temp": mon.cpu_temp()}, "gpu": gpu}

    interval = 2.0                           # WMI EC path: slower (ec_wmi.json poll.monitor_s)
    LIGHT_S = 20.0                           # monitoring off for the EC path: temperatures only, this often

    def wake(self):
        self._wake.set()

    def run(self):
        self._wake = getattr(self, "_wake", None) or threading.Event()
        wait = self.current_interval()
        while not self.stop.is_set():
            self._wake.wait(wait)
            self._wake.clear()
            if self.stop.is_set():
                break
            try:
                lvl = self.level()
                if lvl == "off":
                    with self.lock:
                        self.latest = {"t": time.time(), "monitoring": "off"}
                    wait = 5.0
                    continue
                with self.lock:
                    if lvl == "light":
                        self._sample_light()
                    else:
                        self._sample()
                m = self.latest
                wait = self.LIGHT_S if lvl == "light" else self.current_interval()
                if lvl == "full" and self.recording():
                    self._record(m)
                self._overheat(m)
                if lvl == "full" and getattr(self.svc, "load_rules", None):
                    self.svc.load_rules.tick(m)
            except Exception:  # noqa: BLE001
                log.exception("sampler")

    # -- history ---------------------------------------------------------------------------------
    def recording(self):
        return bool(self.svc.settings_store.get("history_record", True))

    def _record(self, m):
        now = time.time()
        p = self._point(m)
        self.fine.append(p)
        if now - self._last_hist >= HISTORY_STEP:
            self._last_hist = now
            self.history.append(p)
        if self._minute and int(p["t"]) // DAY_STEP != int(self._minute[0]["t"]) // DAY_STEP:
            self.day.append(average(self._minute))
            self._minute = []
        self._minute.append(p)
        if now - self._last_save >= DAY_SAVE:
            self.save_day()

    def points(self, seconds=3600):
        """History for the last `seconds` (60 / 300 / 900 -> 2 s, 3600 -> 5 s, 86400 -> 1 min averages)."""
        buf = getattr(self, RANGES.get(seconds) or ("day" if seconds > 3600 else "history"))
        t0 = time.time() - seconds
        return [p for p in list(buf) if p["t"] >= t0]

    def history_dir(self):
        """Folder of the 24 h history (EC Manager → Monitoring; changing it needs administrator rights)."""
        from . import store
        d = self.svc.settings_store.get("history_dir")
        return d if d and os.path.isabs(d) else store.DATA_DIR

    def _day_path(self):
        return os.path.join(self.history_dir(), "history-24h.json")

    def max_bytes(self):
        kb = self.svc.settings_store.get("history_max_kb")
        return int(kb if kb is not None else DEFAULT_MAX_KB) * 1024

    def current_interval(self):
        """Seconds between two samples: the setting monitor_interval, or automatic (2 s, WMI path 5 s)."""
        v = self.svc.settings_store.get("monitor_interval") or 0
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0
        return v if 1 <= v <= 60 else self.interval

    def clear(self):
        """Forget the whole history (memory and file)."""
        with self.lock:
            self.fine.clear()
            self.history.clear()
            self.day.clear()
            self._minute = []
        try:
            os.remove(self._day_path())
        except OSError:
            pass
        log.info("history cleared")

    def info(self):
        p = self._day_path()
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0
        return {"path": p, "dir": self.history_dir(), "size": size, "points": {"fine": len(self.fine),
                "hour": len(self.history), "day": len(self.day)}, "max_kb": self.max_bytes() // 1024,
                "interval": self.current_interval(), "interval_setting": self.svc.settings_store.get("monitor_interval") or 0,
                "interval_auto": self.interval, "recording": self.recording()}

    def move_to(self, d):
        """Store the 24 h history in another folder (the file moves there)."""
        from . import store
        d = os.path.normpath(d) if d else store.DATA_DIR
        if not os.path.isabs(d):
            raise ValueError("an absolute folder is required")
        os.makedirs(d, exist_ok=True)
        old = self._day_path()
        self.svc.settings_store.set("history_dir", None if d == os.path.normpath(store.DATA_DIR) else d)
        new = self._day_path()
        if old != new:
            self.save_day()
            try:
                os.remove(old)
            except OSError:
                pass
        log.warning("history folder: %s", d)
        return self.info()

    def _load_day(self):
        from . import store
        try:
            data = store.load_json(self._day_path(), [])
        except Exception:  # noqa: BLE001  (settings store not ready in odd test set-ups)
            data = []
        t0 = time.time() - DAY_LEN * DAY_STEP
        if isinstance(data, list):
            self.day.extend(p for p in data if isinstance(p, dict) and isinstance(p.get("t"), (int, float)) and p["t"] >= t0)

    def save_day(self):
        """Write the 24 h history compactly; the oldest minutes go first when it is larger than the size limit."""
        self._last_save = time.time()
        pts = list(self.day)
        limit = self.max_bytes()
        data = json.dumps(pts, separators=(",", ":"))
        if limit > 0 and len(data) > limit and pts:
            per = len(data) / len(pts)
            keep = max(0, int(limit / per) - 1)
            pts = pts[-keep:] if keep else []
            with self.lock:
                while len(self.day) > len(pts):
                    self.day.popleft()
            data = json.dumps(pts, separators=(",", ":"))
        p = self._day_path()
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, p)
        except OSError as e:
            log.warning("cannot save the 24 h history: %s", e)

    def _limits(self):
        """Current CPU power limits for the chart marks: what the service wrote to the EC (0x783/84/85);
        0 there means "the controller's own limits" — then the factory values of the current mode."""
        ec = self.svc.ec
        try:
            pl = [ec.read(a) for a in (0x783, 0x784, 0x785)]
            if not any(pl):
                mode = self.svc.power.option.get("OperatingMode")
                base = {0: 0x734, 1: 0x730, 2: 0x7A7}.get(self._mode_index(mode))
                if base is not None:
                    pl = [ec.read(base + i) for i in range(3)]
        except Exception:  # noqa: BLE001
            return None, None, None
        if getattr(self.svc.power, "manager", "cml") != "std":
            pl[2] = 0                          # PL4 is managed only on RamFan1p5 (Custom mode) platforms
        return tuple(v if v else None for v in pl)

    @staticmethod
    def _mode_index(mode):
        from . import regs as R
        return {R.MODE_OFFICE: 0, R.MODE_GAMING: 1, R.MODE_TURBO: 2}.get(mode)

    def _point(self, m):
        g = m.get("gpu") or {}
        lc = self.svc.liquid.status() if self.svc.liquid.available else {}
        pl1, pl2, pl4 = self._limits()
        cp, gp = m["cpu"].get("power_w"), g.get("power_w")
        bat = m.get("battery") or {}
        return {"t": round(m["t"]), "ct": m["cpu"]["temp"], "cl": m["cpu"]["usage"], "cp": cp,
                "gt": g.get("temp"), "gl": g.get("usage"), "gp": gp,
                "pl1": pl1, "pl2": pl2, "pl4": pl4, "gpl": g.get("power_limit_w"),
                "tp": round((cp or 0) + (gp or 0), 1) if cp is not None or gp is not None else None,
                "bp": bat.get("power_w") if bat.get("status") == "Discharging" else None,
                "cf": m["fans"].get("cpu_rpm"), "gf": m["fans"].get("gpu_rpm"),
                "cm": m["cpu"].get("mhz"), "gm": g.get("core_mhz"),
                "lf": lc.get("fan") if lc.get("connected") else None,
                "lp": lc.get("pump") if lc.get("connected") else None}

    def _overheat(self, m):
        st = self.svc.settings_store
        if not setting(st, "alerts"):
            return
        now = time.time()
        temps = {"cpu": (m["cpu"]["temp"], int(setting(st, "cpu_alert"))),
                 "gpu": ((m.get("gpu") or {}).get("temp"), int(setting(st, "gpu_alert")))}
        for sensor, (t, limit) in temps.items():
            h = self.hot[sensor]
            if not isinstance(t, (int, float)) or t < limit:
                h["since"] = None
                h["boosted"] = False
                continue
            if h["since"] is None:
                h["since"] = now
                continue
            boost = bool(setting(st, "overheat_boost")) and self.svc.fan_control
            if now - h["since"] >= HOLD and now - h["notified"] >= REPEAT:
                h["notified"] = now
                log.warning("%s at %s °C for %d s (limit %d)", sensor.upper(), t, HOLD, limit)
                self.svc.emit("overheat", {"sensor": sensor, "temp": t, "limit": limit, "boost": boost})
            elif (boost and not h["boosted"] and h["notified"] and now - h["notified"] >= HOLD
                  and not self.svc.power.option.get("FanBoostEnable")):
                h["boosted"] = True
                log.warning("still overheating — Fan Boost on")
                self.svc.power.set_fan_boost(True)
                self.svc.emit("overheat_boost", {"sensor": sensor, "temp": t})


def average(points):
    """One per-minute point of the 24 h history: averages of the sensors, the last value of the limits."""
    out = {"t": points[-1]["t"], "n": len(points)}
    for k in points[-1]:
        if k in ("t", "n"):
            continue
        vals = [p[k] for p in points if isinstance(p.get(k), (int, float))]
        if k in LAST_KEYS:
            out[k] = points[-1].get(k)
        elif vals:
            out[k] = round(sum(vals) / len(vals), 1)
            if k in ("ct", "gt", "cp", "gp", "tp"):
                out[k + "_mx"] = max(vals)          # peaks of the minute
        else:
            out[k] = None
    return out


EXPORT_COLUMNS = [("t", "time"), ("ct", "cpu_temp_c"), ("gt", "gpu_temp_c"), ("cl", "cpu_load_pct"),
                  ("gl", "gpu_load_pct"), ("cp", "cpu_power_w"), ("gp", "gpu_power_w"), ("tp", "cpu_gpu_power_w"),
                  ("bp", "battery_discharge_w"), ("pl1", "cpu_pl1_w"), ("pl2", "cpu_pl2_w"), ("pl4", "cpu_pl4_w"),
                  ("gpl", "gpu_power_limit_w"), ("cm", "cpu_clock_mhz"), ("gm", "gpu_clock_mhz"), ("cf", "cpu_fan_rpm"),
                  ("gf", "gpu_fan_rpm"), ("lf", "cooler_fan_pct"), ("lp", "cooler_pump_v")]


def export_history(points, fmt="csv"):
    """History samples as CSV (UTF-8 with BOM, ISO local time) or JSON. Returns (bytes, mime, ext)."""
    rows = []
    for p in points:
        r = {}
        for k, name in EXPORT_COLUMNS:
            v = p.get(k)
            r[name] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(v)) if k == "t" and v else v
        rows.append(r)
    if fmt == "json":
        return json.dumps(rows, ensure_ascii=False, indent=1).encode(), "application/json", "json"
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";" if fmt == "csv-excel" else ",", lineterminator="\r\n")
    w.writerow([name for _, name in EXPORT_COLUMNS])
    for r in rows:
        line = []
        for _, name in EXPORT_COLUMNS:
            v = r[name]
            if v is None:
                v = ""
            elif fmt == "csv-excel" and isinstance(v, float):
                v = str(v).replace(".", ",")          # Excel with a comma decimal separator (ru, de, ...)
            line.append(v)
        w.writerow(line)
    return ("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv", "csv"


class PowerSourceRules:
    """Mode / keyboard backlight / power-profiles-daemon on AC <-> battery changes."""

    PPD = {0: "balanced", 1: "balanced", 2: "performance", 3: "balanced"}

    def __init__(self, svc):
        self.svc = svc
        self.mode_before_battery = None
        self.kb_was_on = None

    def on_ac_change(self, online):
        svc, st = self.svc, self.svc.settings_store
        binding_active = any(getattr(t, "active", None) for t in svc.threads if t.name == "appbind")
        rule_active = getattr(getattr(svc, "load_rules", None), "active", None) is not None   # load rules come first
        if svc.fan_control and not binding_active and not rule_active:
            cur = svc.power.option["OperatingMode"]
            want = setting(st, "mode_on_ac" if online else "mode_on_battery")
            target = None
            if online and want == "previous":
                target = self.mode_before_battery
            elif want not in ("keep", "previous", None):
                target = int(want)
            if not online:
                self.mode_before_battery = cur
            if target is not None and target != cur and target in svc.power.MODES:
                if target != 2 or svc.pf.turbo_support:
                    log.info("power source %s -> mode %s", "AC" if online else "battery", target)
                    svc.power.user_set_mode(target, osd=True)
        if setting(st, "kb_off_on_battery") and svc.keyboard.kind != "none":
            if not online:
                self.kb_was_on = bool(st.get("kb_power", True))
                if self.kb_was_on:
                    svc.keyboard.set_power(False)
            elif self.kb_was_on:
                svc.keyboard.set_power(True)
                self.kb_was_on = None
        self.sync_ppd()

    def follow_system(self, prof):
        """The system power profile changed (not by us): the laptop's mode from "ppd_modes"."""
        svc, st = self.svc, self.svc.settings_store
        if not setting(st, "ppd_follow") or not svc.fan_control:
            return
        binding_active = any(getattr(t, "active", None) for t in svc.threads if t.name == "appbind")
        rule_active = getattr(getattr(svc, "load_rules", None), "active", None) is not None
        if binding_active or rule_active:                # App binding and the rules come first
            return
        want = (setting(st, "ppd_modes") or {}).get(prof, "keep")
        if want in ("keep", None):
            return
        mode = int(want)
        if mode not in svc.power.MODES or (mode == 2 and not svc.pf.turbo_support):
            return
        if svc.power.option["OperatingMode"] != mode:
            log.info("system power profile %s -> mode %s", prof, mode)
            svc.power.user_set_mode(mode, osd=True)

    def sync_ppd(self, mode=None):
        """Follow the operating mode with power-profiles-daemon (on battery: power-saver)."""
        st = self.svc.settings_store
        if not setting(st, "ppd_sync"):
            return
        if mode is None:
            mode = self.svc.power.option["OperatingMode"]
        prof = self.PPD.get(mode, "balanced") if self.svc.power.ac_online else "power-saver"
        sp = getattr(self.svc, "sysprof", None)
        if sp is not None and setting(st, "ppd_follow") and sp.profile:
            want = (setting(st, "ppd_modes") or {}).get(sp.profile, "keep")
            if want not in ("keep", None) and int(want) == mode:
                return                                   # the mode came from this profile: leave the profile
        if sp is not None:
            sp.note_set(prof)
        if sys.platform == "win32":                 # Windows power mode slider (overlay scheme)
            from .win.winapi import set_power_overlay
            try:
                set_power_overlay(prof)
            except OSError as e:
                log.debug("power overlay: %s", e)
            return
        if not shutil.which("powerprofilesctl"):
            return
        try:
            r = subprocess.run(["powerprofilesctl", "set", prof], capture_output=True, text=True, timeout=5, check=False)
            if r.returncode and prof == "performance":     # not every CPU driver offers it
                subprocess.run(["powerprofilesctl", "set", "balanced"], capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError) as e:
            log.debug("powerprofilesctl: %s", e)


# -- automatic profile switching by load / power / temperature (1.6.8) ---------------------------------------------
LOAD_METRICS = {                     # key -> (unit, max value)
    "cpu_power": ("W", 500), "gpu_power": ("W", 500), "total_power": ("W", 1000),
    "cpu_temp": ("°C", 110), "gpu_temp": ("°C", 110), "cpu_load": ("%", 100), "gpu_load": ("%", 100),
    "battery": ("%", 100),           # charge level
    "ac": ("", 1),                   # power source: op "=", value 1 = from the mains, 0 = on battery
    "sys_profile": ("", 2),          # system power profile: op "=", 0 power-saver / 1 balanced / 2 performance
    "saver": ("", 1),                # Windows battery saver: op "=", 1 on / 0 off
    "mode": ("", 3),                 # the laptop's mode: op "=" / "!=", 0 office / 1 gaming / 2 turbo / 3 custom
    "lc_profile": ("", 0),           # the liquid cooler profile in use: op "=" / "!=", its id (text)
    "rule": ("", 12),                # another rule is on (its conditions held long enough, or it is active):
}                                    #   op "=" on / "!=" not on, value its number 1..12, 0 = any other rule
EQ_METRICS = ("ac", "sys_profile", "saver")
STATE_METRICS = ("mode", "lc_profile", "rule")
LOAD_LOG_LEN = 100                  # what the rules did: the last 100 events
MAX_RULE_S = 86400                  # hold / return times up to 24 h
TIME_UNITS = ("s", "min", "h")      # how the window shows a time (stored in seconds)
BACK_MODES = ("never", "while", "after")    # never return / while the conditions hold / N after they stop
LC_RULE_MODES = ("auto", "laptop", "ec", "manual", "high", "medium", "low", "off")
MAX_LOAD_RULES = 12


def load_metric(m, key):
    """A value of the monitor snapshot; None when it is not known (the GPU sleeping counts as 0 W / 0 %)."""
    cpu, gpu = m.get("cpu") or {}, m.get("gpu") or {}
    asleep = bool(gpu.get("asleep"))
    if key == "cpu_power":
        return cpu.get("power_w")
    if key == "gpu_power":
        return 0.0 if asleep else gpu.get("power_w")
    if key == "total_power":
        c, g = cpu.get("power_w"), (0.0 if asleep else gpu.get("power_w"))
        return None if c is None and g is None else (c or 0) + (g or 0)
    if key == "cpu_temp":
        return cpu.get("temp")
    if key == "gpu_temp":
        return None if asleep else gpu.get("temp")
    if key == "cpu_load":
        return cpu.get("usage")
    if key == "gpu_load":
        return 0 if asleep else gpu.get("usage")
    if key == "battery":
        b = m.get("battery") or {}
        return b.get("percent") if b.get("present", True) else None
    if key == "ac":
        return None if m.get("ac") is None else (1 if m.get("ac") else 0)
    if key == "sys_profile":
        p = m.get("sys_profile")
        return SYS_PROFILES.index(p) if p in SYS_PROFILES else None
    if key == "saver":
        return None if m.get("saver") is None else (1 if m.get("saver") else 0)
    if key in ("mode", "lc_profile"):
        return m.get(key)
    return None


def check_load_rules(rules):
    if not isinstance(rules, list) or len(rules) > MAX_LOAD_RULES:
        raise ValueError(f"at most {MAX_LOAD_RULES} rules")
    out = []
    for i, r in enumerate(rules):
        conds = r.get("conditions") or []
        if not 1 <= len(conds) <= 3:
            raise ValueError(f"rule {i + 1}: 1..3 conditions")
        cc = []
        for c in conds:
            k = str(c.get("metric"))
            if k not in LOAD_METRICS:
                raise ValueError(f"rule {i + 1}: metric {k} ({', '.join(LOAD_METRICS)})")
            op = str(c.get("op", ">"))
            if k in STATE_METRICS:
                if op not in ("=", "!="):
                    raise ValueError(f"rule {i + 1}: {k}: operator = or !=")
                if k == "lc_profile":
                    v = str(c.get("value") or "").strip()[:60]
                    if not v:
                        raise ValueError(f"rule {i + 1}: cooler profile: an id is needed")
                else:
                    v = int(c.get("value"))
                    if not 0 <= v <= LOAD_METRICS[k][1]:
                        raise ValueError(f"rule {i + 1}: {k} 0..{LOAD_METRICS[k][1]}")
                    if k == "rule" and v == i + 1:
                        raise ValueError(f"rule {i + 1}: a rule cannot test itself")
                cc.append({"metric": k, "op": op, "value": v})
                continue
            if k in EQ_METRICS:
                op = "="
            elif op not in (">", "<"):
                raise ValueError(f"rule {i + 1}: operator > or <")
            v = float(c.get("value"))
            if not 0 <= v <= LOAD_METRICS[k][1]:
                raise ValueError(f"rule {i + 1}: {k} 0..{LOAD_METRICS[k][1]} {LOAD_METRICS[k][0]}")
            cc.append({"metric": k, "op": op, "value": round(v, 1)})
        join = str(r.get("join", "and"))
        if join not in ("and", "or"):
            raise ValueError(f"rule {i + 1}: join and / or")
        hold, back_after = int(r.get("hold", 30)), int(r.get("back_after", 60))
        if not 0 <= hold <= MAX_RULE_S or not 0 <= back_after <= MAX_RULE_S:
            raise ValueError(f"rule {i + 1}: times 0..{MAX_RULE_S} s (24 h)")
        back = r.get("back", "never")              # 1.6.8 and older: true / false
        back = "after" if back is True else "never" if back in (False, None) else str(back)
        if back not in BACK_MODES:
            raise ValueError(f"rule {i + 1}: back {' | '.join(BACK_MODES)}")
        units = {}
        for k in ("hold_unit", "back_unit"):
            u = r.get(k) or "s"
            if u not in TIME_UNITS:
                raise ValueError(f"rule {i + 1}: {k} s | min | h")
            units[k] = u
        mode = r.get("mode")
        mode = None if mode in (None, "", "keep") else int(mode)
        if mode is not None and mode not in (0, 1, 2, 3):
            raise ValueError(f"rule {i + 1}: mode 0..3 or keep")
        slot = r.get("slot")
        slot = None if slot in (None, "", "current") else int(slot)
        if slot is not None and not 0 <= slot <= 4:
            raise ValueError(f"rule {i + 1}: profile slot 0..4")
        lcp = r.get("lc_profile")
        lcp = None if lcp in (None, "", "keep") else str(lcp)[:60]
        lcm = r.get("lc_mode")
        lcm = None if lcm in (None, "", "keep") else str(lcm)
        if lcm is not None and lcm not in LC_RULE_MODES:
            raise ValueError(f"rule {i + 1}: cooler mode {' | '.join(LC_RULE_MODES)}")
        fb = r.get("fan_boost", "keep")         # keep | on | off (1.6.11 before this: true = on, false = keep)
        fb = "on" if fb is True else "keep" if fb in (False, None, "") else str(fb)
        if fb not in ("keep", "on", "off"):
            raise ValueError(f"rule {i + 1}: fan_boost keep | on | off")
        if mode is None and lcp is None and lcm is None and fb == "keep":
            raise ValueError(f"rule {i + 1}: nothing to switch (mode, Fan Boost or the liquid cooler)")
        out.append({"enabled": bool(r.get("enabled", True)), "name": str(r.get("name") or "")[:40],
                    "conditions": cc, "join": join, "hold": hold, "mode": mode, "slot": slot if mode is not None else None,
                    "fan_boost": fb, "lc_mode": lcm, "lc_profile": lcp,
                    "back": back, "back_after": back_after, **units})
    return out


class LoadRules:
    """Switch the laptop's mode (and profile slot), Fan Boost and the liquid cooler (mode, profile) when power /
    temperature / load / power source hold past a limit.

    Rules are checked in their order on every monitor sample (full monitoring); the first rule whose conditions held
    for `hold` seconds (0: at once) is applied — once, when it becomes active. While a rule is active, App binding and
    the power source rules do not change the mode ("rules come first"). Return (`back`): "never" — stay; "while" — back
    as soon as the conditions stop; "after" — back when they have been false for `back_after` seconds. Each thing is
    put back only if nobody changed it meanwhile.
    """

    def __init__(self, svc):
        self.svc = svc
        self.since = {}          # rule index -> since when its conditions hold
        self.false_since = None
        self.active = None       # index of the active rule
        self.saved = None        # the state before the first rule became active (what a return puts back)
        self.did = {}            # what the active rule(s) set
        self.log = collections.deque(maxlen=LOAD_LOG_LEN)    # what the rules did, newest last
        self.lock = threading.Lock()

    # kept for 1.6.8 callers / tests
    @property
    def prev(self):
        return (self.saved or {}).get("mode")

    def _note(self, what, r, now=None, **kw):
        self.log.append({"t": round(now or time.time()), "what": what, "rule": r.get("name") or "",
                         "mode": kw.get("mode"), "slot": kw.get("slot"), "lc_profile": kw.get("lc_profile"),
                         "lc_mode": kw.get("lc_mode"), "fan_boost": kw.get("fan_boost")})

    def clear_log(self):
        with self.lock:
            self.log.clear()

    def rules(self):
        return self.svc.settings_store.get("load_rules", []) or []

    @staticmethod
    def holds(rule, m, i=None, on=frozenset()):
        """i: the rule's own index; on: the rules that are on (conditions held long enough, or active)."""
        res = []
        for c in rule["conditions"]:
            op = c["op"]
            if c["metric"] == "rule":
                n = int(c["value"])
                is_on = any(j != i for j in on) if n == 0 else (n - 1) in on
                res.append(is_on if op == "=" else not is_on)
                continue
            v = load_metric(m, c["metric"])
            if op == "!=":
                res.append(v is not None and v != c["value"])
            else:
                res.append(v is not None and (v == c["value"] if op == "=" else v > c["value"] if op == ">" else v < c["value"]))
        return all(res) if rule.get("join", "and") == "and" else any(res)

    def _state(self, m):
        """The laptop's mode and the cooler profile, for the conditions on them."""
        out = dict(m)
        try:
            out["mode"] = self.svc.power.option.get("OperatingMode")
        except Exception:  # noqa: BLE001
            out["mode"] = None
        lc = self._lc()
        out["lc_profile"] = lc.cfg.get("profile") if lc is not None else None
        return out

    # -- what a rule can change ----------------------------------------------------------------------
    def _current(self):
        p = self.svc.power
        mode = p.option.get("OperatingMode")
        try:
            slot = (p.status().get("profile_index") or {}).get({0: "office", 1: "gaming", 2: "turbo", 3: "custom"}.get(mode))
        except Exception:  # noqa: BLE001
            slot = None
        return mode, slot

    def _lc(self):
        lc = getattr(self.svc, "liquid", None)
        return lc if lc is not None and getattr(lc, "cfg", None) is not None else None

    def _snapshot(self):
        lc = self._lc()
        snap = {"mode": self._current(), "fan_boost": bool(self.svc.power.option.get("FanBoostEnable"))}
        if lc is not None:
            snap["lc_mode"] = lc.cfg.get("mode")
            if hasattr(lc, "curves_snapshot"):
                snap["lc_curves"] = lc.curves_snapshot()
        return snap

    def _apply(self, mode, slot, why):
        p = self.svc.power
        if mode is None:
            return True
        if mode == 2 and not self.svc.pf.turbo_support or mode not in p.MODES:
            log.warning("load rule: mode %s is not available here", mode)
            return False
        cur = self._current()
        if cur == (mode, slot) or (slot is None and cur[0] == mode):
            return True
        log.info("load rule: %s -> mode %s%s", why, mode, f" slot {slot}" if slot is not None else "")
        if slot is not None:
            p.set_profile_index(mode, slot)
        else:
            p.user_set_mode(mode, osd=True)
        self.svc.emit("load_rule", {"rule": why, "mode": mode, "slot": slot})
        return True

    def _fan_boost(self, on):
        p = self.svc.power
        if bool(p.option.get("FanBoostEnable")) != on:
            log.info("load rule: Fan Boost %s", "on" if on else "off")
            p.set_fan_boost(on)

    def _apply_lc(self, r):
        """The liquid cooler's mode and / or profile with the rule; returns what was set."""
        lc, out = self._lc(), {}
        if lc is None:
            return out
        try:
            pid = r.get("lc_profile")
            if pid and not (lc.cfg.get("profile") == pid and not LCV.modified(lc.cfg)):
                lc.profile({"action": "apply", "id": pid})
                log.info("load rule: cooler profile %s", pid)
            if pid:
                out["lc_profile"] = pid
            m = r.get("lc_mode")
            if m and lc.cfg.get("mode") != m:
                lc.configure({"mode": m})
                log.info("load rule: cooler mode %s", m)
            if m:
                out["lc_mode"] = m
        except (KeyError, ValueError) as e:
            log.warning("load rule: liquid cooler: %s", e)
        return out

    def _activate(self, i, r, now):
        if self.active is None:
            self.saved = self._snapshot()
            self.did = {}
        if not self._apply(r.get("mode"), r.get("slot"), r.get("name") or f"rule {i + 1}"):
            return
        did = {}
        if r.get("mode") is not None:
            did["mode"] = (r["mode"], r.get("slot"))
        fb = r.get("fan_boost")
        fb = "on" if fb is True else fb
        if fb in ("on", "off"):
            self._fan_boost(fb == "on")
            did["fan_boost"] = fb == "on"
        did.update(self._apply_lc(r))
        self.did.update(did)
        self.active, self.false_since = i, None
        self._note("on", r, now, mode=r.get("mode"), slot=r.get("slot"), lc_profile=did.get("lc_profile"),
                   lc_mode=did.get("lc_mode"), fan_boost=did.get("fan_boost"))

    def _return(self, r, now):
        """Put back what the rules changed — each part only if it is still what the rule set."""
        sv, did, lc = self.saved or {}, self.did, self._lc()
        back = {}
        cur = self._current()
        if "mode" in did and sv.get("mode") and cur[0] == did["mode"][0]:
            log.info("load rule %s over: back to mode %s", r.get("name") or "", sv["mode"][0])
            self._apply(sv["mode"][0], sv["mode"][1], "back")
            back["mode"], back["slot"] = sv["mode"]
        if "fan_boost" in did and did["fan_boost"] != sv.get("fan_boost") \
                and bool(self.svc.power.option.get("FanBoostEnable")) == did["fan_boost"]:
            self._fan_boost(bool(sv.get("fan_boost")))
            back["fan_boost"] = bool(sv.get("fan_boost"))
        if lc is not None:
            try:
                if did.get("lc_profile") and sv.get("lc_curves") and lc.cfg.get("profile") == did["lc_profile"] \
                        and not LCV.modified(lc.cfg):
                    lc.curves_restore(sv["lc_curves"])
                    back["lc_profile"] = did["lc_profile"]
                if did.get("lc_mode") and sv.get("lc_mode") and lc.cfg.get("mode") == did["lc_mode"]:
                    lc.configure({"mode": sv["lc_mode"]})
                    back["lc_mode"] = sv["lc_mode"]
            except (KeyError, ValueError) as e:
                log.warning("load rule: liquid cooler back: %s", e)
        self._note("back" if back else "end", r, now, **back)
        self.active, self.saved, self.did = None, None, {}

    def tick(self, m, now=None):
        if not self.svc.fan_control or not m or m.get("monitoring", "full") != "full":
            return
        sp = getattr(self.svc, "sysprof", None)
        if sp is not None:
            m = {**m, "sys_profile": sp.profile, "saver": sp.saver}
        now = time.time() if now is None else now
        rules = self.rules()
        m = self._state(m)
        with self.lock:
            on = {j for j, t in self.since.items() if j < len(rules) and now - t >= rules[j].get("hold", 0)}
            if self.active is not None:
                on.add(self.active)
            hit = None
            for i, r in enumerate(rules):
                if not r.get("enabled", True):
                    self.since.pop(i, None)
                    continue
                if self.holds(r, m, i, on):
                    self.since.setdefault(i, now)
                    if hit is None and now - self.since[i] >= r.get("hold", 0):
                        hit = i
                else:
                    self.since.pop(i, None)
            try:
                if hit is not None and hit != self.active:
                    self._activate(hit, rules[hit], now)
                elif self.active is not None and self.active < len(rules):
                    r = rules[self.active]
                    if self.active in self.since:
                        self.false_since = None
                    else:
                        self.false_since = self.false_since or now
                        back = r.get("back", "never")
                        back = "after" if back is True else "never" if back is False else back
                        if back == "never":
                            self._note("end", r, now)
                            self.active, self.saved, self.did = None, None, {}
                        elif back == "while" or now - self.false_since >= r.get("back_after", 0):
                            self._return(r, now)
                elif self.active is not None:            # the rule was removed
                    self.active, self.saved, self.did = None, None, {}
            except Exception:  # noqa: BLE001
                log.exception("load rules")

    def status(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            return {"rules": self.rules(), "active": self.active, "metrics": {k: v[0] for k, v in LOAD_METRICS.items()},
                    "log": list(reversed(self.log)),
                    "held": {str(i): round(now - t) for i, t in self.since.items()},
                    "back_in": (round(self.rules()[self.active]["back_after"] - (now - self.false_since))
                                if self.active is not None and self.false_since and self.active < len(self.rules())
                                and self.rules()[self.active].get("back") in ("after", True) else None),
                    "lc_modes": list(LC_RULE_MODES)}
