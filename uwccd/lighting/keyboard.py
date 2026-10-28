"""Keyboard backlight manager: ITE RGB (KeyboardType '1') or EC single colour ('2')."""
import logging
import threading
import time

from .. import regs as R
from ..hw import SINGLE_COLOR_EC_IDS
from . import fx, ite

log = logging.getLogger("uwccd.kb")


class SingleColor:
    """MyControlCenter.SingleColorKeyboard — EC 0x78C."""

    def __init__(self, ec):
        self.ec = ec

    def power(self):
        return not (self.ec.read(R.KB_SINGLE) & 0x02)

    def set_power(self, on):
        v = self.ec.read(R.KB_SINGLE)
        self.ec.write(R.KB_SINGLE, (v & 0xFD) if on else (v | 0x02))

    def level(self):
        return self.ec.read(R.KB_SINGLE) >> 5

    def set_level(self, lvl):
        v = (self.ec.read(R.KB_SINGLE) | 0x10) & 0x1F
        self.ec.write(R.KB_SINGLE, v | ((int(lvl) & 7) << 5))


class KeyboardManager:
    def __init__(self, ec, platform, store, mock=False):
        self.ec = ec
        self.pf = platform
        self.st = store
        self.mock = mock
        self.rgb = None
        self.lb = None             # chassis light bar (separate ITE device)
        self.single = None
        self.kind = "none"
        self.lock = threading.RLock()
        self.idle_off = False
        # BetterRGB effects: power source and service metrics (set by the service), values from the user session
        self.ac_fn = lambda: True
        self.metrics_fn = lambda: {}
        self.session = {}             # key -> (value, time): volume / mic / audio from the tray or the agent
        self._metrics = (0.0, {})

    # -- BetterRGB effects ---------------------------------------------------------------
    def fx_config(self):
        return fx.clean_config(self.st.get("kb_fx"))

    def fx_env(self):
        now = time.monotonic()
        t, m = self._metrics
        if now - t > 1.0:
            try:
                m = dict(self.metrics_fn() or {})
            except Exception:  # noqa: BLE001
                m = {}
            self._metrics = (now, m)
        m = dict(m)
        for k, (v, ts) in list(self.session.items()):
            if now - ts < 3.0:
                m[k] = v
        try:
            ac = bool(self.ac_fn())
        except Exception:  # noqa: BLE001
            ac = True
        return {"config": self.fx_config(), "ac": ac, "metrics": m}

    def engine(self):
        return self.rgb.fx() if self.rgb else None

    def set_fx_config(self, upd):
        cur = self.fx_config()
        for k, v in (upd or {}).items():
            if k == "bar" and isinstance(v, dict):
                cur["bar"] = {**cur["bar"], **v}
            elif k in fx.DEFAULT_CONFIG:
                cur[k] = v
        cur = fx.clean_config(cur)
        self.st.set("kb_fx", cur)
        return cur

    def fx_input(self, keys=None, screen=None, metrics=None):
        """input from the user session: pressed keys (names), a small screen picture, audio levels"""
        e = self.engine()
        if keys and e:
            e.press([str(k)[:16] for k in keys[:64]])
        if screen and e:
            e.feed_screen(fx.decode_screen(screen))
        if metrics:
            now = time.monotonic()
            for k in ("volume", "mic", "audio"):
                if metrics.get(k) is not None:
                    self.session[k] = (max(0.0, min(1.0, float(metrics[k]))), now)
        return {"needs": e.needs() if e else []}

    def fx_calibrate(self, action, observed=None):
        """white calibration: start (raw white on the keys) -> apply (the colour seen) | cancel | reset"""
        e = self.engine()
        if action == "start":
            if not e:
                raise ValueError("start a BetterRGB effect first — the calibration shows raw white through it")
            e.calibrate(True)
        elif action == "cancel":
            if e:
                e.calibrate(False)
        elif action == "apply":
            gains = fx.white_gains(observed or [])
            if not gains:
                raise ValueError("the colour is too dark to calibrate")
            self.set_fx_config({"gains": gains})
            if e:
                e.calibrate(False)
        elif action == "reset":
            self.set_fx_config({"gains": [1000, 1000, 1000]})
            if e:
                e.calibrate(False)
        else:
            raise ValueError("action: start | apply | cancel | reset")
        return {"gains": self.fx_config()["gains"], "calibrating": bool(e and e.calibrating)}

    def needs_keys(self):
        e = self.engine()
        return bool(e and "keys" in e.needs())

    def start(self):
        self.rgb = ite.open_keyboard(self.ec, mock=self.mock)
        if self.rgb:
            self.kind = "rgb"
            self.rgb.fx_env = self.fx_env
            try:
                ec_caps = self.ec.read(R.EC_CAPS_742)
                vendor = 4
                if ec_caps & 0x04:
                    vendor = 0
                elif ec_caps & 0x08:
                    vendor = 1
                elif ec_caps & 0x40:
                    vendor = 2
                elif ec_caps & 0x80:
                    vendor = 3
                elif self.ec.read(R.LED_VENDOR_2) & 0x80:
                    vendor = 4
                from .oem import wkdcolor
                wkdcolor.set_vendor(vendor)
            except Exception as e:  # noqa: BLE001
                log.debug("LED vendor: %s", e)
            saved = self.st.get("kb_effect")
            power = self.st.get("kb_power", True)
            self.rgb.pictures_ok = not self.picture_modes_blocked()
            try:
                if saved:
                    self.rgb.set_effect(**saved, force=True)
                if not power:
                    self.rgb.set_power(False)
            except (NotImplementedError, ValueError, OSError) as e:
                log.warning("restore keyboard effect: %s", e)
        elif self.pf.project_id in SINGLE_COLOR_EC_IDS or self.st.get("force_single_color"):
            self.single = SingleColor(self.ec)
            self.kind = "single"
            lvl = self.st.get("kb_single_level")
            if lvl is not None:
                self.single.set_level(lvl)
            if self.st.get("kb_power") is False:
                self.single.set_power(False)
        log.info("keyboard backlight: %s", self.kind)
        try:
            self.lb = ite.open_lightbar(self.ec, mock=self.mock)
        except OSError as e:
            log.warning("light bar: %s", e)
        if self.lb:
            for zone, cfg in (self.st.get("lightbar") or {}).items():
                if zone not in self.lb.zones:
                    continue
                try:
                    if cfg.get("effect"):
                        self.lb.set_zone(zone, **{k: cfg[k] for k in ("effect", "light", "speed", "colors") if k in cfg})
                    if cfg.get("power") is False:
                        self.lb.set_zone_power(zone, False)
                except (ValueError, OSError) as e:
                    log.warning("restore light bar %s: %s", zone, e)

    # -- API -------------------------------------------------------------------------
    def picture_modes_blocked(self):
        """User mode (per-key colours) and the gaming zones are drawn as 12h/16h pictures. On ITE firmware 0x11
        (MAIBENBEN Tsunami) they looked ignored — that was the 08h reset sent before them (removed in 1.5.4), the
        original draws single colour the same way there. They can still be hidden (setting kb_picture_modes off)."""
        if self.rgb and self.rgb.four_zone():
            return True                       # no per-key LEDs at all
        return bool(self.rgb and self.rgb.ver[0] == 0x11 and not self.rgb.fw_effects()
                    and self.st.get("kb_picture_modes", True) is False)

    def set_effect(self, **kw):
        if self.kind != "rgb":
            raise ValueError("no RGB keyboard")
        blocked = self.picture_modes_blocked()
        code = ite.EFFECTS.get(kw.get("idx"), (None, None))[1]
        zone_soft = bool(self.rgb.four_zone() and code in ite.FOUR_ZONE_SOFT)     # drawn zone by zone
        if fx.is_fx(kw.get("idx")):
            kw = {k: kw[k] for k in ("idx", "light", "fx", "force") if k in kw}
        elif blocked and not zone_soft and (kw.get("idx") in (14, 15) or code in ite.AP_EFFECTS):
            raise ValueError("this keyboard does not support per-key / gaming modes (see Settings to try anyway)")
        with self.lock:
            self.rgb.pictures_ok = not blocked      # single colour falls back to the firmware static effect
            self.rgb.set_effect(**kw)
            self.st.set("kb_effect", self.rgb.saved)
            self.st.set("kb_power", True)

    def set_power(self, on):
        with self.lock:
            if self.kind == "rgb":
                self.rgb.set_power(on)
            elif self.kind == "single":
                self.single.set_power(on)
            self.st.set("kb_power", bool(on))

    def set_level(self, lvl):
        if self.kind == "single":
            self.single.set_level(lvl)
            self.st.set("kb_single_level", int(lvl))
        elif self.kind == "rgb":
            self.rgb.set_brightness(int(lvl))
            self.st.set("kb_effect", self.rgb.saved)

    def lightbar(self, zone, power=None, **effect):
        if not self.lb:
            raise ValueError("no light bar")
        if zone not in self.lb.zones:
            raise ValueError(f"this light bar has no '{zone}' zone ({', '.join(self.lb.zones)})")
        effect = {k: v for k, v in effect.items() if v is not None}
        with self.lock:
            if effect:
                cur = {k: v for k, v in (self.lb.saved.get(zone) or {}).items() if k != "power"}
                cur.update(effect)
                self.lb.set_zone(zone, **cur)
            if power is not None:
                self.lb.set_zone_power(zone, bool(power))
            self.st.set("lightbar", {z: dict(v) for z, v in self.lb.saved.items()})

    def idle(self, idle):
        """KeyboardCloseTimer: switch the backlight off after inactivity, back on at input."""
        if not self.st.get("kb_power", True):
            return
        e = self.engine()
        if e and self.fx_config()["transition"] != "off":
            e.set_idle(idle)              # BetterRGB: the transition fades the keys out and back in
            self.idle_off = bool(idle)
            return
        with self.lock:
            if idle and not self.idle_off:
                self.idle_off = True
                if self.kind == "rgb":
                    self.rgb.set_power(False)
                elif self.kind == "single":
                    self.single.set_power(False)
            elif not idle and self.idle_off:
                self.idle_off = False
                if self.kind == "rgb":
                    self.rgb.set_power(True)
                elif self.kind == "single":
                    self.single.set_power(True)

    def status(self):
        d = {"kind": self.kind, "power": self.st.get("kb_power", True),
             "effects": {i: n for i, (n, _) in ite.EFFECTS.items()},
             "software_effects": [i for i, (_, c) in ite.EFFECTS.items() if c in ite.AP_EFFECTS],
             "unsupported_effects": [i for i, (_, c) in ite.EFFECTS.items()
                                     if c == 0x22 or (c in ite.LB_ONLY_EFFECTS and not (self.rgb and self.rgb.kb_type in ite.ME_LIGHTBAR))
                                     or ((i in (14, 15) or c in ite.AP_EFFECTS) and self.picture_modes_blocked()
                                         and not (self.rgb and self.rgb.four_zone() and c in ite.FOUR_ZONE_SOFT))
                                     or (self.rgb and self.rgb.four_zone()
                                         and c not in ite.FOUR_ZONE_EFFECTS | ite.FOUR_ZONE_SOFT)],
             "four_zone": bool(self.rgb and self.rgb.four_zone()),
             "unchecked_effects": [i for i, (_, c) in ite.EFFECTS.items() if self.rgb and self.rgb.four_zone()
                                   and c in ite.FOUR_ZONE_EFFECTS and c not in ite.FOUR_ZONE_CHECKED],
             "picture_modes_blocked": self.picture_modes_blocked(),
             "picture_modes_switch": bool(self.rgb and not self.rgb.four_zone() and self.rgb.ver[0] == 0x11
                                          and not self.rgb.fw_effects()),
             "default_colors": ite.DEFAULT_COLORS,
             "fx_effects": fx.catalog(), "fx_config": self.fx_config(), "fx_transitions": fx.TRANSITIONS,
             "fx_bar_modes": fx.BAR_MODES, "fx_bar_directions": fx.BAR_DIRECTIONS,
             "fx": self.engine().info() if self.engine() else None}
        if self.lb:
            d["lightbar"] = {"device": self.lb.info(), "effects": list(ite.LB_EFFECTS),
                             "zones": {z: {"power": True, "effect": "static", "light": 4, "speed": 2,
                                           "colors": [[255, 255, 255]], **(self.lb.saved.get(z) or {})}
                                       for z in self.lb.zones}}
        if self.kind == "rgb":
            d["effect"] = self.rgb.saved
            d["device"] = self.rgb.info()
        elif self.kind == "single":
            d["level"] = self.single.level()
            d["power"] = self.single.power()
        return d
