"""Control Center 3.0 / Clevo — features (experimental).

What Control Center 3 does through its driver, as DCHU commands (data = little-endian u32, sub-command in the top byte):

    0x0C          fan speeds, duty, temperatures (buffer)
    0x0D          fan count, factory fan curves, start fan mode (buffer)
    0x0E          custom fan curve (256-byte buffer)
    0x10 0x46 0x52 0x60 0x7A   capability bits
    0x67          keyboard backlight: F0..F3 zone colour (B,R,G), F4 brightness 0..255, E0 on/off, effect codes
    0x79          options: 01 fan mode, 0E fan offset, 18 backlight sleep timer, 19 power mode, 1E boot effect,
                  22 factory fan curve, 29 anti-dust
    0x04          package query (EC version)

The firmware does not report the current power mode, fan mode or backlight: Control Center 3 keeps them itself.
So does this module (setting clevo_state); with clevo_restore they are sent again when the service starts.
Every command that changes something needs the setting clevo_writes ("Allow commands (experimental)").
"""
import logging
import struct
import threading
import time

from .transport import ClevoError, open_transport

log = logging.getLogger("uwccd.clevo")

POWER_MODES = {"quiet": 0, "powersave": 1, "performance": 2, "entertainment": 3}
FAN_MODES = {"auto": 0, "max": 1, "maxq": 5, "custom": 6}
KB_EFFECTS = {"random": 0x70, "breathe": 0x10, "cycle": 0x33, "wave": 0xB0, "dance": 0x80, "tempo": 0x90,
              "flash": 0xA0}
FANS = ("cpu", "gpu1", "gpu2")
RPM_K = 2156250            # rpm = K / raw period

OPT_FAN_MODE, OPT_FAN_OFFSET, OPT_KB_SLEEP, OPT_POWER, OPT_BOOT_FX, OPT_FAN_DEFAULT, OPT_ANTIDUST = (
    0x01, 0x0E, 0x18, 0x19, 0x1E, 0x22, 0x29)

CAP_BITS = {
    0x10: {0: "power_modes", 1: "flexikey", 2: "flexi_access", 3: "per_key_kb", 4: "rgb_kb", 5: "gpu_oc",
           6: "cpu_oc", 7: "fan_setting", 8: "energy_save", 9: "battery_utility"},
    0x7A: {0: "fan_speed", 1: "gaming_group", 4: "custom_fan", 5: "wake_on_lan", 12: "lightbar", 15: "fanless",
           18: "logo_color", 20: "mshybrid", 24: "xmp", 28: "kb_sleep"},
    0x60: {2: "new_mode", 5: "all_mode_gpu_oc", 7: "anti_dust", 9: "pcie_aspm", 10: "no_fan_offset"},
}


def u32(sub, value=0):
    return struct.pack("<I", ((sub & 0xFF) << 24) | (int(value) & 0xFFFFFF))


def pct2raw(p):
    return max(0, min(255, round(float(p) / 100 * 255)))


def raw2pct(r):
    return round(r / 255 * 100)


def slope(d_lo, d_hi, t_lo, t_hi):
    """Control Center 3 slope between two curve points: duty % per °C × 2.55 × 16."""
    if t_hi <= t_lo:
        return 0
    return max(0, min(0xFFFF, round((d_hi - d_lo) / (t_hi - t_lo) * 2.55 * 16)))


def parse_fan_info(b):
    out = []
    for i, name in enumerate(FANS):
        period = (b[2 + 2 * i] << 8) | b[3 + 2 * i]
        out.append({"fan": name, "rpm": RPM_K // period if period else 0, "duty": raw2pct(b[16 + 3 * i]),
                    "temp": b[18 + 3 * i] or None, "raw_period": period})
    return out


def parse_fan_table(b):
    """0x0D: count, start mode, factory curve per fan (T1, D1, T2, D2, T3, D3; D in 0..255)."""
    t = {"count": b[12], "start_mode": b[14], "maxq": b[14] == 5,
         "custom_supported": b[12] > 1 and not (b[43] >> 1) & 1, "curves": {}}
    for i, name in enumerate(FANS):
        o = 16 + 8 * i
        pts = [(b[o + 2 * k], raw2pct(b[o + 2 * k + 1])) for k in range(3)]
        if any(x for p in pts for x in p):
            t["curves"][name] = [list(p) for p in pts] + [[100, 100]]
    return t


