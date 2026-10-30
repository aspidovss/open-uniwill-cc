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
from .busy import Busy
from .automation import DEFAULTS as AUTO_DEFAULTS, LoadRules, PowerSourceRules, Sampler, setting as auto_setting
from .events import AppBinding, ECPoller, HotkeyEvents, IdleTimer, KeyPresses
from .fan import PowerManager
from .fan_std import PowerManagerStd
from .hw import Platform
from .lighting.keyboard import KeyboardManager
from .monitor import Monitor
from .nvram import MockNvram, Nvram
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
        self.settings_store = store.Settings()
        self.listeners = []
        self.llock = threading.Lock()
        self.busy = Busy(self.emit)              # long operations the window waits for (WMI: mode switches)
        from .clevo import ClevoManager
        self.clevo = ClevoManager(self.settings_store, self.emit, mock=mock)     # Control Center 3.0 / Clevo
        self.clevo.start()
        from .ecaccess import open_backend
        self.ec, self.ec_info = open_backend(self.settings_store, mock=mock, prefer=None if mock else backend,
                                             clevo=self.clevo.present)
        self.oem_driver = None
        self.pf = Platform(self.ec)
        if self.ec_info.get("active") not in ("none", None):
            self.settings_store.set("ec_project", self.pf.project_raw)       # WMI layout of the next start
        from .admin import Admin
        from .api import RUN_DIR
        self.admin = Admin(RUN_DIR, self.emit)
        log.info("project %s (raw 0x%X), ramfan1.5=%s turbo=%s nv=%s amd=%s", self.pf.project_name,
                 self.pf.project_raw, self.pf.ramfan15, self.pf.turbo_support, self.pf.nv_gpu, self.pf.amd)
        self.nvram = MockNvram() if mock else Nvram()
        self.nvram.verify(self.pf.project_raw)
        apply_debug(self.settings_store.get("debug", False) or os.environ.get("UWCC_DEBUG") == "1")
        # MyFanCtrl: commercial projects -> _CML manager, all others -> RamFan1p5 manager (with Custom mode)
        choice = self.settings_store.get("fan_manager", "auto")
        std = (choice == "std") or (choice != "cml" and not self.pf.commercial)
        self.power = (PowerManagerStd if std else PowerManager)(self.ec, self.pf, self.nvram, self.emit)
        log.info("fan manager: %s (%s)", self.power.manager, "forced" if choice in ("std", "cml") else "by project")
        self.power.busy = self.busy
        self.power.tables.busy = self.busy
        self.power.tables.deferred = self.ec_info.get("active") == "wmi"     # fan curve after the mode, in background
        if std:
            self.power.tcc_extended = bool(self.settings_store.get("tcc_extended", False))
            if self.pf.nv_gpu:
                from .gputemp import GpuTargetTemperature
                self.power.gputemp = GpuTargetTemperature(mock=mock)
        self.settings = SettingsManager(self.ec, self.pf, self.nvram, self.settings_store, self.emit)
        self.battery = BatteryManager(self.ec, self.pf, self.nvram, self.settings_store)
        self.keyboard = KeyboardManager(self.ec, self.pf, self.settings_store, mock=mock)
        self.keyboard.ac_fn = lambda: getattr(self.power, "ac_online", True)
        self.keyboard.metrics_fn = self._fx_metrics
        if IS_WIN:          # also with --mock: /proc and /sys do not exist on Windows
            from .win.sysinfo import WinMonitor
            self.monitor = WinMonitor(self.ec, self.pf)
        else:
            self.monitor = Monitor(self.ec, self.pf)
        self.liquid = LiquidCooler(self.ec, self.hottest_temp, self.emit, mock=mock,
                                   mode_fn=lambda: self.power.option.get("OperatingMode") if self.fan_control else None)
        self.liquid.no_temps = lambda: self.monitor_level() == "off"
        self.sampler = Sampler(self)
        from .selfcheck import SelfCheck
        self.selfcheck = SelfCheck(self)
        self.tray_clients = 0          # Windows tray apps connected to /api/events (they install updates)
        from .updates import Updater
        self.updater = Updater(self)
        self.rules = PowerSourceRules(self)
        self.load_rules = LoadRules(self)              # mode by power / temperature / load (Automation)
        self.threads = []
        self.fan_control = False

    def monitor_level(self):
        """EC Manager monitoring switches: "full" | "light" (temperatures only, every LIGHT_S) | "off"."""
        from .ecaccess import monitoring
        return monitoring(self.settings_store, self.ec_info.get("active"))

    def restart_service(self, reason=""):
        """Restart the service (EC path changed, restart button). The window shows a wait dialog meanwhile."""
        log.info("restarting the service%s", f" ({reason})" if reason else "")
        self.emit("restarting", {"reason": reason})
        if self.mock:
            return False
        if IS_WIN:
            from .win.winplat import restart_self
            threading.Timer(0.8, restart_self).start()
            threading.Timer(40.0, lambda: os._exit(3)).start()     # the clean restart did not happen: SCM recovery
        else:
            threading.Timer(0.8, lambda: os._exit(3)).start()      # systemd Restart=on-failure
        return True

    def hottest_temp(self, source="max"):
        """Temperature driving the cooler: the hotter of CPU and NVIDIA GPU, or one of them.
        "gpu" falls back to the CPU while the GPU sleeps / is not there (otherwise the cooler would stay put).
        Monitoring "light": the temperatures the sampler reads every LIGHT_S; "off": none (the cooler uses a preset)."""
        lvl = self.monitor_level()
        if lvl == "off":
            return None
        if lvl == "light":
            m = self.sampler.latest or {}
            cpu = (m.get("cpu") or {}).get("temp")
            gpu = (m.get("gpu") or {}).get("temp") if source != "cpu" else None
        else:
            cpu = self.monitor.cpu_temp()
            gpu = (self.monitor.nvidia() or {}).get("temp") if self.pf.nv_gpu and source != "cpu" else None
        ok = lambda v: isinstance(v, (int, float))          # noqa: E731
        if source == "cpu":
            return cpu if ok(cpu) else None
        if source == "gpu":
            return gpu if ok(gpu) else (cpu if ok(cpu) else None)
        ts = [v for v in (cpu, gpu) if ok(v)]
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
        if kind == "lc" and data.get("event") != "hwoc" and getattr(self, "hwoc", None):
            self.hwoc.wake.set()                 # cooler connected / flow changed
        msg = json.dumps({"type": kind, "data": data, "t": time.time()})
        with self.llock:
            for q in list(self.listeners):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

    # -- lifecycle -----------------------------------------------------------------------------
    def _gpu_temp_probe(self):
        """Read the GPU temperature-limit range once (on Linux only while the dGPU is awake: nvidia-smi wakes it)."""
        time.sleep(8)
        if not IS_WIN and not self.mock:
            from .monitor import dgpu_state
            if dgpu_state() not in (None, "active"):
                return
        if self.power.gputemp.info():
            self.emit("status", {})

    def start(self):
        self.power.ac_online = self.monitor.ac_online()
        self.fan_control = self.pf.ramfan15 or bool(self.settings_store.get("force_fan_control"))
        if self.ec_info.get("active") != "none":
            from .selfcheck import restore_snapshot
            restore_snapshot(self.ec)              # a self-check with writes was interrupted
        if self.fan_control:
            self.power.start()
        else:
            log.warning("EC does not report RamFan 1.5 (0x78E bit6). GCUService uses a different fan manager "
                        "on such machines — modes/fan tables are disabled (monitoring, lighting, switches work).")
        self.settings.start()
        self.battery.start()
        self.keyboard.start()
        if getattr(self.power, "gputemp", None):
            threading.Thread(target=self._gpu_temp_probe, daemon=True, name="gpu-temp-probe").start()
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
        def binding_mode(mode):                       # load rules come first: no App binding change while one is active
            if self.load_rules.active is None:
                self.power.user_set_mode(mode)
        self.threads.append(AppBinding(lambda: self.settings_store.get("app_binding", []),
                                       binding_mode, lambda: self.power.option["OperatingMode"]))
        if self.ec_info.get("active") == "wmi":
            from .ecaccess import config as wmi_config
            self.sampler.interval = float(wmi_config(self.pf.project_raw)["poll"].get("monitor_s", 5))
        if IS_WIN and not self.mock:
            def driver_info():
                from .ecaccess import oem_driver_info
                self.oem_driver = oem_driver_info()
            threading.Thread(target=driver_info, daemon=True, name="oem-driver-info").start()
        self.threads.append(self.sampler)
        from .hwoc import LiquidHWOC
        self.hwoc = LiquidHWOC(self)
        self.threads.append(self.hwoc)
        if not self.mock:
            self.threads.append(self.updater)
        for t in self.threads:
            t.start()
        self.liquid.start()
        from . import version_string
        log.info("service started: open-uniwill-cc %s (hotkeys: %s)", version_string(),
                 "kernel module" if hk.available else "polling")

    def stop(self):
        t = self.power.tables
        t._pending = None
        t.wait_idle(20)                    # a fan curve still being written in the background
        self.liquid.stop()
        self.sampler.save_day()
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
        elif code == R.EV_FAN_BOOST and getattr(self, "selfcheck", None) and self.selfcheck.running == 2:
            pass                                      # the self-check switches Fan Boost itself
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
        elif code == R.EV_HWOC:
            self.hwoc.on_wmi(code)
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
            self.power.tables.invalidate()
            inv = getattr(self.ec, "invalidate", None)
            if inv:
                inv()
            if self.fan_control:
                self.power.start()
            self.settings.start()
            self.battery.start()
            self.liquid.resume()
            if self.keyboard.rgb and self.keyboard.rgb.saved and self.settings_store.get("kb_power", True):
                try:
                    self.keyboard.rgb.set_effect(**self.keyboard.rgb.saved, force=True)
                except Exception:  # noqa: BLE001
                    pass
            self.emit("status", {})
        elif key == "boost":
            if self.selfcheck.running == 2:          # the self-check switches Fan Boost itself
                return
            self.power.fan_boost_from_ec()
        elif key == "winkey":
            self.settings_store.set("winkey_lock", value)
            self.emit("setting", {"winkey_lock": value, "osd": True})
        elif key == "fnlock":
            self.emit("setting", {"fn_lock": value, "osd": True})

    def _fx_metrics(self):
        """battery charge, CPU and GPU load for the top-row bar of the BetterRGB effects (from the monitor sample;
        CPU and GPU only while monitoring is on)"""
        m = self.sampler.latest or {}
        out = {}
        bat = m.get("battery")
        if not bat:
            try:
                bat = self.monitor.battery()
            except Exception:  # noqa: BLE001
                bat = None
        if bat and bat.get("percent") is not None:
            out["battery"] = bat["percent"]
        if (m.get("cpu") or {}).get("usage") is not None:
            out["cpu"] = m["cpu"]["usage"]
        if (m.get("gpu") or {}).get("usage") is not None:
            out["gpu"] = m["gpu"]["usage"]
        return out

    # -- aggregated state for the UI ----------------------------------------------------------------
    def state(self):
        p = self.power
        return {
            "platform": {**self.pf.as_dict(), "ec_backend": self.ec.name, "nvram": self.nvram.verified,
                         "fan_control": self.fan_control,
                         "hotkeys": any(t.name == "hotkeys" and getattr(t, "available", False) for t in self.threads),
                         "os": "windows" if IS_WIN else "linux"},
            "update": self.updater.status(),
            "power": p.status(),
            "profiles": p.profiles,
            "tables": {n: p.tables.tables.get(n) for n in p.TABLE_NAMES},
            "default_tables": p.tables.defaults,
            "settings": self.settings.status(),
            "battery": self.battery.status(),
            "keyboard": self.keyboard.status(),
            "app_binding": self.settings_store.get("app_binding", []),
            "liquid": self.liquid.status(),
            "hwoc": self.hwoc.status() if getattr(self, "hwoc", None) else None,
            "automation": {k: auto_setting(self.settings_store, k) for k in AUTO_DEFAULTS},
            "load_rules": self.load_rules.status(),
            "info": self.monitor.info(),
            "ec_access": self.ec_access(),
            "clevo": self.clevo.status() if self.clevo.present else {"present": False},
            "busy": self.busy.state(),
            "monitoring": self.monitor_level(),
        }

    def ec_access(self):
        from .ecaccess import status
        return status(self)
