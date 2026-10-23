"""Switches — port of MySettingManager (base) + BatteryProtection2."""
import glob
import logging
import os
import subprocess
import sys

from . import regs as R

IS_WIN = sys.platform == "win32"
log = logging.getLogger("uwccd.settings")


class SettingsManager:
    def __init__(self, ec, platform, nvram, store, notify):
        self.ec = ec
        self.pf = platform
        self.nvram = nvram
        self.st = store
        self.notify = notify
        self.bios_fn = 0xFF
        self.ac_recovery_bios = False
        self.dgpu_direct_support = False

    # -- startup (MySettingManager.Init) ------------------------------------------
    def start(self):
        cam = self.st.get("webcam")
        if cam is False:
            self.set_webcam(False, save=False)
        usb = self.st.get("usb_charger")
        if usb is not None:
            self.set_usb_charger(usb, save=False)
        wk = self.st.get("winkey_lock")
        if wk is not None:
            self._winkey(wk)
        tp = self.st.get("touchpad_toggle")
        if tp is not None:
            self.set_touchpad_toggle(tp, save=False)
        if self.nvram.verified:
            f = self.nvram.fields()
            self.ac_recovery_bios = f.get("ACRecoverySupport") == 1
            self.dgpu_direct_support = f.get("OemDisplayMode", 0xFF) != 0xFF
            self.bios_fn = f.get("FnKeyStatus", 0xFF)
        if self.bios_fn != 0xFF:
            self._fn(1 if self.bios_fn else 0)
        else:
            self._fn(1 if self.st.get("fn_lock", 0) else 0)

    # -- Win key (0x768 bit0 status, 0x767 bit0 trigger) -----------------------------
    def winkey_locked(self):
        return bool(self.ec.read(R.STATUS_768) & 1)

    def _winkey(self, lock):
        if self.winkey_locked() != bool(lock):
            v = self.ec.read(R.TRIGGER_767)
            self.ec.write(R.TRIGGER_767, (v & 0xFE) + 1)

    def set_winkey(self, lock):
        self._winkey(lock)
        self.st.set("winkey_lock", bool(lock))
        self.notify("setting", {"winkey_lock": bool(lock)})

    # -- Fn lock (0x74E bit4 + NVRAM FnKeyStatus) --------------------------------------
    def fn_locked(self):
        return bool(self.ec.read(R.FN_LOCK) & 0x10)

    def _fn(self, on):
        self.ec.set_bit(R.FN_LOCK, 4, bool(on))

    def set_fn_lock(self, on):
        self.st.set("fn_lock", 1 if on else 0)
        if self.bios_fn != 0xFF:
            self.nvram.set("FnKeyStatus", 1 if on else 0)
            self.bios_fn = 1 if on else 0
        self._fn(on)
        self.notify("setting", {"fn_lock": bool(on)})

    # -- USB charging in sleep (0x767 bit4) --------------------------------------------
    def usb_charger(self):
        return bool(self.ec.read(R.TRIGGER_767) & 0x10)

    def set_usb_charger(self, on, save=True):
        self.ec.set_bit(R.TRIGGER_767, 4, bool(on))
        if save:
            self.st.set("usb_charger", bool(on))

    # -- touchpad toggle function (0x7A6 bit6 = disabled) ---------------------------------
    def touchpad_toggle(self):
        return not (self.ec.read(R.TOUCHPAD) & 0x40)

    def set_touchpad_toggle(self, on, save=True):
        self.ec.set_bit(R.TOUCHPAD, 6, not on)
        if save:
            self.st.set("touchpad_toggle", bool(on))

    def touchpad_led(self):
        return bool(self.ec.read(R.TOUCHPAD) & 0x08)

    def set_touchpad(self, on):
        """TOUCHPAD_LED_ON/OFF: switches the touchpad (done by the user agent) and its LED."""
        self.ec.set_bit(R.TOUCHPAD, 3, bool(on))
        self.st.set("touchpad_enabled", bool(on))
        self.notify("touchpad", {"enabled": bool(on)})

    # -- AC recovery (power on when AC is plugged) ------------------------------------------
    def ac_recovery(self):
        if self.ac_recovery_bios:
            return self.nvram.get("ACRecoveryStatus") == 1
        return bool(self.ec.read(R.BALANCED_PROTECT) & 0x08)

    def set_ac_recovery(self, on):
        if self.ac_recovery_bios:
            self.nvram.set("ACRecoveryStatus", 1 if on else 0)
        else:
            self.ec.set_bit(R.BALANCED_PROTECT, 3, bool(on))

    # -- dGPU direct connection / MUX (NVRAM OemDisplayMode, needs reboot) ---------------------
    def dgpu_direct(self):
        if not self.dgpu_direct_support:
            return None
        v = self.nvram.get("OemDisplayMode")
        return v == 1 if self.pf.amd else v == 2

    def set_dgpu_direct(self, on):
        if not self.dgpu_direct_support:
            raise ValueError("not supported by BIOS")
        val = (1 if on else 0) if self.pf.amd else (2 if on else 4)
        if not self.nvram.set("OemDisplayMode", val):
            raise RuntimeError("NVRAM write failed")
        self.notify("reboot_required", {"reason": "dgpu_direct"})

    # -- light bar ---------------------------------------------------------------------------
    def lightbar_on(self):
        return bool(self.ec.read(R.STATUS_768) & 0x02)

    def lightbar_trigger(self):
        v = self.ec.read(R.TRIGGER_767)
        self.ec.write(R.TRIGGER_767, (v & 0xFD) + 2)

    # -- radio switches (WIFI_/BT_ON/OFF) -> rfkill --------------------------------------------
    @staticmethod
    def rfkill(kind, on):
        if IS_WIN:
            raise NotImplementedError("Wi-Fi / Bluetooth switches: use the Windows quick settings")
        subprocess.run(["rfkill", "unblock" if on else "block", kind], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # -- built-in webcam (USB video class device; disabled = de-authorized on the USB bus) --------------
    @staticmethod
    def webcams():
        if IS_WIN:
            return []
        devs = []
        for intf in glob.glob("/sys/bus/usb/devices/*:*"):
            try:
                if open(os.path.join(intf, "bInterfaceClass")).read().strip() != "0e":
                    continue
            except OSError:
                continue
            dev = os.path.dirname(os.path.realpath(intf))
            if os.path.exists(os.path.join(dev, "authorized")) and dev not in devs:
                devs.append(dev)
        return devs

    def webcam(self):
        if IS_WIN:
            from .win.winplat import webcam_state
            return webcam_state()
        devs = self.webcams()
        if not devs:
            return None if self.st.get("webcam") is not False else False
        try:
            return all(open(os.path.join(d, "authorized")).read().strip() == "1" for d in devs)
        except OSError:
            return None

    def set_webcam(self, on, save=True):
        if IS_WIN:
            from .win.winplat import set_webcam
            set_webcam(bool(on))
            if save:
                self.st.set("webcam", bool(on))
            return
        devs = self.webcams()
        if not devs and save:
            raise ValueError("no USB camera found")
        for d in devs:
            with open(os.path.join(d, "authorized"), "w") as f:
                f.write("1" if on else "0")
        if save:
            self.st.set("webcam", bool(on))

    @staticmethod
    def rfkill_state(kind):
        if IS_WIN:
            return None
        try:
            out = subprocess.run(["rfkill", "-n", "-o", "TYPE,SOFT", "list"], capture_output=True,
                                 text=True, check=False).stdout
            states = [ln.split()[1] for ln in out.splitlines() if ln.split()[:1] == [{"wifi": "wlan"}.get(kind, kind)]]
            return None if not states else all(s == "unblocked" for s in states)
        except OSError:
            return None

    def status(self):
        return {
            "winkey_lock": self.winkey_locked(),
            "fn_lock": self.fn_locked(),
            "usb_charger": self.usb_charger(),
            "touchpad_toggle": self.touchpad_toggle(),
            "touchpad_enabled": self.st.get("touchpad_enabled", True),
            "touchpad_led": self.touchpad_led(),
            "ac_recovery": self.ac_recovery(),
            "ac_recovery_bios": self.ac_recovery_bios,
            "dgpu_direct": self.dgpu_direct(),
            "lightbar_on": self.lightbar_on(),
            "wifi": self.rfkill_state("wifi"),
            "bluetooth": self.rfkill_state("bluetooth"),
            "kb_timeout": self.st.get("kb_timeout", 0),
            "osd": self.st.get("osd", True),
            "debug": bool(self.st.get("debug", False)),
            "tcc_extended": bool(self.st.get("tcc_extended", False)),
            "update_check": bool(self.st.get("update_check", True)),
            "history_record": bool(self.st.get("history_record", True)),
            "lang": self.st.get("lang", "en"),
            "webcam": self.webcam(),
        }


class BatteryManager:
    """BatteryProtection2 — health modes and custom charge limits."""

    HEALTH = {0: (0, 0), 1: (1, 0), 2: (0, 1)}   # high(full) / middle / low -> bits 4,5 of 0x7A6

    def __init__(self, ec, platform, nvram, store):
        self.ec = ec
        self.pf = platform
        self.nvram = nvram
        self.st = store

    def start(self):
        h = self.st.get("battery_health")
        if h is not None:
            self.set_health(h, save=False)
        tc = self.st.get("typec_priority")
        if tc is not None and self.pf.typec_prio_support:
            self.set_typec_priority(tc, save=False)

    def health(self):
        v = self.ec.read(R.TOUCHPAD)
        b4, b5 = (v >> 4) & 1, (v >> 5) & 1
        return 1 if b4 else (2 if b5 else 0)

    def set_health(self, mode, save=True):
        b4, b5 = self.HEALTH[int(mode)]
        self.ec.update(R.TOUCHPAD, 0x30, (b4 << 4) | (b5 << 5))
        if save:
            self.st.set("battery_health", int(mode))

    def limit_up(self):
        v = self.ec.read(R.CHARGE_LIMIT_UP) & 0x7F
        return 100 if v == 0 else v

    def limit_down(self):
        v = self.ec.read(R.CHARGE_LIMIT_DOWN)
        return 95 if v == 0 else v

    def set_limits(self, up=None, down=None, mode=None):
        if up is not None:
            up = int(up)
            if not 1 <= up <= 100:
                raise ValueError("upper limit 1..100")
            v = self.ec.read(R.CHARGE_LIMIT_UP) & 0x80
            self.ec.write(R.CHARGE_LIMIT_UP, v if up == 100 else v + up)
            self.nvram.set("ChargeMaximumLimit", up)
        if down is not None:
            down = int(down)
            if 1 <= down <= 95:
                v = self.ec.read(R.CHARGE_LIMIT_DOWN) & 0x80
                self.ec.write(R.CHARGE_LIMIT_DOWN, v + down)
                self.nvram.set("ChargeMinimumLimit", down)
        if mode is not None:
            self.nvram.set("BatteryLimitation", int(mode))

    def typec_priority(self):
        return bool(self.ec.read(R.TYPEC_PRIO) & 0x80) if self.pf.typec_prio_support else None

    def set_typec_priority(self, on, save=True):
        self.ec.set_bit(R.TYPEC_PRIO, 7, bool(on))
        if save:
            self.st.set("typec_priority", bool(on))

    def status(self):
        return {
            "health_mode": self.health(),
            "limit_up": self.limit_up(),
            "limit_down": self.limit_down(),
            "cycle_count": self.ec.read16(R.BAT_CYCLE_L, R.BAT_CYCLE_L + 1),
            "design_voltage_mv": self.ec.read16(R.BAT_DESIGN_VOLT_L, R.BAT_DESIGN_VOLT_L + 1),
            "alert": bool(self.ec.read(R.BAT_ALERT)),
            "typec_priority": self.typec_priority(),
            "typec_priority_support": self.pf.typec_prio_support,
        }