def build_curve(curves, defaults):
    """0x0E buffer from {fan: [[t1,d1],[t2,d2],[t3,d3]]} (d in %); the first point and missing fans come from the
    factory curve. Point 4 is always 100 °C / 100 %."""
    b = bytearray(256)
    for i, name in enumerate(FANS):
        pts = curves.get(name) or defaults.get(name)
        if not pts:
            continue
        p = [list(map(int, x)) for x in pts[:3]] + [[100, 100]]
        b[2 + 4 * i:6 + 4 * i] = bytes([p[1][0], pct2raw(p[1][1]), p[2][0], pct2raw(p[2][1])])
        for k in range(3):
            r = slope(p[k][1], p[k + 1][1], p[k][0], p[k + 1][0])
            struct.pack_into(">H", b, 14 + 6 * i + 2 * k, r)
    return bytes(b)


def check_curve(pts):
    if len(pts) < 3:
        raise ValueError("a curve has 3 points: [[t, duty], ...]")
    pts = [[int(t), int(d)] for t, d in pts[:3]]
    for t, d in pts:
        if not (0 <= t < 100 and 0 <= d <= 100):
            raise ValueError("temperature 0..99 °C, duty 0..100 %")
    if not (pts[0][0] < pts[1][0] < pts[2][0]) or not (pts[0][1] <= pts[1][1] <= pts[2][1]):
        raise ValueError("temperatures must rise and duties must not fall")
    return pts


