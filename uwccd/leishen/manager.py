"""Leishen / Thunderobot (Quanta chassis, Leishen ControlCenter 3.x) — features (experimental).

Commands of the firmware's RW_GMWMI block (see transport.py), as the firmware of the Thunderobot R16 (board NLY,
BIOS TP162) handles them in its ACPI method WSAA:

  get 0x200  a2 CPU °C, a3 GPU °C, a4 fan 1 rpm, a5 fan 2 rpm, a6 keyboard light level (0 off, 1 low, 2 high);
             the firmware also sets its "control program present" bit (EC 0x62 bit 0), as every poll of Leishen
             ControlCenter does
  get 0x201  a0 0x200 = this command set, a2 0x34 RGB keyboard / 0x35 single-colour keyboard
  get 0x202  a2..a6 hardware flags
  get 0x205  a2 factory fan table (4 = NLY)
  get 0x206  a2 "control program present" bit, a3 the same or 0xFF = no third fan, a4 adapter flag
  get 0x207  a2 GPU °C, a3 fan 3 rpm
  get 0x300  a2 power mode (0 Performance, 1 Gaming, 2 Office)
  set 0x300  a2 power mode: EC mode register + NVIDIA power limits (NPCF), as Leishen ControlCenter does
  set 0x205  a2 / a3 / a4 fan 1 / 2 / 3 speed in % (0xFF: no third fan)
  set 0x206  bit "control program present": the firmware writes a2, then a3 (both are sent)
  set 0x200  a2 0, a6 1 = Windows key locked, 0 = free
  set 0x202  a2 0 = touchpad off, 1 = on
  set 0x400  a2 1 = mode-key event handled
  set 0x100  keyboard light: a2 zone (0 all, 6 keyboard, 5 / 4 / 3 keyboard zones 1-3, 7 rear, 8 logo),
             a3 = mode << 28 | level << 24 | RRGGBB (mode 1 static, 2 breathing, 3 colour cycle, 4 ambilight)

Own fan speeds work like in Leishen ControlCenter: the program reads the temperatures every 2 s and writes the speeds
of its curve with set 0x205; "automatic" is set 0x206 with 0. The light command waits inside the firmware for the
keyboard controller, so it is only sent when the firmware reports an RGB keyboard (0x34). The firmware does not report
the Windows key lock, the touchpad or the light colours: the values last set here are kept (setting leishen_state).
Every command that changes something needs the setting leishen_writes.
"""
import logging
import sys
import threading
import time

from .transport import GET, SET, UNKNOWN, LeishenError, open_transport, pack, unpack

log = logging.getLogger("uwccd.leishen")

MODES = {"performance": 0, "gaming": 1, "office": 2}
MODE_NAMES = {v: k for k, v in MODES.items()}
KB_ZONES = {"all": 0, "keyboard": 6, "zone1": 5, "zone2": 4, "zone3": 3, "rear": 7, "logo": 8}
KB_MODES = {"static": 1, "breathing": 2, "cycle": 3, "ambilight": 4}
NO_FAN = 0xFF
CURVE_TEMPS = (30, 40, 50, 60, 70, 80, 90, 100)
DEFAULT_CURVE = [[t, d] for t, d in zip(CURVE_TEMPS, (30, 30, 30, 30, 50, 60, 70, 100))]   # factory table NLY
HYSTERESIS = 5
READ_CACHE_S = 1.5


def check_curve(pts):
    pts = [[int(t), int(d)] for t, d in pts]
    if not 2 <= len(pts) <= 12:
        raise ValueError("a curve has 2..12 points [[°C, %], ...]")
    for i, (t, d) in enumerate(pts):
        if not (0 <= t <= 110 and 0 <= d <= 100):
            raise ValueError("temperature 0..110 °C, speed 0..100 %")
        if i and (t <= pts[i - 1][0] or d < pts[i - 1][1]):
            raise ValueError("temperatures must rise and speeds must not fall")
    return pts


