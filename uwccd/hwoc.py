"""Liquid-cooling "super performance" (GCUService.MyFan.BTCooling.LiquidHWOC, original UI: CoolingOCSwitch).

While the liquid cooler is connected and its coolant flow is OK, and the EC supports liquid-cooling fan tables
(0x7C8 bit5), the original service:

  * stops writing the user's fan tables (MyFanTableCtrl.SetFanTable("IsLCConnect"));
  * asks the EC to load its own liquid-cooling table for the mode (RefreshDefaultFanTable):
        0xF5F = code (Office 7, Gaming 6, Turbo 5; Custom: 6 with the custom flag), then 0xF5D = 0xFD, 0xF5E = 0xC9,
        and waits (10 x 0.5 s) until the EC has replaced the 0xFD / 0xC9 handshake;
  * passes the EC's overclocking power level (0x7C7 bits 2..4) to the firmware method INOU.PWUP(level)
    (SetHWOC("PUWP") -> UWACPIDriver IOCTL 0x9C40A504), again on every WMI event 0xC2. PWUP switches GPU power
    straps and the NVIDIA platform controller baseline (NPCF.ACBT) by level; level 5 needs the EC's cooler state.

When the cooler disconnects or the flow fails the mode's own fan table is applied again. The GPU clock offsets the
original adds in Turbo are left out (no GPU overclocking in this program).
"""
import logging
import threading
import time

from . import regs as R

log = logging.getLogger("uwccd.hwoc")

REG_LEVEL = 0x7C7                   # bits 2..4: OC power level published by the EC
REG_LC_TABLE = 0xF5F                # mode code of the EC liquid-cooling fan table
REG_HANDSHAKE = (0xF5D, 0xF5E)
HANDSHAKE = (0xFD, 0xC9)
MODE_CODE = {R.MODE_OFFICE: 7, R.MODE_GAMING: 6, R.MODE_TURBO: 5, 3: 6}
FLOW_STABLE = 5.0                   # s of good flow before switching on
EV_HWOC = 0xC2


class LiquidHWOC(threading.Thread):
    def __init__(self, svc):
        super().__init__(daemon=True, name="hwoc")
        self.svc = svc
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.active = False
        self.mode = None
        self.level = None
        self.table_loaded = None        # True / False (EC did not answer) / None
        self.reason = None
        self._flow_ok_since = None

    # -- conditions --------------------------------------------------------------------------------
    def supported(self):
        lc = self.svc.liquid
        if (getattr(self.svc, "ec_info", None) or {}).get("active") == "wmi":
            return False                  # PWUP needs the OEM driver (docs/EC/WMI-vs-Driver.md)
        return bool(getattr(self.svc, "fan_control", False) and getattr(self.svc.power, "manager", "") == "std"
                    and lc.available and lc.ec_table)

    def enabled(self):
        return bool(self.svc.settings_store.get("lc_hwoc", False))

    def _want(self):
        if not self.supported():
            if (getattr(self.svc, "ec_info", None) or {}).get("active") == "wmi":
                return False, "not available with the WMI path (needs the OEM driver)"
            return False, "not supported on this laptop"
        if not self.enabled():
            return False, "off"
        st = self.svc.liquid.status()
        if not st.get("connected"):
            self._flow_ok_since = None
            return False, "cooler not connected"
        if st.get("flow") != "ok":
            self._flow_ok_since = None
            return False, "waiting for coolant flow" if st.get("flow") in ("starting", "unknown") else "no coolant flow"
        self._flow_ok_since = self._flow_ok_since or time.monotonic()
        if time.monotonic() - self._flow_ok_since < FLOW_STABLE:
            return False, "waiting for coolant flow"
        return True, None

    # -- actions -----------------------------------------------------------------------------------
    def load_table(self, mode):
        """RefreshDefaultFanTable: let the EC load its liquid-cooling fan table for the mode."""
        ec = self.svc.ec
        code = MODE_CODE.get(mode, 6)
        ec.write(REG_LC_TABLE, code)
        ec.write(REG_HANDSHAKE[0], HANDSHAKE[0])
        ec.write(REG_HANDSHAKE[1], HANDSHAKE[1])
        for _ in range(10):
            time.sleep(0.5)
            if (ec.read(REG_HANDSHAKE[0]), ec.read(REG_HANDSHAKE[1])) != HANDSHAKE:
                self.table_loaded = True
                log.info("EC liquid-cooling fan table loaded (mode %s, code %d)", mode, code)
                return True
        self.table_loaded = False
        log.warning("EC did not load the liquid-cooling fan table (code %d)", code)
        return False

    def sync_level(self):
        """SetOCLevel(ReadHWOCLevel()): hand the EC's OC power level to the firmware (INOU.PWUP)."""
        try:
            level = (self.svc.ec.read(REG_LEVEL) >> 2) & 0x07
            self.svc.ec.pwup(level)
            self.level = level
            log.info("OC power level %d passed to the firmware (PWUP)", level)
        except Exception as e:  # noqa: BLE001
            log.warning("PWUP: %s", e)

    def _activate(self, mode):
        p = self.svc.power
        p.tables.blocked = True                 # the EC runs its own table now
        p.lc_override = self.load_table
        self.load_table(mode)
        self.sync_level()
        self.active, self.mode = True, mode
        self.svc.emit("lc", {"event": "hwoc", "on": True})

    def _deactivate(self):
        p = self.svc.power
        p.tables.blocked = False
        p.lc_override = None
        self.active, self.mode, self.table_loaded = False, None, None
        try:
            p.set_user_profile(p.option["OperatingMode"])   # the mode's own fan table again
        except Exception as e:  # noqa: BLE001
            log.warning("restore after super performance: %s", e)
        self.sync_level()
        self.svc.emit("lc", {"event": "hwoc", "on": False})

    def update(self):
        with self.lock:
            want, self.reason = self._want()
            mode = self.svc.power.option.get("OperatingMode") if self.supported() else None
            if want and not self.active:
                log.info("liquid-cooling super performance on")
                self._activate(mode)
            elif not want and self.active:
                log.info("liquid-cooling super performance off (%s)", self.reason)
                self._deactivate()
            elif want and mode != self.mode:     # set_user_profile already loaded the table through lc_override
                self.mode = mode

    def on_wmi(self, code):
        if code == EV_HWOC and self.supported():      # WMI path: PWUP is not reachable — nothing to pass on
            self.sync_level()

    def run(self):
        while not self.stop.is_set():
            try:
                self.update()
            except Exception:  # noqa: BLE001
                log.exception("hwoc")
            self.wake.wait(2)
            self.wake.clear()
        # on service stop nothing is restored here: PowerManager.shutdown hands fan control back to the EC

    def status(self):
        return {"supported": self.supported(), "enabled": self.enabled(), "active": self.active,
                "reason": self.reason, "level": self.level, "table_loaded": self.table_loaded}
