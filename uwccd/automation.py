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
import shutil
import subprocess
import sys
import threading
import time

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
RANGES = {60: "fine", 300: "fine", 900: "fine", 3600: "history", 86400: "day"}

DEFAULTS = {
    "alerts": True, "cpu_alert": 95, "gpu_alert": 87, "overheat_boost": False,
    "mode_on_ac": "keep", "mode_on_battery": "keep", "kb_off_on_battery": False, "ppd_sync": False,
}


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

    def snapshot(self):
        with self.lock:
            if self.latest is None:
                self._sample()
            return self.latest

    def _sample(self):
        m = self.svc.monitor.snapshot()
        m["cpu"]["power_w"] = self.svc.monitor.rapl.watts()
        self.latest = m

    def run(self):
        while not self.stop.wait(2):
            try:
                with self.lock:
                    self._sample()
                m = self.latest
                if self.recording():
                    self._record(m)
                self._overheat(m)
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

    def _day_path(self):
        from . import store
        return store.path("history-24h.json")

    def _load_day(self):
        from . import store
        data = store.load_json(self._day_path(), [])
        t0 = time.time() - DAY_LEN * DAY_STEP
        if isinstance(data, list):
            self.day.extend(p for p in data if isinstance(p, dict) and isinstance(p.get("t"), (int, float)) and p["t"] >= t0)

    def save_day(self):
        from . import store
        self._last_save = time.time()
        try:
            store.save_json(self._day_path(), list(self.day))
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
        if svc.fan_control and not binding_active:
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

    def sync_ppd(self, mode=None):
        """Follow the operating mode with power-profiles-daemon (on battery: power-saver)."""
        if not setting(self.svc.settings_store, "ppd_sync"):
            return
        if mode is None:
            mode = self.svc.power.option["OperatingMode"]
        prof = self.PPD.get(mode, "balanced") if self.svc.power.ac_online else "power-saver"
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
