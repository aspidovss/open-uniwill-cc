"""CPU package power on Windows from the "Energy Meter" performance counters (Intel RAPL / AMD RAPL exposed
by Windows through EMI: instances such as rapl_package0_pkg). The Linux build reads the same RAPL counter
from /sys/class/powercap. Returns None when the counter set does not exist on this machine."""
import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger("uwccd.monitor")

PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2
ERROR_SUCCESS = 0


class PDH_FMT_COUNTERVALUE(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class PDH_FMT_COUNTERVALUE_ITEM_W(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", PDH_FMT_COUNTERVALUE)]


class EnergyMeterPower:
    PATH = r"\Energy Meter(*)\Power"

    def __init__(self):
        self.query = self.counter = None
        self.ok = False
        try:
            self.pdh = ctypes.WinDLL("pdh")
            q, c = wintypes.HANDLE(), wintypes.HANDLE()
            if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(q)) != ERROR_SUCCESS:
                return
            if self.pdh.PdhAddEnglishCounterW(q, self.PATH, None, ctypes.byref(c)) != ERROR_SUCCESS:
                self.pdh.PdhCloseQuery(q)
                log.info("Energy Meter counters not available: no CPU package power on this machine")
                return
            self.query, self.counter = q, c
            self.pdh.PdhCollectQueryData(q)
            self.ok = True
        except (OSError, AttributeError) as e:
            log.info("PDH: %s", e)

    def _values(self):
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        rc = self.pdh.PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None)
        if rc & 0xFFFFFFFF != PDH_MORE_DATA or not size.value:
            return {}
        buf = ctypes.create_string_buffer(size.value)
        rc = self.pdh.PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), buf)
        if rc != ERROR_SUCCESS:
            return {}
        items = ctypes.cast(buf, ctypes.POINTER(PDH_FMT_COUNTERVALUE_ITEM_W))
        return {items[i].szName.lower(): items[i].FmtValue.doubleValue for i in range(count.value)
                if items[i].FmtValue.CStatus in (0, 1)}

    def watts(self):
        if not self.ok:
            return None
        try:
            if self.pdh.PdhCollectQueryData(self.query) != ERROR_SUCCESS:
                return None
            vals = self._values()
        except OSError:
            return None
        pkg = [v for k, v in vals.items() if "pkg" in k or "package" in k]
        if not pkg:
            return None
        w = sum(pkg) / 1000.0               # the counter is documented in milliwatts
        while w > 1000:                     # some drivers report µW / pW: a laptop CPU package is < 1 kW
            w /= 1000.0
        return round(w, 1)
