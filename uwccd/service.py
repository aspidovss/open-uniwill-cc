"""Service core — the Linux counterpart of GCUService (MyControlCenter.App)."""
import json
import os
import logging
import queue
import sys
import threading
import time

from . import regs as R
from . import store
from .ec import open_ec
from .automation import DEFAULTS as AUTO_DEFAULTS, PowerSourceRules, Sampler, setting as auto_setting
from .events import AppBinding, ECPoller, HotkeyEvents, IdleTimer
from .fan import PowerManager
from .fan_std import PowerManagerStd
from .hw import Platform
from .lighting.keyboard import KeyboardManager
from .monitor import Monitor
from .nvram import Nvram
from .settings import BatteryManager, SettingsManager
from .watercooler import LiquidCooler

IS_WIN = sys.platform == "win32"
log = logging.getLogger("uwccd")



def apply_debug(on):
    """Verbose (DEBUG) logging for the whole service: setting "debug" (UI / uwccctl debug on) or UWCC_DEBUG=1.
    Turning it off restores the level the service was started with (-v keeps DEBUG)."""
    root = logging.getLogger()
    if not hasattr(apply_debug, "base"):
        apply_debug.base = root.level
    level = logging.DEBUG if on else apply_debug.base
    root.setLevel(level)
    for h in root.handlers:
        h.setLevel(logging.NOTSET)
    if on:
        log.info("debug logging on")