def curve_duty(pts, temp, last=None):
    """Steps like Leishen ControlCenter: the speed of the highest point at or below the temperature; a lower step only
    when the temperature has fallen HYSTERESIS °C below the point of the current one."""
    want = pts[0][1]
    for t, d in pts:
        if temp >= t:
            want = d
    if last is not None and want < last:
        for t, d in pts:
            if d == last and temp > t - HYSTERESIS:
                return last
    return want


def next_mode(cur):
    """The mode key of Leishen ControlCenter: Office -> Gaming -> Performance -> Office."""
    v = MODES.get(cur, 1)
    return MODE_NAMES[2 if v == 0 else v - 1]


class LeishenManager:
    def __init__(self, store, emit, mock=False):
        self.store = store
        self.emit = emit
        self.mock = mock
        self.wmi = None
        self.reason = "not started"
        self.info = {}
        self.lock = threading.Lock()
        self.stop_ev = threading.Event()
        self.last_duty = {}
        self.curve_error = None
        self._cache = (0.0, None)
        self.hotkey_state = "Windows only" if sys.platform != "win32" else "not started"

    # -- setup -----------------------------------------------------------------------------------------
    @property
    def present(self):
        return self.wmi is not None

    def start(self):
        self.wmi, self.reason = open_transport(self.mock)
        if not self.wmi:
            log.debug("Leishen: %s", self.reason)
            return False
        try:
            r = self.get(0x201)
            if r["a0"] == UNKNOWN or r["a2"] not in (0x34, 0x35):
                raise LeishenError(f"the firmware does not answer the Leishen commands (0x201: {r})")
            self.info = {"kb_rgb": r["a2"] == 0x34, "kb_code": r["a2"], "version": r["a0"],
                         "power_modes": r["a0"] != 0x106}
            self.info["fans3"] = self.get(0x206)["a3"] != NO_FAN
            self.info["fan_table"] = self.get(0x205)["a2"]
        except Exception as e:  # noqa: BLE001
            log.warning("Leishen: the interface answers wrongly, module off: %s", e)
            self.reason = str(e)
            self.wmi.close()
            self.wmi = None
            return False
        log.info("Leishen / Thunderobot (experimental) via %s: %s keyboard, %d fans, fan table %s", self.wmi.name,
                 "RGB" if self.info["kb_rgb"] else "single-colour", 3 if self.info["fans3"] else 2,
                 self.info["fan_table"])
        threading.Thread(target=self._late, daemon=True, name="leishen-start").start()
        threading.Thread(target=self._fan_loop, daemon=True, name="leishen-fans").start()
        if sys.platform == "win32" and not self.mock:
            threading.Thread(target=self._hotkey_loop, daemon=True, name="leishen-keys").start()
        return True

    def _late(self):
        if self.store.get("leishen_restore", True) and self.writes_allowed():
            self.restore()

    def stop(self):
        """Service stop: the fans go back to the firmware (automatic)."""
        self.stop_ev.set()
        if self.present and self.writes_allowed() and self.state().get("fan_mode", "auto") != "auto":
            try:
                self._fans_auto()
                log.info("Leishen: fans back to automatic")
            except Exception as e:  # noqa: BLE001
                log.warning("Leishen: fans back to automatic failed: %s", e)

    # -- raw -------------------------------------------------------------------------------------------
    def _call(self, a0, a1, a2=0, a3=0, a4=0, a5=0, a6=0):
        if not self.wmi:
            raise LookupError("no Leishen interface on this laptop")
        with self.lock:
            return unpack(self.wmi.call(pack(a0, a1, a2, a3, a4, a5, a6)))

    def get(self, func):
        return self._call(GET, func)

    def hw(self):
        """get 0x200 (temperatures, fans 1-2, light level), shared by the monitor and the fan curve for 1.5 s."""
        t, v = self._cache
        if v is not None and time.time() - t < READ_CACHE_S:
            return v
        v = self.get(0x200)
        self._cache = (time.time(), v)
        return v

    def _set(self, func, what, **a):
        if not self.writes_allowed():
            raise LookupError("Leishen commands are off (setting leishen_writes)")
        log.info("Leishen set 0x%03X %s %s", func, " ".join(f"{k}=0x{v:X}" for k, v in a.items()), what)
        r = self._call(SET, func, **a)
        if r["a0"] == UNKNOWN:
            raise ValueError(f"the firmware does not know command 0x{func:03X}")
        return r

    def writes_allowed(self):
        return bool(self.store.get("leishen_writes", False))

    # -- state ------------------------------------------------------------------------------------------
    def state(self):
        return dict(self.store.get("leishen_state", {}) or {})

    def _save(self, **kv):
        st = self.state()
        for k, v in kv.items():
            if isinstance(v, dict) and k == "light":
                st[k] = {**(st.get(k) or {}), **v}
            else:
                st[k] = v
        self.store.set("leishen_state", st)
        self.emit("leishen", {})

    def restore(self):
        st = self.state()
        steps = []
        if st.get("mode") in MODES:
            steps.append(lambda: self.set_mode(st["mode"], save=False))
        if st.get("fan_mode") == "fixed" and st.get("fixed"):
            steps.append(lambda: self.set_fans_fixed(st["fixed"], save=False))
        if "win_lock" in st:
            steps.append(lambda: self.set_win_lock(st["win_lock"], save=False))
        for f in steps:
            try:
                f()
                time.sleep(0.05)
            except Exception as e:  # noqa: BLE001
                log.warning("Leishen restore: %s", e)
        if steps:
            log.info("Leishen: %d saved settings sent again", len(steps))

    # -- reading ---------------------------------------------------------------------------------------
    def sensors(self):
        a = self.hw()
        fans = [{"fan": "cpu", "rpm": a["a4"] & 0xFFFF}, {"fan": "gpu", "rpm": a["a5"] & 0xFFFF}]
        if self.info.get("fans3"):
            fans.append({"fan": "sys", "rpm": self.get(0x207)["a3"] & 0xFFFF})
        return {"cpu_temp": a["a2"] & 0xFF, "gpu_temp": a["a3"] & 0xFF, "fans": fans,
                "kb_level": a["a6"]}       # the firmware maps its register to 0 off, 1 low, 2 high

    def monitor_fans(self):
        """Fans for the Monitor page / history: rpm from the firmware, % only where this program sets them."""
        try:
            a = self.hw()
        except Exception as e:  # noqa: BLE001  (the monitor keeps running without the fans)
            log.debug("Leishen fans: %s", e)
            return {"cpu_duty": None, "cpu_rpm": 0}
        duty = self.last_duty if self.state().get("fan_mode") in ("fixed", "curve") else {}
        return {"cpu_duty": duty.get("cpu"), "cpu_rpm": a["a4"] & 0xFFFF,
                "gpu_duty": duty.get("gpu"), "gpu_rpm": a["a5"] & 0xFFFF}

    def cpu_temp(self):
        try:
            return (self.hw()["a2"] & 0xFF) or None
        except Exception:  # noqa: BLE001
            return None

    def mode(self):
        v = self.get(0x300)["a2"]
        return MODE_NAMES.get(v, v)

    def status(self):
        st = {"present": self.present, "reason": None if self.present else self.reason,
              "transport": getattr(self.wmi, "name", None), "writes": self.writes_allowed(),
              "restore": bool(self.store.get("leishen_restore", True)),
              "hotkey": bool(self.store.get("leishen_hotkey", False)), "hotkey_state": self.hotkey_state,
              "info": self.info, "state": self.state(), "modes": list(MODES), "kb_zones": list(KB_ZONES),
              "kb_modes": list(KB_MODES), "default_curve": DEFAULT_CURVE, "curve_error": self.curve_error,
              "duty": self.last_duty}
        if self.present:
            try:
                st["sensors"] = self.sensors()
                st["mode"] = self.mode()
            except Exception as e:  # noqa: BLE001
                st["error"] = str(e)
        return st

    def diagnostics(self):
        """For the diagnostic report: every read-only command, raw."""
        if not self.present:
            return {"present": False, "reason": self.reason}
        d = {"present": True, "transport": self.wmi.name, "info": self.info, "state": self.state(),
             "writes": self.writes_allowed(), "hotkey_state": self.hotkey_state, "get": {}}
        for f in (0x200, 0x201, 0x202, 0x203, 0x204, 0x205, 0x206, 0x207, 0x300, 0x400):
            try:
                d["get"][f"0x{f:03X}"] = {k: f"0x{v:X}" for k, v in self.get(f).items()}
            except Exception as e:  # noqa: BLE001
                d["get"][f"0x{f:03X}"] = f"error: {e}"
        return d

    # -- commands --------------------------------------------------------------------------------------
    def set_mode(self, name, save=True):
        if name not in MODES:
            raise ValueError(f"mode {name} ({', '.join(MODES)})")
        self._set(0x300, f"power mode {name}", a2=MODES[name])
        if save:
            self._save(mode=name)

    def _fans_auto(self):
        self._set(0x206, "own fan speeds off", a2=0, a3=0)
        self.last_duty = {}

    def _fans_speed(self, cpu, gpu, sys_=None, enable=False):
        if enable:
            self._set(0x206, "own fan speeds on", a2=1, a3=1)
        s = NO_FAN if sys_ is None or not self.info.get("fans3") else int(sys_)
        self._set(0x205, f"fans {cpu}/{gpu}/{s} %", a2=int(cpu), a3=int(gpu), a4=s)
        self.last_duty = {"cpu": int(cpu), "gpu": int(gpu), **({"sys": s} if s != NO_FAN else {})}

    def set_fans_auto(self, save=True):
        self._fans_auto()
        if save:
            self._save(fan_mode="auto")

    def set_fans_fixed(self, fixed, save=True):
        vals = {k: int(fixed.get(k, 50)) for k in ("cpu", "gpu", "sys")}
        for v in vals.values():
            if not 0 <= v <= 100:
                raise ValueError("fan speed 0..100 %")
        if min(vals["cpu"], vals["gpu"]) < 20 and not fixed.get("allow_low"):
            raise ValueError("below 20 % the fans may stop: send allow_low to confirm")
        self._fans_speed(vals["cpu"], vals["gpu"], vals["sys"], enable=True)
        if save:
            self._save(fan_mode="fixed", fixed={k: vals[k] for k in ("cpu", "gpu", "sys")})

    def set_fans_curve(self, curves, save=True):
        clean = {}
        for k in ("cpu", "gpu", "sys"):
            if curves.get(k):
                clean[k] = check_curve(curves[k])
        if not clean.get("cpu"):
            raise ValueError("a curve for cpu is needed (gpu and sys use it when they have none)")
        if not self.writes_allowed():
            raise LookupError("Leishen commands are off (setting leishen_writes)")
        self.last_duty = {}
        self._set(0x206, "own fan speeds on", a2=1, a3=1)
        if save:
            self._save(fan_mode="curve", curves=clean)
        self._curve_step()

    def _curve_step(self):
        st = self.state()
        if st.get("fan_mode") != "curve" or not self.writes_allowed():
            return
        cur = st.get("curves") or {}
        a = self.hw()
        temps = {"cpu": a["a2"] & 0xFF, "gpu": a["a3"] & 0xFF}
        temps = {k: max(30, v) for k, v in temps.items()}            # Leishen ControlCenter: at least 30 °C
        temps["sys"] = max(temps.values())
        duty = {}
        for k in ("cpu", "gpu", "sys"):
            pts = cur.get(k) or cur.get("cpu")
            duty[k] = curve_duty(pts, temps[k], self.last_duty.get(k))
        if {k: duty[k] for k in ("cpu", "gpu")} != {k: self.last_duty.get(k) for k in ("cpu", "gpu")} \
                or (self.info.get("fans3") and duty["sys"] != self.last_duty.get("sys")):
            self._fans_speed(duty["cpu"], duty["gpu"], duty["sys"])

    def _fan_loop(self):
        while not self.stop_ev.wait(2):
            try:
                self._curve_step()
                self.curve_error = None
            except Exception as e:  # noqa: BLE001
                if str(e) != self.curve_error:
                    log.warning("Leishen fan curve: %s", e)
                self.curve_error = str(e)

    def set_win_lock(self, on, save=True):
        self._set(0x200, f"Windows key {'locked' if on else 'free'}", a2=0, a6=1 if on else 0)
        if save:
            self._save(win_lock=bool(on))

    def set_touchpad(self, on, save=True):
        self._set(0x202, f"touchpad {'on' if on else 'off'}", a2=1 if on else 0)
        if save:
            self._save(touchpad=bool(on))

    def set_light(self, zone, mode, level, rgb, save=True):
        if not self.info.get("kb_rgb"):
            raise ValueError("the firmware reports a single-colour keyboard: the light command is not sent")
        if zone not in KB_ZONES or mode not in KB_MODES or int(level) not in (0, 1, 2):
            raise ValueError(f"zone {'/'.join(KB_ZONES)}, mode {'/'.join(KB_MODES)}, level 0..2")
        r, g, b = (int(x) & 0xFF for x in rgb)
        data = (KB_MODES[mode] << 28) | (int(level) << 24) | (r << 16) | (g << 8) | b
        self._set(0x100, f"light {zone} {mode} level {level} #{r:02X}{g:02X}{b:02X}", a2=KB_ZONES[zone], a3=data)
        if save:
            self._save(light={zone: {"mode": mode, "level": int(level), "color": [r, g, b]}})

    # -- mode key ----------------------------------------------------------------------------------------
    def handle_event(self, data):
        """GMC_WMIEvent.EventDetail (bytes): byte 7 = the mode key (Leishen ControlCenter switches the mode itself)."""
        data = bytes(data or b"")
        if len(data) < 8 or not data[7]:
            return None
        if not (self.store.get("leishen_hotkey", False) and self.writes_allowed()):
            return None
        new = next_mode(self.state().get("mode") or self.mode())
        self.set_mode(new)
        try:
            self._set(0x400, "mode-key event handled", a2=1)
        except Exception as e:  # noqa: BLE001
            log.debug("Leishen 0x400: %s", e)
        log.info("Leishen mode key: %s", new)
        self.emit("toast", {"text": f"Leishen: {new}"})
        return new

    def _hotkey_loop(self):
        """root\\WMI GMC_WMIEvent (the firmware's hot-key events), Windows only."""
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            svc = win32com.client.GetObject("winmgmts:{impersonationLevel=impersonate}!\\\\.\\root\\WMI")
            watcher = svc.ExecNotificationQuery("SELECT * FROM GMC_WMIEvent")
        except Exception as e:  # noqa: BLE001
            self.hotkey_state = f"unavailable: {e}"
            log.info("Leishen hot-key events unavailable: %s", e)
            return
        self.hotkey_state = "listening"
        while not self.stop_ev.is_set():
            try:
                ev = watcher.NextEvent(1000)
            except Exception:  # noqa: BLE001  (timeout every second)
                continue
            try:
                raw = ev.Properties_("EventDetail").Value
                data = bytes(bytearray(raw or []))
                log.debug("Leishen event %s", data.hex())
                self.handle_event(data)
            except Exception as e:  # noqa: BLE001
                log.warning("Leishen event: %s", e)

    # -- API ---------------------------------------------------------------------------------------------
    def command(self, b):
        """POST /api/leishen: one action per request."""
        a = str(b.get("action", ""))
        if a == "mode":
            self.set_mode(str(b["mode"]))
        elif a == "fans_auto":
            self.set_fans_auto()
        elif a == "fans_fixed":
            self.set_fans_fixed(b.get("fixed") or {})
        elif a == "fans_curve":
            self.set_fans_curve(b.get("curves") or {})
        elif a == "win_lock":
            self.set_win_lock(bool(b["on"]))
        elif a == "touchpad":
            self.set_touchpad(bool(b["on"]))
        elif a == "light":
            c = b.get("color", [255, 255, 255])
            if isinstance(c, str):
                c = list(bytes.fromhex(c.lstrip("#")))
            self.set_light(str(b.get("zone", "all")), str(b.get("mode", "static")), int(b.get("level", 2)), c)
        else:
            raise KeyError(f"action {a}")
        self.emit("leishen", {})
        return self.status()