class ClevoManager:
    def __init__(self, store, emit, mock=False):
        self.store = store
        self.emit = emit
        self.mock = mock
        self.dchu = None
        self.reason = "not started"
        self.caps = {}
        self.cap_raw = {}
        self.table = {}
        self.ec_version = None
        self.lock = threading.Lock()

    # -- setup -----------------------------------------------------------------------------------------
    @property
    def present(self):
        return self.dchu is not None

    def start(self):
        self.dchu, self.reason = open_transport(self.mock)
        if not self.dchu:
            log.debug("Control Center 3.0 / Clevo: %s", self.reason)
            return False
        try:
            self._read_caps()
            self.table = parse_fan_table(self._buf(0x0D))
        except Exception as e:  # noqa: BLE001
            log.warning("Control Center 3.0 / Clevo: reading the capabilities failed: %s", e)
        log.info("Control Center 3.0 / Clevo (experimental) via %s: %s", self.dchu.name,
                 ", ".join(k for k, v in self.caps.items() if v) or "no capability bits")
        threading.Thread(target=self._late, daemon=True, name="clevo-start").start()
        return True

    def _late(self):
        try:
            self.ec_version = self.read_ec_version()
        except Exception as e:  # noqa: BLE001
            log.debug("Clevo EC version: %s", e)
        if self.store.get("clevo_restore", True) and self.writes_allowed():
            self.restore()

    def _read_caps(self):
        for cmd in (0x10, 0x46, 0x52, 0x60, 0x7A):
            self.cap_raw[cmd] = self._int(cmd)
        caps = {}
        for cmd, bits in CAP_BITS.items():
            v = self.cap_raw.get(cmd, 0)
            for bit, name in bits.items():
                caps[name] = bool((v >> bit) & 1)
        caps["fan_offset"] = not caps.pop("no_fan_offset")
        self.caps = caps

    # -- raw ---------------------------------------------------------------------------------------------
    def _call(self, cmd, data=b"", length=4):
        if not self.dchu:
            raise LookupError("no Control Center 3.0 / Clevo interface on this laptop")
        with self.lock:
            return self.dchu.call(cmd, data, length)

    def _int(self, cmd):
        return self._call(cmd).value

    def _buf(self, cmd):
        return self._call(cmd).buffer()

    def _write(self, cmd, data, length=4, what=""):
        if not self.writes_allowed():
            raise LookupError("Control Center 3.0 / Clevo commands are off (setting clevo_writes)")
        log.info("Clevo DCHU 0x%02X %s %s", cmd, data[:length].hex(), what)
        try:
            return self._call(cmd, data, length)
        except (OSError, ClevoError) as e:
            raise ConnectionError(f"DCHU 0x{cmd:02X}: {e}") from e

    def writes_allowed(self):
        return bool(self.store.get("clevo_writes", False))

    # -- state (the firmware does not report it) -----------------------------------------------------------
    def state(self):
        return dict(self.store.get("clevo_state", {}) or {})

    def _save(self, _drop=(), **kv):
        st = self.state()
        for k in _drop:                      # "curve", or "kb.effect"
            top, _, sub = k.partition(".")
            if sub:
                (st.get(top) or {}).pop(sub, None)
            else:
                st.pop(top, None)
        for k, v in kv.items():
            if isinstance(v, dict):
                st[k] = {**(st.get(k) or {}), **v}
            else:
                st[k] = v
        self.store.set("clevo_state", st)
        self.emit("clevo", {})

    def restore(self):
        st = self.state()
        kb = st.get("kb") or {}
        steps = []
        if "power_mode" in st:
            steps.append(lambda: self.set_power_mode(st["power_mode"], save=False))
        if st.get("fan_mode") == "custom" and st.get("curve"):
            steps.append(lambda: self.set_curve(st["curve"], save=False))
        elif "fan_mode" in st:
            steps.append(lambda: self.set_fan_mode(st["fan_mode"], save=False))
        if "fan_offset" in st:
            steps.append(lambda: self.set_fan_offset(st["fan_offset"], save=False))
        if "on" in kb:
            steps.append(lambda: self.kb_power(kb["on"], save=False))
        if kb.get("on", True):
            if "effect" in kb:
                steps.append(lambda: self.kb_effect(kb["effect"], save=False))
            elif "color" in kb:
                steps.append(lambda: self.kb_color(kb["color"], save=False))
            if "brightness" in kb:
                steps.append(lambda: self.kb_brightness(kb["brightness"], save=False))
        for f in steps:
            try:
                f()
                time.sleep(0.05)
            except Exception as e:  # noqa: BLE001
                log.warning("Clevo restore: %s", e)
        if steps:
            log.info("Control Center 3.0 / Clevo: %d saved settings sent again", len(steps))

    # -- reading -------------------------------------------------------------------------------------------
    def fans(self):
        return parse_fan_info(self._buf(0x0C))[:max(1, self.table.get("count") or 2)]

    def read_ec_version(self):
        txt = b""
        for i in range(4):
            q = bytes([1, i, 0, 0, 0, 0, 0xDE])
            r = self._call(0x04, q, 256).buffer()
            if i:
                txt += r[1:6]
        s = ("1." + txt.decode("ascii", "replace")).split("$")[0].strip("\0 ")
        return s if len(s) > 2 else None

    def status(self):
        st = {"present": self.present, "reason": None if self.present else self.reason,
              "transport": getattr(self.dchu, "name", None), "writes": self.writes_allowed(),
              "restore": bool(self.store.get("clevo_restore", True)), "caps": self.caps,
              "caps_raw": {f"0x{k:02X}": v for k, v in self.cap_raw.items()}, "fan_table": self.table,
              "ec_version": self.ec_version, "state": self.state(),
              "power_modes": list(POWER_MODES), "fan_modes": self.fan_modes(), "kb_effects": list(KB_EFFECTS)}
        if self.present:
            try:
                st["fans"] = self.fans()
            except Exception as e:  # noqa: BLE001
                st["fans_error"] = str(e)
        return st

    def fan_modes(self):
        m = ["auto", "max"]
        if self.table.get("maxq"):
            m.append("maxq")
        if self.table.get("custom_supported") or self.caps.get("custom_fan"):
            m.append("custom")
        return m

    def diagnostics(self):
        """For the diagnostic report: capability words and the raw fan buffers (read-only commands)."""
        if not self.present:
            return {"present": False, "reason": self.reason}
        d = {"present": True, "transport": self.dchu.name, "caps_raw": {f"0x{k:02X}": f"0x{v:08X}"
                                                                        for k, v in self.cap_raw.items()},
             "caps": self.caps, "ec_version": self.ec_version, "state": self.state(),
             "writes": self.writes_allowed()}
        for cmd in (0x0C, 0x0D):
            try:
                d[f"buf_0x{cmd:02X}"] = self._buf(cmd)[:64].hex(" ")
            except Exception as e:  # noqa: BLE001
                d[f"buf_0x{cmd:02X}"] = f"error: {e}"
        d["fan_table"] = self.table
        return d

    # -- commands ------------------------------------------------------------------------------------------
    def set_power_mode(self, name, save=True):
        v = POWER_MODES[name]
        self._write(0x79, u32(OPT_POWER, v), what=f"power mode {name}")
        if save:
            self._save(power_mode=name)

    def set_fan_mode(self, name, save=True):
        if name not in self.fan_modes():
            raise ValueError(f"fan mode {name} is not supported here ({', '.join(self.fan_modes())})")
        if name == "custom" and not self.state().get("curve"):
            raise ValueError("set a custom curve first")
        if name == "custom":
            return self.set_curve(self.state()["curve"], save=save)
        self._write(0x79, u32(OPT_FAN_MODE, FAN_MODES[name]), what=f"fan mode {name}")
        if save:
            self._save(fan_mode=name)

    def set_fan_offset(self, pct, save=True):
        pct = int(pct)
        if not 0 <= pct <= 100:
            raise ValueError("offset 0..100 %")
        self._write(0x79, u32(OPT_FAN_OFFSET, pct2raw(pct)), what=f"fan offset {pct} %")
        if save:
            self._save(fan_offset=pct)

    def set_curve(self, curves, save=True):
        if "custom" not in self.fan_modes():
            raise ValueError("custom fan curves are not supported here")
        defaults = self.table.get("curves") or {}
        clean = {}
        for name, pts in (curves or {}).items():
            if name not in FANS:
                raise ValueError(f"fan {name}")
            clean[name] = check_curve(pts)
            if defaults.get(name):
                clean[name][0] = list(defaults[name][0])          # the first point is the factory one
                check_curve(clean[name])
        if not clean:
            raise ValueError("no curve")
        self._write(0x0E, build_curve(clean, defaults), 256, what="custom fan curve")
        self._write(0x79, u32(OPT_FAN_MODE, FAN_MODES["custom"]), what="fan mode custom")
        if save:
            self._save(curve=clean, fan_mode="custom")

    def fan_defaults(self):
        self._write(0x79, u32(OPT_FAN_DEFAULT, 1), what="factory fan curve")
        self._save(_drop=("curve",), fan_mode="auto")

    def anti_dust(self):
        if not self.caps.get("anti_dust"):
            raise ValueError("anti-dust is not supported here")
        self._write(0x79, u32(OPT_ANTIDUST, 1), what="anti-dust")

    def kb_power(self, on, save=True):
        self._write(0x67, u32(0xE0, 0x010000 if on else 0), what=f"backlight {'on' if on else 'off'}")
        if save:
            self._save(kb={"on": bool(on)})

    def kb_color(self, rgb, zone=None, save=True):
        r, g, b = (int(x) & 0xFF for x in rgb)
        zones = [0] if zone is None else [int(zone)]
        for z in zones:
            if not 0 <= z <= 3:
                raise ValueError("zone 0..3")
            self._write(0x67, u32(0xF0 + z, (b << 16) | (r << 8) | g), what=f"colour zone {z}")
        if save:
            self._save(_drop=("kb.effect",), kb={"color" if zone is None else f"color{zone}": [r, g, b]})

    def kb_brightness(self, level, save=True):
        level = int(level)
        if not 0 <= level <= 255:
            raise ValueError("brightness 0..255")
        self._write(0x67, u32(0xF4, level), what=f"brightness {level}")
        if save:
            self._save(kb={"brightness": level})

    def kb_effect(self, name, save=True):
        self._write(0x67, u32(KB_EFFECTS[name]), what=f"effect {name}")
        if save:
            self._save(kb={"effect": name})      # colour stays: it is sent again when the effect is left

    def kb_sleep(self, seconds, save=True):
        seconds = int(seconds)
        if seconds <= 0:
            self._write(0x79, u32(OPT_KB_SLEEP, 0), what="backlight sleep off")
        else:
            seconds = min(seconds, 0xFFFF)
            self._write(0x79, u32(OPT_KB_SLEEP, (seconds << 8) | 0xFF), what=f"backlight sleep {seconds} s")
        if save:
            self._save(kb={"sleep": max(0, seconds)})

    def boot_effect(self, off, save=True):
        """Control Center 3 "override boot effect": True = no colour cycle at power-on."""
        self._write(0x79, u32(OPT_BOOT_FX, 1 if off else 0), what=f"boot effect {'off' if off else 'on'}")
        if save:
            self._save(kb={"boot_effect_off": bool(off)})

    def command(self, b):
        """POST /api/clevo: one action per request."""
        a = str(b.get("action", ""))
        if a == "power_mode":
            self.set_power_mode(str(b["mode"]))
        elif a == "fan_mode":
            self.set_fan_mode(str(b["mode"]))
        elif a == "fan_offset":
            self.set_fan_offset(b["value"])
        elif a == "curve":
            self.set_curve(b["curves"])
        elif a == "fan_defaults":
            self.fan_defaults()
        elif a == "anti_dust":
            self.anti_dust()
        elif a == "kb_power":
            self.kb_power(bool(b["on"]))
        elif a == "kb_color":
            c = b["color"]
            if isinstance(c, str):
                c = bytes.fromhex(c.lstrip("#"))
            self.kb_color(list(c), b.get("zone"))
        elif a == "kb_brightness":
            self.kb_brightness(b["value"])
        elif a == "kb_effect":
            self.kb_effect(str(b["effect"]))
        elif a == "kb_sleep":
            self.kb_sleep(b["seconds"])
        elif a == "boot_effect":
            self.boot_effect(bool(b["off"]))
        else:
            raise KeyError(f"action {a}")
        self.emit("clevo", {})
        return self.status()
