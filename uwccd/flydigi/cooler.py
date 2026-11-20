"""The Flydigi BS cooler in the service: connection, modes, the temperature curve, status (1.8.2.7).

Connection order is THRM's (internal/device/device.go connect): BS2 / BS2 Pro / BS3 / BS3 Pro by HID (paired in the
system's Bluetooth settings, or by USB), then BS1 by USB HID, then BS1 by a Bluetooth LE scan. One difference: the
Bluetooth LE scan for a BS1 runs only when asked for (Search BS1) or for a BS1 found before — THRM's background
scan every 15 minutes would scan on every laptop that has no BS1 at all.

Modes:
  curve  — realtime RPM from the temperature curve (THRM's default curve, hysteresis 2 °C, min change 50 RPM,
           ramp +220 / -160 RPM per step — THRM's SmartControl defaults; its learning offsets are not ported);
  rpm    — a fixed realtime RPM;
  gear   — a gear 1..4 with THRM's low / mid / high RPM presets (0x26, or 0x08 when the slot already has it);
  stop   — 0 RPM (the realtime session stays, so the next target wakes the fan through THRM's start path);
  device — the program sends nothing: the cooler's own buttons rule.
"""
import copy
import logging
import os
import threading
import time

from .. import store
from . import device as D, hidio, proto as P

log = logging.getLogger("uwccd.flydigi")

MODES = ("curve", "rpm", "gear", "stop", "device")
TEMP_SOURCES = ("max", "cpu", "gpu")
SMART_START_STOP = ("off", "immediate", "delayed")
LOOP_S = 1.0               # control step (THRM samples the temperature about once a second)
SCAN_S = 5.0               # HID enumeration while not connected
BLE_RETRY_S = 60.0         # reconnect attempts to a remembered BS1 over Bluetooth LE
EMIT_S = 2.0
MAX_CURVE_POINTS = 20
CURVE_SLOTS = 5            # 1.9.0.0: own temperature curves, one of them in use ("curve" is the copy of that one)
SLOT_NAME_MAX = 32
# 1.8.2.8: the highest speed a model actually reaches. The protocol (and THRM) take 0..5000 for every model, but the
# fan stops at its own ceiling: BS1 is rated 3000 rpm on its top gear and was measured at 3400 rpm. Other models:
# no data yet, so THRM's 5000. Targets above the limit are cut to it.
MODEL_MAX_RPM = {"BS1": 3400}
SHORTFALL_RATIO, SHORTFALL_S = 0.9, 15.0     # below 90 % of the target for 15 s: "does not reach the speed"

DEFAULTS = {
    "mode": "curve", "rpm": 2000, "gear": 2, "level": "mid",
    "curve": [list(p) for p in P.DEFAULT_FAN_CURVE],
    "temp_source": "max",
    "hysteresis": 2, "min_change": 50, "ramp_up": 220, "ramp_down": 160,     # THRM SmartControl defaults
    "ble_address": None,                                                       # a BS1 found before
    "model": None,                                                             # the last connected model
    "slot": 0,                                                                 # 1.9.0.0: the curve slot in use
    "curves": None,                                                            # [{name, curve}] × CURVE_SLOTS
}


def normal_slots(saved, current):
    """CURVE_SLOTS slots {name, curve}; a config from before 1.9.0.0 keeps its curve in slot 1, the others start
    with THRM's default curve."""
    out = []
    for i in range(CURVE_SLOTS):
        s = saved[i] if isinstance(saved, list) and i < len(saved) and isinstance(saved[i], dict) else None
        curve = None
        if s is not None:
            try:
                curve = check_curve(s.get("curve"))
            except (TypeError, ValueError, IndexError):
                curve = None
        if curve is None:
            curve = copy.deepcopy(current) if i == 0 and s is None and not isinstance(saved, list) \
                else [list(p) for p in P.DEFAULT_FAN_CURVE]
        out.append({"name": str((s or {}).get("name") or "")[:SLOT_NAME_MAX], "curve": [list(p) for p in curve]})
    return out