class Service:
    def __init__(self, backend=None, mock=False):
        self.mock = mock
        self.ec = open_ec("mock" if mock else backend)
        self.pf = Platform(self.ec)
        log.info("project %s (raw 0x%X), ramfan1.5=%s turbo=%s nv=%s amd=%s", self.pf.project_name,
                 self.pf.project_raw, self.pf.ramfan15, self.pf.turbo_support, self.pf.nv_gpu, self.pf.amd)
        self.nvram = Nvram(allow_write=not mock)
        self.nvram.verify(self.pf.project_raw)
        self.settings_store = store.Settings()
        apply_debug(self.settings_store.get("debug", False) or os.environ.get("UWCC_DEBUG") == "1")
        self.listeners = []
        self.llock = threading.Lock()
        # MyFanCtrl: commercial projects -> _CML manager, all others -> RamFan1p5 manager (with Custom mode)
        choice = self.settings_store.get("fan_manager", "auto")
        std = (choice == "std") or (choice != "cml" and not self.pf.commercial)
        self.power = (PowerManagerStd if std else PowerManager)(self.ec, self.pf, self.nvram, self.emit)
        log.info("fan manager: %s (%s)", self.power.manager, "forced" if choice in ("std", "cml") else "by project")
        self.settings = SettingsManager(self.ec, self.pf, self.nvram, self.settings_store, self.emit)
        self.battery = BatteryManager(self.ec, self.pf, self.nvram, self.settings_store)
        self.keyboard = KeyboardManager(self.ec, self.pf, self.settings_store, mock=mock)
        if IS_WIN:          # also with --mock: /proc and /sys do not exist on Windows
            from .win.sysinfo import WinMonitor
            self.monitor = WinMonitor(self.ec, self.pf)
        else:
            self.monitor = Monitor(self.ec, self.pf)
        self.liquid = LiquidCooler(self.ec, self.hottest_temp, self.emit, mock=mock,
                                   mode_fn=lambda: self.power.option.get("OperatingMode") if self.fan_control else None)
        self.sampler = Sampler(self)
        self.rules = PowerSourceRules(self)
        self.threads = []
        self.fan_control = False

    def hottest_temp(self):
        """Temperature driving the cooler's auto mode: the hotter of CPU and NVIDIA GPU."""
        ts = [self.monitor.cpu_temp()]
        if self.pf.nv_gpu:
            ts.append((self.monitor.nvidia() or {}).get("temp"))
        ts = [t for t in ts if isinstance(t, (int, float))]
        return max(ts) if ts else None

    # -- event fan-out to UI / agent (SSE) ------------------------------------------------
    def subscribe(self):
        q = queue.Queue(maxsize=200)
        with self.llock:
            self.listeners.append(q)
        return q

    def unsubscribe(self, q):
        with self.llock:
            if q in self.listeners:
                self.listeners.remove(q)

    def emit(self, kind, data):
        if kind == "mode":
            threading.Thread(target=self.rules.sync_ppd, args=(data.get("mode"),), daemon=True).start()
        msg = json.dumps({"type": kind, "data": data, "t": time.time()})
        with self.llock:
            for q in list(self.listeners):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

    # -- lifecycle -----------------------------------------------------------------------------
    def start(self):
        self.power.ac_online = self.monitor.ac_online()
        self.fan_control = self.pf.ramfan15 or bool(self.settings_store.get("force_fan_control"))
        if self.fan_control:
            self.power.start()
        else:
            log.warning("EC does not report RamFan 1.5 (0x78E bit6). GCUService uses a different fan manager "
                        "on such machines — modes/fan tables are disabled (monitoring, lighting, switches work).")
        self.settings.start()
        self.battery.start()
        self.keyboard.start()
        if IS_WIN and not self.mock:
            from .win.wmievents import WmiHotkeyEvents
            hk = WmiHotkeyEvents(self.on_wmi_event)
        else:
            hk = HotkeyEvents(self.on_wmi_event)
        self.threads.append(hk)
        poll = ECPoller(self.ec, self.monitor, self.on_poll_change, use_ec_bits=not hk.available)
        self.threads.append(poll)
        if not IS_WIN:      # on Windows the tray app reports user idle time (a service cannot see input)
            self.threads.append(IdleTimer(lambda: int(self.settings_store.get("kb_timeout", 0) or 0), self.keyboard.idle))
        self.threads.append(AppBinding(lambda: self.settings_store.get("app_binding", []),
                                       self.power.user_set_mode, lambda: self.power.option["OperatingMode"]))
        self.threads.append(self.sampler)
        for t in self.threads:
            t.start()
        self.liquid.start()
        log.info("service started (hotkeys: %s)", "kernel module" if hk.available else "polling")

    def stop(self):
        self.liquid.stop()
        for t in self.threads:
            getattr(t, "stop").set()
        if self.fan_control:
            self.power.shutdown()          # ApExistFlag in NVRAM stays 1 (cleared only by uninstall)
        if self.keyboard.rgb:
            self.keyboard.rgb.close()
        self.ec.close()

    # -- WMIEC.WMIHandleEvent ---------------------------------------------------------------------
    def on_wmi_event(self, code):
        if code in (R.EV_MODE_SWITCH, R.EV_FAN_BOOST, R.EV_FAN_BOOST_OFF, R.EV_PROTECT) and not self.fan_control:
            self.emit("wmi", {"code": code})
        elif code == R.EV_MODE_SWITCH:
            self.power.mode_switch_key()
        elif code == R.EV_FAN_BOOST:
            self.power.fan_boost_from_ec()
        elif code == R.EV_FAN_BOOST_OFF:
            self.power.fan_boost_from_ec(off=True)
        elif code in (R.EV_WINKEY_LOCK, R.EV_WINKEY_UNLOCK):
            locked = code == R.EV_WINKEY_LOCK
            self.settings_store.set("winkey_lock", locked)
            self.emit("setting", {"winkey_lock": locked, "osd": True})
        elif code == R.EV_FNLOCK:
            self.emit("setting", {"fn_lock": self.settings.fn_locked(), "osd": True})
        elif code in R.EV_KB_BACKLIGHT:
            self.emit("kb_level", {"level": code - 0x3B, "osd": True})
        elif code in (R.EV_SINGLE_KB_LEVEL, R.EV_SINGLE_KB_POWER):
            self.emit("keyboard", self.keyboard.status())
        elif code in (R.EV_LIGHTBAR_ON, R.EV_LIGHTBAR_OFF):
            self.emit("setting", {"lightbar_on": code == R.EV_LIGHTBAR_ON})
        elif code == R.EV_PROTECT and self.pf.balanced_protect:
            self.power.set_user_profile(self.power.option["OperatingMode"])
        elif code in (R.EV_LC_FAN_BOOST, R.EV_LC_PUMP_BOOST):
            if self.liquid.status()["connected"]:
                self.liquid.toggle_boost("fan" if code == R.EV_LC_FAN_BOOST else "pump")
        elif code == R.EV_LAUNCH_APP:
            self.emit("launch", {})
        elif code == R.EV_AIRPLANE:
            self.emit("osd", {"airplane": True})
        else:
            self.emit("wmi", {"code": code})

    def on_poll_change(self, key, value):
        if key == "ac":
            log.info("AC adapter %s", "online" if value else "offline")
            if self.fan_control:
                self.power.power_status_change(value)
            else:
                self.power.ac_online = value
            try:
                self.rules.on_ac_change(value)
            except Exception:  # noqa: BLE001
                log.exception("power source rules")
            self.emit("ac", {"online": value})
        elif key == "resume":
            log.info("resume detected — re-applying settings")
            if self.fan_control:
                self.power.start()
            self.settings.start()
            self.battery.start()
            self.liquid.resume()
            if self.keyboard.rgb and self.keyboard.rgb.saved and self.settings_store.get("kb_power", True):
                try:
                    self.keyboard.rgb.set_effect(**self.keyboard.rgb.saved)
                except Exception:  # noqa: BLE001
                    pass
            self.emit("status", {})
        elif key == "boost":
            self.power.fan_boost_from_ec()
        elif key == "winkey":
            self.settings_store.set("winkey_lock", value)
            self.emit("setting", {"winkey_lock": value, "osd": True})
        elif key == "fnlock":
            self.emit("setting", {"fn_lock": value, "osd": True})

    # -- aggregated state for the UI ----------------------------------------------------------------
    def state(self):
        p = self.power
        return {
            "platform": {**self.pf.as_dict(), "ec_backend": self.ec.name, "nvram": self.nvram.verified,
                         "fan_control": self.fan_control,
                         "hotkeys": any(t.name == "hotkeys" and getattr(t, "available", False) for t in self.threads),
                         "os": "windows" if IS_WIN else "linux"},
            "power": p.status(),
            "profiles": p.profiles,
            "tables": {n: p.tables.tables.get(n) for n in p.TABLE_NAMES},
            "default_tables": p.tables.defaults,
            "settings": self.settings.status(),
            "battery": self.battery.status(),
            "keyboard": self.keyboard.status(),
            "app_binding": self.settings_store.get("app_binding", []),
            "liquid": self.liquid.status(),
            "automation": {k: auto_setting(self.settings_store, k) for k in AUTO_DEFAULTS},
            "info": self.monitor.info(),
        }
