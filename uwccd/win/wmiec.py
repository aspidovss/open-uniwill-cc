"""EC access through the Windows built-in WMI driver (wmiacpi.sys) — open alternative to UWACPIDriver.sys (beta).

The firmware of MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super / XMG NEO 16 (E23) (Uniwill project 0x10)
exposes root\\WMI\\AcpiTest_MULong.GetSetULong (DSDT WMBC -> OEMG -> RKBC / WKBC):
    read : Data = (1 << 40) | addr    -> Return & 0xFF
    write: Data = (value << 16) | addr
Each call takes ~125 ms (wait loops with Sleep(50) inside the firmware), so reads are cached and unchanged writes
skipped (CachedEC). SMRW (Smart APC limits) and PWUP (liquid-cooling power level) are not reachable this way:
limits come from ec_wmi.json, PWUP is reported as unavailable.

COM objects are used from one worker thread only (the service calls the EC from many threads).
See docs/EC/WMI-vs-Driver.md.
"""
import logging
import queue
import threading

from ..ec import CachedEC, ECError, _hexset

log = logging.getLogger("uwccd.wmiec")


class WinWmiEC(CachedEC):
    name = "wmi"

    def __init__(self, cfg=None):
        cfg = cfg or {}
        poll = cfg.get("poll", {})
        super().__init__(poll.get("cache_ms", 4000), _hexset(cfg.get("always_write", [])),
                         _hexset(cfg.get("no_cache", [])))
        self.timeout = float(cfg.get("timeout_s", 5))
        self.instance = str(cfg.get("instance", "1_1"))
        w = cfg.get("wmi") or {}                      # layout of the call from the platform profile
        enc = w.get("encoding") or {}
        self.ns = w.get("namespace", "root\\WMI")
        self.cls = w.get("class", "AcpiTest_MULong")
        self.meth = w.get("method", "GetSetULong")
        self.read_flag = 1 << int(enc.get("read_flag_bit", 40))
        self.value_shift = int(enc.get("value_shift", 16))
        self.read_mask = int(enc.get("read_mask", 0xFF))
        self.limits = cfg.get("limits")
        self.smapc_source = "config"
        self.q = queue.Queue()
        ready = queue.Queue()
        self.worker = threading.Thread(target=self._loop, args=(ready,), daemon=True, name="wmi-ec")
        self.worker.start()
        ok, err = ready.get(timeout=30)
        if not ok:
            raise ECError(err)

    # -- COM worker ----------------------------------------------------------------------------------
    def _loop(self, ready):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            svc = win32com.client.GetObject("winmgmts:{impersonationLevel=impersonate}!\\\\.\\" + self.ns)
            insts = list(svc.ExecQuery(f"SELECT * FROM {self.cls}"))
            if not insts:
                raise ECError(f"{self.cls} not found: this firmware has no WMI EC interface")
            inst = next((i for i in insts if str(i.InstanceName).endswith(self.instance)), insts[0])
            path = inst.Path_.Path
            meth = svc.Get(self.cls).Methods_(self.meth)
            self.instance_name = str(inst.InstanceName)
        except Exception as e:  # noqa: BLE001
            ready.put((False, f"WMI EC interface unavailable: {e}"))
            return
        ready.put((True, None))
        log.info("WMI EC path ready: %s", self.instance_name)
        while True:
            data, reply = self.q.get()
            if data is None:
                break
            try:
                p = meth.InParameters.SpawnInstance_()
                p.Data = str(data)                       # uint64 is passed as a string in SWbem
                reply.put((True, int(svc.ExecMethod(path, self.meth, p).Return)))
            except Exception as e:  # noqa: BLE001
                reply.put((False, e))

    def _call(self, data):
        reply = queue.Queue()
        self.q.put((data, reply))
        try:
            ok, v = reply.get(timeout=self.timeout)
        except queue.Empty:
            raise ECError(f"WMI call timed out after {self.timeout} s") from None
        if not ok:
            raise ECError(f"WMI call failed: {v}")
        return v

    def _read(self, addr):
        return self._call(self.read_flag | addr) & self.read_mask & 0xFF

    def _write(self, addr, val):
        self._call(((val & 0xFF) << self.value_shift) | addr)

    # -- what WMI cannot do --------------------------------------------------------------------------
    def smart_apc_table(self):
        if not self.limits:
            raise ECError("SMRW is not available through WMI and ec_wmi.json has no limits for this laptop")
        return dict(self.limits)

    def _pwup(self, level):
        raise ECError("PWUP is not available through WMI (needs the OEM driver)")

    def close(self):
        self.q.put((None, None))