def interpolate(curve, temp):
    """Linear interpolation on the (°C, RPM) points; the ends hold outside them."""
    pts = sorted((float(t), int(r)) for t, r in curve)
    if temp <= pts[0][0]:
        return pts[0][1]
    for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
        if temp <= t1:
            return int(round(r0 + (r1 - r0) * (temp - t0) / (t1 - t0))) if t1 > t0 else r1
    return pts[-1][1]


def apply_ramp_limit(target, last, up, down):
    """smartcontrol/target.go ApplyRampLimit"""
    if target > last:
        return min(last + up, target)
    if target < last:
        return max(last - down, target)
    return target


def model_max_rpm(model):
    return MODEL_MAX_RPM.get(model or "", P.REALTIME_RPM_MAX)


def clamp_curve(curve, limit):
    return [[t, min(int(r), limit)] for t, r in curve]


def check_curve(curve):
    if not isinstance(curve, list) or not 2 <= len(curve) <= MAX_CURVE_POINTS:
        raise ValueError(f"curve: 2..{MAX_CURVE_POINTS} points")
    out = []
    for p in curve:
        t, r = float(p[0]), int(p[1])
        if not 0 <= t <= 120 or not 0 <= r <= P.REALTIME_RPM_MAX:
            raise ValueError(f"curve point: 0..120 °C, 0..{P.REALTIME_RPM_MAX} RPM")
        out.append([round(t, 1), r])
    out.sort()
    if len({p[0] for p in out}) != len(out):
        raise ValueError("curve: two points at the same temperature")
    for a, b in zip(out, out[1:]):                     # enforceNonDecreasingRPM
        if b[1] < a[1]:
            b[1] = a[1]
    return out


