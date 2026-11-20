"""Switches — port of MySettingManager (base) + BatteryProtection2."""
import glob
import logging
import os
import subprocess
import sys
import threading

from . import EULA_VERSION
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
        # RAM overclocking (MemorySettings.MemoryOverClockSwitch of the original): the BIOS publishes support in
        # UniWillVariable.MemoryOverClockSupport and applies MemoryOverClockSwitch at the next start
        self.mem_oc_support = bool(nvram and nvram.verified and nvram.get("MemoryOverClockSupport") == 1)
        self.mem_oc_boot = nvram.get("MemoryOverClockSwitch") if self.mem_oc_support else None

    # -- RAM overclocking -------------------------------------------------------------
    def mem_oc(self):
        return bool(self.nvram.get("MemoryOverClockSwitch")) if self.mem_oc_support else False

    def mem_oc_pending(self):
        return self.mem_oc_support and self.nvram.get("MemoryOverClockSwitch") != self.mem_oc_boot

    def set_mem_oc(self, on):
        if not self.mem_oc_support:
            raise ValueError("the BIOS of this laptop does not report RAM overclocking support")
        if not self.nvram.set("MemoryOverClockSwitch", 1 if on else 0):
            raise ValueError("the BIOS variable could not be written")
        log.info("RAM overclocking %s in the BIOS variable — applied at the next start", "on" if on else "off")
        self.notify("mem_oc", {"on": bool(on), "pending": self.mem_oc_pending()})

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

    def set_lightbar(self, on):
        """Light bar power through the EC: the trigger toggles it, so it is sent only when the state differs."""
        if self.lightbar_on() != bool(on):
            self.lightbar_trigger()

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
            "update_minor": bool(self.st.get("update_minor", True)),        # 1.7.6.0: offer 4th-number releases
            "history_record": bool(self.st.get("history_record", True)),
            "profile_autoapply": bool(self.st.get("profile_autoapply", True)),     # Mode selection: write at once
            "lc_hwoc": bool(self.st.get("lc_hwoc", False)),
            # in the rules (1.8.2.8); 1.9.2.0: on by default — it only works while the Flydigi BS module is on
            "flydigi_automation": bool(self.st.get("flydigi_automation", True)),
            "flydigi_intro_seen": bool(self.st.get("flydigi_intro_seen", False)),   # the page's first-visit note
            "eula_accepted": int(self.st.get("eula_accepted", 0) or 0), "eula_version": EULA_VERSION,
            "mem_oc_support": self.mem_oc_support, "mem_oc": self.mem_oc(), "mem_oc_pending": self.mem_oc_pending(),
            "lang": self.st.get("lang", "en"),
            # 1.9.0.0: the window asks for the language once; an installation that already ran counts as chosen
            "lang_chosen": bool(self.st.get("lang_chosen") or self.st.get("lang") or self.st.get("eula_accepted")),
            "fan_manager": self.st.get("fan_manager", "auto"),
            "webcam": self.webcam(),
        }


