"""Keyboard backlight manager: ITE RGB (KeyboardType '1') or EC single colour ('2')."""
import logging
import threading

from .. import regs as R
from . import ite

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
        self.single = None
        self.kind = "none"
        self.lock = threading.RLock()
        self.idle_off = False

    def start(self):
        self.rgb = ite.open_keyboard(self.ec, mock=self.mock)
        if self.rgb:
            self.kind = "rgb"
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
            try:
                if saved:
                    self.rgb.set_effect(**saved)
                if not power:
                    self.rgb.set_power(False)
            except (NotImplementedError, ValueError, OSError) as e:
                log.warning("restore keyboard effect: %s", e)
        elif self.pf.project_id in (0x12, 0x13, 0x14) or self.st.get("force_single_color"):
            self.single = SingleColor(self.ec)
            self.kind = "single"
            lvl = self.st.get("kb_single_level")
            if lvl is not None:
                self.single.set_level(lvl)
            if self.st.get("kb_power") is False:
                self.single.set_power(False)
        log.info("keyboard backlight: %s", self.kind)

    # -- API -------------------------------------------------------------------------
    def set_effect(self, **kw):
        if self.kind != "rgb":
            raise ValueError("no RGB keyboard")
        with self.lock:
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

    def idle(self, idle):
        """KeyboardCloseTimer: switch the backlight off after inactivity, back on at input."""
        if not self.st.get("kb_power", True):
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
                                     if c == 0x22 or (c in ite.LB_ONLY_EFFECTS and not (self.rgb and self.rgb.kb_type in ite.ME_LIGHTBAR))],
             "default_colors": ite.DEFAULT_COLORS}
        if self.kind == "rgb":
            d["effect"] = self.rgb.saved
            d["device"] = self.rgb.info()
        elif self.kind == "single":
            d["level"] = self.single.level()
            d["power"] = self.single.power()
        return d