class FlydigiCooler:
    def __init__(self, temp_fn, emit, mock=False):
        self.temp_fn = temp_fn
        self.emit = emit
        self.mock = bool(mock and os.environ.get("UWCC_MOCK_FLYDIGI"))     # the window without hardware
        self.path = store.path("flydigi.json")
        saved = store.load_json(self.path, {}) or {}
        self.cfg = copy.deepcopy(DEFAULTS)
        self.cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
        try:
            self.cfg["curve"] = check_curve(self.cfg["curve"])
        except (TypeError, ValueError, IndexError):
            self.cfg["curve"] = copy.deepcopy(DEFAULTS["curve"])
        self.cfg["curves"] = normal_slots(self.cfg.get("curves"), self.cfg["curve"])
        if not isinstance(self.cfg.get("slot"), int) or not 0 <= self.cfg["slot"] < CURVE_SLOTS:
            self.cfg["slot"] = 0
        self.cfg["curve"] = [list(p) for p in self.cfg["curves"][self.cfg["slot"]]["curve"]]
        self.dev = None
        self.lock = threading.RLock()
        self.stop_ev = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.error = None
        self.settings = {}              # query_settings() of the connected cooler
        self.last_type = None           # "hid" | "ble": the transport of the last connection (THRM lastDeviceType)
        self.last_ble_try = 0.0
        self.applied = None             # the mode / gear applied to the connected cooler
        self.ctl_temp = None
        self.ctl_rpm = None
        self.last_emit = 0.0
        self.scanning = False
        self.suspended = False
        self.found_other = None         # 1.9.0.0: a BS2+ seen by the Bluetooth search, not paired yet
        self.short_since = None         # since when the fan stays below the target (monotonic)
        self.shortfall = None           # {"target", "rpm"} while it does for SHORTFALL_S
        try:
            import bleak  # noqa: F401
            self.ble_available = True
        except ImportError:
            self.ble_available = False

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def start(self):
        if self.thread_running():
            return
        self.stop_ev.clear()
        self.thread = threading.Thread(target=self._main, daemon=True, name="flydigi")
        self.thread.start()

    def stop(self):
        self.stop_ev.set()
        self.wake.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(5)
        self._drop()
        self._changed(force=True)

    def thread_running(self):
        return bool(self.thread and self.thread.is_alive())

    def suspend(self):
        self.suspended = True
        self._drop()

    def resume(self):
        """After sleep the HID handle may be dead (THRM reconnects): connect again from scratch."""
        self.suspended = False
        self._drop()
        self.wake.set()

    # -- connection -----------------------------------------------------------------------------------------------
    def _drop(self):
        with self.lock:
            d, self.dev = self.dev, None
            self.applied = None
            self.ctl_rpm = None
        if d is not None:
            try:
                d.close()
            except Exception:  # noqa: BLE001
                log.debug("flydigi close", exc_info=True)

    def _lost(self):
        with self.lock:
            self.dev = None
            self.applied = None
            self.ctl_rpm = None
        self._changed(force=True, event="disconnected")
        self.wake.set()

    def _connect_hid(self):
        if self.mock:
            return MockCooler(self._changed)
        cands = D.pick_hid_candidates(hidio.enumerate_hid(hidio.VENDOR_ID, hidio.SUPPORTED_PIDS))
        for c in cands:
            try:
                d = D.HidCooler(c, on_update=self._changed, on_lost=self._lost)
                log.info("Flydigi: %s connected (%s, %s)", d.model, d.transport, c["path"])
                return d
            except OSError as e:
                log.warning("Flydigi: opening %s (0x%04X) failed: %s", hidio.MODEL.get(c["pid"]), c["pid"], e)
                self.error = str(e)
        info = D.find_bs1_hid()
        if info:
            try:
                d = D.BS1Hid(info, on_update=self._changed, on_lost=self._lost)
                log.info("Flydigi: BS1 connected by USB")
                return d
            except (OSError, D.DeviceError) as e:
                log.warning("Flydigi: BS1 by USB: %s", e)
                self.error = str(e)
        return None

    def _connect_ble(self, known):
        d = D.BS1Ble(on_update=self._changed, on_lost=self._lost)
        try:
            addr = d.connect(known)
        except BaseException:
            d.close()
            raise
        self.cfg["ble_address"] = addr
        self._save()
        log.info("Flydigi: BS1 connected by Bluetooth LE (%s)", addr)
        return d

    def _try_connect(self):
        d = self._connect_hid()
        if d is None and self.ble_available and self.cfg.get("ble_address") \
                and time.monotonic() - self.last_ble_try >= BLE_RETRY_S \
                and not D.should_skip_ble_fallback(True, self.last_type, None):
            self.last_ble_try = time.monotonic()
            try:
                d = self._connect_ble(self.cfg["ble_address"])
            except Exception as e:  # noqa: BLE001
                log.debug("Flydigi: BS1 by Bluetooth LE: %s", e)
        if d is None:
            return False
        with self.lock:
            self.dev = d
            self.error = None
            self.found_other = None
            self.last_type = "ble" if d.kind == "bs1-ble" else "hid"
            self.applied = None
            self.ctl_rpm = None
        self._on_model(d.model)
        threading.Thread(target=self._read_settings, daemon=True, name="flydigi-query").start()
        self._changed(force=True, event="connected")
        return True

    def max_rpm(self):
        """The highest speed of the connected (or the last connected) model."""
        d = self.dev
        return model_max_rpm(d.model if d is not None and d.connected else self.cfg.get("model"))

    def _on_model(self, model):
        """Remember the model; an unchanged default curve is fitted to the model's limit (BS1: up to 3400 rpm)."""
        limit = model_max_rpm(model)
        changed = self.cfg.get("model") != model
        self.cfg["model"] = model
        default = [list(p) for p in P.DEFAULT_FAN_CURVE]
        if limit < P.REALTIME_RPM_MAX:
            for s in self.cfg.get("curves") or []:      # every slot still on the default curve (1.9.0.0)
                if [list(p) for p in s["curve"]] == default:
                    s["curve"] = clamp_curve(default, limit)
                    changed = True
            if self.cfg.get("curves"):
                self.cfg["curve"] = [list(p) for p in self.cfg["curves"][self.cfg.get("slot", 0)]["curve"]]
            elif [list(p) for p in self.cfg["curve"]] == default:
                self.cfg["curve"] = clamp_curve(default, limit)
                changed = True
        if changed:
            self._save()

    def _read_settings(self):
        d = self.dev
        if d is None:
            return
        try:
            self.settings = d.query_settings()
        except Exception as e:  # noqa: BLE001
            log.warning("Flydigi: reading the device settings: %s", e)
        self._changed(force=True)

    def search_ble(self):
        """Search by Bluetooth (button): one Bluetooth LE scan (10 s). A BS1 is connected at once; a BS2 / BS2 Pro /
        BS3 / BS3 Pro is only reported — it is controlled over HID after pairing in the system (as in THRM)."""
        if not self.ble_available:
            raise NotImplementedError("Bluetooth LE is not available (python3-bleak / bleak missing)")
        if self.dev is not None:
            raise ConnectionError("a cooler is already connected")
        self.scanning = True
        self.found_other = None
        self._changed(force=True)
        try:
            d = self._connect_ble(self.cfg.get("ble_address"))
        except D.OtherModelFound as e:
            self.found_other = {"name": e.name, "model": e.model, "address": e.address}
            log.info("Flydigi: %s found by Bluetooth LE — it needs pairing in the system", e.name)
            self._changed(force=True)
            return {"found_other": self.found_other}
        finally:
            self.scanning = False
        with self.lock:
            self.dev, self.last_type, self.applied, self.error = d, "ble", None, None
        self._on_model(d.model)
        self._changed(force=True, event="connected")
        self.wake.set()
        return d.info

    def forget_ble(self):
        self.cfg["ble_address"] = None
        self._save()
        if self.dev is not None and self.dev.kind == "bs1-ble":
            self._drop()
        self._changed(force=True)

    # -- control --------------------------------------------------------------------------------------------------
    def _main(self):
        next_scan = 0.0
        while not self.stop_ev.is_set():
            try:
                if self.suspended:
                    pass
                elif self.dev is None or not self.dev.connected:
                    if self.dev is not None:
                        self._drop()
                    if time.monotonic() >= next_scan:
                        next_scan = time.monotonic() + SCAN_S
                        self._try_connect()
                if self.dev is not None and self.dev.connected:
                    self._control()
            except Exception:  # noqa: BLE001
                log.exception("Flydigi loop")
            self.wake.wait(LOOP_S)
            self.wake.clear()

    def _temp(self):
        try:
            return self.temp_fn(self.cfg.get("temp_source", "max"))
        except Exception:  # noqa: BLE001
            return None

    def curve_target(self, temp):
        """Target RPM of the curve with THRM's hysteresis: a falling temperature counts only when it fell by the
        hysteresis or more; a rising one at once."""
        c = self.cfg
        if self.ctl_temp is None or temp >= self.ctl_temp or self.ctl_temp - temp >= c["hysteresis"]:
            self.ctl_temp = temp
        return interpolate(c["curve"], self.ctl_temp)

    def _control(self):
        d, c = self.dev, self.cfg
        mode = c["mode"]
        if mode == "device":
            self.applied = ("device",)
            self._track_shortfall(None)
            return
        if mode == "gear":
            key = ("gear", c["gear"], c["level"])
            if self.applied != key:
                rpm = P.DEFAULT_MANUAL_GEAR_RPM[P.GEARS[c["gear"] - 1]][c["level"]]
                try:
                    d.set_manual_gear_rpm(c["gear"], rpm)
                    self.applied, self.error = key, None
                except Exception as e:  # noqa: BLE001
                    self.error = str(e)
                    log.warning("Flydigi: gear %s %s: %s", c["gear"], c["level"], e)
                    self.applied = key                      # not again every second; a change retries
                self.ctl_rpm = None
                self._changed(force=True)
            self._track_shortfall(None)
            return
        if mode == "stop":
            target = 0
        elif mode == "rpm":
            target = int(c["rpm"])
        else:
            t = self._temp()
            if t is None:
                if self.ctl_rpm is not None:
                    return                                   # no temperature: hold the last target
                target = int(c["rpm"])
            else:
                target = self.curve_target(t)
        target = min(target, self.max_rpm())                 # the model's ceiling (BS1: 3400 rpm)
        if mode == "curve" and self.ctl_rpm is not None:
            rpm = apply_ramp_limit(target, self.ctl_rpm, int(c["ramp_up"]), int(c["ramp_down"]))
            if rpm != target and abs(rpm - self.ctl_rpm) < int(c["min_change"]):
                rpm = self.ctl_rpm
            elif rpm == target and target != 0 and abs(rpm - self.ctl_rpm) < int(c["min_change"]):
                rpm = self.ctl_rpm                           # MinRPMChange: not worth a write
        else:
            rpm = target
        try:
            if d.set_fan_speed(rpm):
                self.ctl_rpm = rpm
                self.applied = (mode,)
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            log.debug("Flydigi: set %d RPM: %s", rpm, e)
        self._track_shortfall(self.ctl_rpm)

    def _track_shortfall(self, target, now=None):
        """The fan stays below 90 % of the target for 15 s: the model's limit or a weak charger (the top speeds need a
        PD charger: 18-20 W for BS1 / BS2, 27 W for BS2 Pro). Cleared as soon as it catches up."""
        now = time.monotonic() if now is None else now
        st = self.dev.status if self.dev is not None and self.dev.connected else None
        cur = st.get("current_rpm") if st else None
        if not target or cur is None or cur >= SHORTFALL_RATIO * target:
            was = self.shortfall
            self.short_since = self.shortfall = None
            if was:
                self._changed(force=True)
            return
        if self.short_since is None:
            self.short_since = now
        elif now - self.short_since >= SHORTFALL_S:
            first = self.shortfall is None
            self.shortfall = {"target": target, "rpm": cur}
            if first:
                log.info("Flydigi: the fan stays at %d rpm, below the target %d rpm", cur, target)
                self._changed(force=True)

    # -- settings -------------------------------------------------------------------------------------------------
    def _save(self):
        store.save_json(self.path, self.cfg)

    def configure(self, b):
        c = dict(self.cfg)
        c["curves"] = copy.deepcopy(self.cfg["curves"])
        if "slot" in b:                                # 1.9.0.0: switch to another own curve
            v = int(b["slot"])
            if not 0 <= v < CURVE_SLOTS:
                raise ValueError(f"slot 0..{CURVE_SLOTS - 1}")
            c["slot"] = v
            c["curve"] = [list(p) for p in c["curves"][v]["curve"]]
        if "slot_name" in b:                           # the name of the slot in use ("" = the default "Curve N")
            c["curves"][c["slot"]]["name"] = str(b["slot_name"] or "").strip()[:SLOT_NAME_MAX]
        if "mode" in b:
            if b["mode"] not in MODES:
                raise ValueError(f"mode: {' | '.join(MODES)}")
            c["mode"] = b["mode"]
        if "rpm" in b:
            v = int(b["rpm"])
            if not 0 <= v <= P.REALTIME_RPM_MAX:
                raise ValueError(f"rpm 0..{P.REALTIME_RPM_MAX}")
            c["rpm"] = min(v, self.max_rpm())
        if "gear" in b:
            v = int(b["gear"])
            if not 1 <= v <= 4:
                raise ValueError("gear 1..4")
            c["gear"] = v
        if "level" in b:
            if b["level"] not in P.LEVELS:
                raise ValueError("level: low | mid | high")
            c["level"] = b["level"]
        if "curve" in b:
            c["curve"] = clamp_curve(check_curve(b["curve"]) if b["curve"] else copy.deepcopy(DEFAULTS["curve"]),
                                     self.max_rpm())
            c["curves"][c["slot"]]["curve"] = [list(p) for p in c["curve"]]    # edits the slot in use
        if "temp_source" in b:
            if b["temp_source"] not in TEMP_SOURCES:
                raise ValueError("temp_source: max | cpu | gpu")
            c["temp_source"] = b["temp_source"]
        for k, lo, hi in (("hysteresis", 0, 8), ("min_change", 20, 400),
                          ("ramp_up", 50, 1200), ("ramp_down", 50, 1200)):
            if k in b:                                 # THRM's limits (smartcontrol/config.go)
                v = int(b[k])
                if not lo <= v <= hi:
                    raise ValueError(f"{k} {lo}..{hi}")
                c[k] = v
        with self.lock:
            changed_mode = (c["mode"], c["gear"], c["level"]) != (self.cfg["mode"], self.cfg["gear"], self.cfg["level"])
            if c["slot"] != self.cfg["slot"]:
                log.info("Flydigi: curve %d (%s)", c["slot"] + 1, c["curves"][c["slot"]]["name"] or "-")
            self.cfg = c
            if changed_mode:
                self.applied = None
                self.ctl_temp = None
        self._save()
        self.wake.set()
        self._changed(force=True)

    def device_setting(self, b):
        """Settings kept in the cooler's own flash: gear light, power-on start, smart start/stop."""
        d = self.dev
        if d is None or not d.connected:
            raise ConnectionError("no Flydigi cooler connected")
        if "gear_light" in b:
            d.set_gear_light(bool(b["gear_light"]))
            self.settings["gear_light"] = bool(b["gear_light"])
        if "rgb" in b:                                       # the cooler's lighting on / off (0x46)
            d.set_rgb_enabled(bool(b["rgb"]))
            self.settings["rgb"] = "on" if b["rgb"] else "off"
        if "power_on_start" in b:
            d.set_power_on_start(bool(b["power_on_start"]))
            self.settings["power_on_start"] = bool(b["power_on_start"])
        if "smart_start_stop" in b:
            if b["smart_start_stop"] not in SMART_START_STOP:
                raise ValueError("smart_start_stop: off | immediate | delayed")
            d.set_smart_start_stop(b["smart_start_stop"])
        self._changed(force=True)

    def refresh_settings(self):
        self._read_settings()

    # -- automation -----------------------------------------------------------------------------------------------
    def snapshot(self):
        return {k: self.cfg[k] for k in ("mode", "rpm", "gear", "level", "slot")}

    def restore(self, snap):
        self.configure({k: v for k, v in (snap or {}).items() if k in ("mode", "rpm", "gear", "level", "slot")})

    # -- status ---------------------------------------------------------------------------------------------------
    def _changed(self, force=False, event="state"):
        now = time.monotonic()
        if not force and now - self.last_emit < EMIT_S:
            return
        self.last_emit = now
        try:
            self.emit("flydigi", {"event": event})
        except Exception:  # noqa: BLE001
            pass

    def rpm(self):
        d = self.dev
        st = d.status if d is not None and d.connected else None
        return st["current_rpm"] if st else None

    def brief(self):
        """For the Monitor page and the sidebar (every monitor sample): connected, model, fan speed, target."""
        d = self.dev
        conn = bool(d is not None and d.connected)
        st = (d.status if conn else None) or {}
        return {"connected": conn, "model": d.model if conn else None, "mode": self.cfg["mode"], "max": self.max_rpm(),
                "slot": self.cfg["slot"],
                "rpm": st.get("current_rpm"), "target": st.get("target_rpm"), "temp": self.ctl_temp
                if conn and self.cfg["mode"] == "curve" else None}

    def status(self):
        d = self.dev
        conn = bool(d is not None and d.connected)
        st = (d.status if conn else None) or {}
        return {
            "connected": conn, "running": self.thread_running(), "model": d.model if conn else None,
            "transport": getattr(d, "transport", None) if conn else None,
            "info": d.info if conn else {}, "settings": self.settings if conn else {},
            "current_rpm": st.get("current_rpm"), "target_rpm": st.get("target_rpm"),
            "realtime": st.get("realtime"), "selected_gear": st.get("selected_gear"), "max_gear": st.get("max_gear"),
            "smart_start_stop": st.get("smart_start_stop") or None,
            "control_rpm": self.ctl_rpm, "temp": self.ctl_temp if self.cfg["mode"] == "curve" else None,
            "config": self.cfg, "modes": list(MODES), "levels": list(P.LEVELS),
            "gear_presets": P.DEFAULT_MANUAL_GEAR_RPM, "gear_names": list(P.GEARS),
            "default_curve": [list(p) for p in P.DEFAULT_FAN_CURVE], "max_curve_points": MAX_CURVE_POINTS,
            "curve_slots": CURVE_SLOTS,
            "rpm_max": self.max_rpm(), "rpm_axis": P.REALTIME_RPM_MAX, "shortfall": self.shortfall if conn else None,
            "found_other": None if conn else self.found_other,
            "ble_available": self.ble_available, "scanning": self.scanning,
            "error": self.error if not conn else None,
        }