class BatteryManager:
    """BatteryProtection2 — health modes and custom charge limits.

    1.8.2.2 (MECHREVO Aurora X: set to balanced + 90/85 %, charged to 100 %):
      * the EC may change the protection mode when a charger is plugged in, and keeps 0x7B9 only until sleep — the
        mode and the limits are written again on every AC change (twice: at once and a few seconds later) and after
        resume, as the Linux kernel driver uniwill-laptop does;
      * bit7 of 0x7B9 is the EC's "limit reached" flag (kernel: CHARGE_CTRL_REACHED), not ours to write back;
      * Uniwill boards have EITHER the charge limit (0x7B9) OR the protection modes (0x7A6 bits4..5) — never both;
        when the kernel driver is loaded it knows which one (charge_control_end_threshold vs charge_types in the
        battery's sysfs folder): the other one is reported unavailable, and changes go through the driver's file so
        that its own copy (restored by the driver on AC change and resume) matches ours.

    1.9.2.1 (the same Aurora X with 1.8.2.2: 0x7A6 = balanced AND 0x7B9 = 90 — the EC never set "limit reached" and
    charged to 100 %): the two exclude each other here too. Choosing a protection mode other than full capacity
    clears the limit (0x7B9 = 0, i.e. 100 %); applying a limit below 100 % sets the mode to full capacity. Only the
    chosen one is kept and written again; a configuration with both (saved by 1.8.2.2) keeps the mode.
    """

    HEALTH = {0: (0, 0), 1: (1, 0), 2: (0, 1)}   # high(full) / middle / low -> bits 4,5 of 0x7A6
    KERNEL_TYPES = {0: "Standard", 1: "Long Life", 2: "Trickle"}     # POWER_SUPPLY_CHARGE_TYPE_* of uniwill-laptop
    SYS_PS = "/sys/class/power_supply"
    SYS_MOD = "/sys/module/uniwill_laptop"

    def __init__(self, ec, platform, nvram, store):
        self.ec = ec
        self.pf = platform
        self.nvram = nvram
        self.st = store

    # -- the kernel driver uniwill-laptop (Linux) ------------------------------------------------------------
    def _kernel_bat(self):
        """The battery's sysfs folder when the kernel's uniwill-laptop driver is loaded, else None."""
        if sys.platform == "win32" or not os.path.isdir(self.SYS_MOD):
            return None
        for d in sorted(glob.glob(os.path.join(self.SYS_PS, "BAT*"))):
            if os.path.isfile(os.path.join(d, "charge_types")) or \
                    os.path.isfile(os.path.join(d, "charge_control_end_threshold")):
                return d
        return None

    def kernel_kind(self):
        """"modes" / "limit" — what the kernel driver offers on this laptop — or None (no driver)."""
        d = self._kernel_bat()
        if not d:
            return None
        return "limit" if os.path.isfile(os.path.join(d, "charge_control_end_threshold")) else "modes"

    def _kernel_write(self, name, value):
        d = self._kernel_bat()
        if not d or not os.path.isfile(os.path.join(d, name)):
            return False
        try:
            with open(os.path.join(d, name), "w") as f:
                f.write(str(value))
            return True
        except OSError as e:
            log.warning("battery: %s/%s <- %s: %s", d, name, value, e)
            return False

    def start(self):
        if self.st.get("battery_limits") is None:          # set before 1.8.2.2: keep what the EC holds now
            up, down = self.limit_up(), self.limit_down()
            self.st.set("battery_limits", {"up": up, "down": down} if up != 100 else {})
        self.reapply()
        tc = self.st.get("typec_priority")
        if tc is not None and self.pf.typec_prio_support:
            self.set_typec_priority(tc, save=False)

    def health(self):
        v = self.ec.read(R.TOUCHPAD)
        b4, b5 = (v >> 4) & 1, (v >> 5) & 1
        return 1 if b4 else (2 if b5 else 0)

    def set_health(self, mode, save=True):
        mode = int(mode)
        b4, b5 = self.HEALTH[mode]
        if mode and self.limit_up() != 100:              # 1.9.2.1: a mode and a limit exclude each other
            self._write_limits(100, None)
            if save:
                self.st.set("battery_limits", {})
        self._kernel_write("charge_types", self.KERNEL_TYPES[mode])       # keeps the driver's own copy in step
        self.ec.update(R.TOUCHPAD, 0x30, (b4 << 4) | (b5 << 5))
        if save:
            self.st.set("battery_health", mode)

    def active(self):
        """What protects the battery now: "mode" (balanced / stationary), "limit" (below 100 %) or None."""
        if self.health():
            return "mode"
        return "limit" if self.limit_up() != 100 else None

    def reapply(self, why=""):
        """Write the saved protection mode and charge limits again (start, resume, AC change)."""
        h = self.st.get("battery_health")
        lim = self.st.get("battery_limits")
        if h and lim and lim.get("up") not in (None, 100):         # both saved (1.8.2.2): the mode wins (1.9.2.1)
            log.warning("battery: protection mode %s and limit %s %% exclude each other — the limit is cleared",
                        h, lim.get("up"))
            lim = {"up": 100, "down": lim.get("down")} if lim.get("down") is not None else {"up": 100}
            self.st.set("battery_limits", {})
        try:
            if h is not None:
                self.set_health(h, save=False)
            if lim:
                self._write_limits(lim.get("up"), lim.get("down"))
        except Exception as e:  # noqa: BLE001
            log.warning("battery: re-applying failed: %s", e)
            return
        if why and (h is not None or lim):
            log.info("battery: protection mode %s%s re-applied (%s)", h,
                     f", limits {lim.get('up')}/{lim.get('down')} %" if lim else "", why)

    def on_ac_change(self, online):
        """The EC may switch the mode itself right after a charger is plugged in: write it now and once more later."""
        self.reapply("AC " + ("online" if online else "offline"))
        t = threading.Timer(6.0, self.reapply)
        t.daemon = True
        t.start()

    def limit_up(self):
        v = self.ec.read(R.CHARGE_LIMIT_UP) & 0x7F
        return 100 if v == 0 else v

    def limit_down(self):
        v = self.ec.read(R.CHARGE_LIMIT_DOWN)
        return 95 if v == 0 else v

    def _write_limits(self, up=None, down=None):
        if up is not None:
            # bits0..6 the limit (0 = 100 %); bit7 is set by the EC when the limit is reached — never written back
            self.ec.write(R.CHARGE_LIMIT_UP, 0 if up == 100 else up)
            self._kernel_write("charge_control_end_threshold", up)
        if down is not None:
            v = self.ec.read(R.CHARGE_LIMIT_DOWN) & 0x80
            self.ec.write(R.CHARGE_LIMIT_DOWN, v + down)

    def set_limits(self, up=None, down=None, mode=None):
        if up is not None:
            up = int(up)
            if not 1 <= up <= 100:
                raise ValueError("upper limit 1..100")
        if down is not None:
            down = int(down)
            if not 1 <= down <= 95:
                down = None
        if up is not None and up != 100 and self.health():          # 1.9.2.1: a limit replaces the protection mode
            self.set_health(0)
        self._write_limits(up, down)
        if up is not None or down is not None:
            lim = dict(self.st.get("battery_limits") or {})
            if up is not None:
                lim["up"] = up
                self.nvram.set("ChargeMaximumLimit", up)
            if down is not None:
                lim["down"] = down
                self.nvram.set("ChargeMinimumLimit", down)
            self.st.set("battery_limits", lim)
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
            "active": self.active(),
            "limit_up": self.limit_up(),
            "limit_down": self.limit_down(),
            "cycle_count": self.ec.read16(R.BAT_CYCLE_L, R.BAT_CYCLE_L + 1),
            "design_voltage_mv": self.ec.read16(R.BAT_DESIGN_VOLT_L, R.BAT_DESIGN_VOLT_L + 1),
            "alert": bool(self.ec.read(R.BAT_ALERT)),
            "typec_priority": self.typec_priority(),
            "typec_priority_support": self.pf.typec_prio_support,
            "limit_reached": bool(self.ec.read(R.CHARGE_LIMIT_UP) & 0x80),
            "kernel": self.kernel_kind(),
        }
