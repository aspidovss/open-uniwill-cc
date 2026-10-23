"""Service-side automation that goes beyond the OEM program (ideas from Control Center X V5 / OpenRevo):

  * Sampler      — one monitor snapshot every 2 s shared by all UI clients, plus a one-hour history
                   (every 5 s) of temperatures, load, CPU package / GPU power, fans and the liquid cooler;
  * overheat     — notify when the CPU or GPU stays at/above a limit for 30 s (at most once in 10 min),
                   optionally switch Fan Boost on if it is still hot 30 s after the notice;
  * power source — switch the operating mode when the charger is plugged in / unplugged, turn the keyboard
                   backlight off on battery, follow the mode with power-profiles-daemon.
"""
import collections
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
        self._last_hist = 0.0
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
                now = time.time()
                if now - self._last_hist >= HISTORY_STEP:
                    self._last_hist = now
                    self.history.append(self._point(m))
                self._overheat(m)
            except Exception:  # noqa: BLE001
                log.exception("sampler")

    def _point(self, m):
        g = m.get("gpu") or {}
        lc = self.svc.liquid.status() if self.svc.liquid.available else {}
        return {"t": round(m["t"]), "ct": m["cpu"]["temp"], "cl": m["cpu"]["usage"], "cp": m["cpu"].get("power_w"),
                "gt": g.get("temp"), "gl": g.get("usage"), "gp": g.get("power_w"),
                "cf": m["fans"].get("cpu_rpm"), "gf": m["fans"].get("gpu_rpm"),
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