class MockCooler(D.BaseCooler):
    """A pretend BS2 Pro (--mock with UWCC_MOCK_FLYDIGI=1): the fan follows the target in steps."""
    kind = "hid"
    model = "BS2 Pro"
    transport = "mock"

    def __init__(self, on_update):
        super().__init__(on_update)
        if os.environ.get("UWCC_MOCK_FLYDIGI") == "BS1":                 # UWCC_MOCK_FLYDIGI=BS1: a pretend BS1
            self.model, self.transport = "BS1", "ble"
        self.connected = True
        self.info = {"model": self.model, "product_id": "0x1002", "path": "mock"}
        self.target, self.gear, self.rt = 1800, 2, False
        self._publish(self._st())
        threading.Thread(target=self._spin, daemon=True).start()

    def _st(self):
        cur = (self.status or {}).get("current_rpm", 0)
        top = 3000 if self.model == "BS1" else 5000      # a pretend weak charger on the BS1: below its 3400
        cur += max(-150, min(150, min(self.target, top) - cur))
        return {"gear_byte": 0x60 | (0x6 + 2 * self.gear), "mode_byte": 0x02 | (1 if self.rt else 0),
                "max_gear": "extreme", "selected": P.gear_code_name(self.gear), "selected_gear": self.gear,
                "realtime": self.rt, "smart_start_stop": "off", "current_rpm": cur, "target_rpm": self.target}

    def _spin(self):
        while self.connected:
            time.sleep(0.5)
            self._publish(self._st())

    def set_fan_speed(self, rpm):
        self.target, self.rt = int(rpm), True
        return True

    def set_manual_gear_rpm(self, gear, rpm):
        self.gear, self.target, self.rt = int(gear), int(rpm), False
        return True

    set_fixed_gear = lambda self, g: self.set_manual_gear_rpm(g, P.DEFAULT_MANUAL_GEAR_RPM[P.GEARS[int(g) - 1]]["mid"])  # noqa: E731

    def set_gear_light(self, on):
        return True

    set_power_on_start = set_gear_light

    def set_smart_start_stop(self, mode):
        return True

    def set_rgb_enabled(self, on):
        return True

    def query_settings(self):
        return {"model": self.model, "firmware": "0.0.3.5", "device_id": "AA:BB:CC:DD:EE:FF", "capability_tier": 3,
                "gear_table": [1700, 2400, 3000, 4000], "rgb": "on", "max_selectable_gear": 4}

    def close(self):
        self.connected = False
