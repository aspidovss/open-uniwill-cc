"""NVIDIA GPU target temperature ("Temperature Limit" of the GPU in the original Control Center).

Windows: the same NVAPI calls GCUService makes through GPUInfoDLL.dll (GetNvGpuThermalLimitInfo /
SetNVGpuThermalPoliciesStatus): client thermal policies, temperatures in 1/256 °C.
  NvAPI_GPU_ClientThermalPoliciesGetInfo   0x0D258BB5  NV_GPU_THERMAL_POLICIES_INFO   v3, 0x578 bytes
  NvAPI_GPU_ClientThermalPoliciesGetStatus 0xE9C425A1  NV_GPU_THERMAL_POLICIES_STATUS v3, 0x548 bytes
  NvAPI_GPU_ClientThermalPoliciesSetStatus 0x34C0B13D
  info:   [4] flags (bit0 valid), [5] count, entries at 8 (stride 0x15C): +0 controller, +0xC min, +0x10 default,
          +0x14 max
  status: [4] count, entries at 8 (stride 0x150): +0 controller, +8 target
Linux: nvidia-smi -q -d TEMPERATURE ("GPU Target Temperature", "GPU Max Operating Temp") and nvidia-smi -gtt T.
"""
import logging
import re
import shutil
import struct
import subprocess
import sys
import threading

log = logging.getLogger("uwccd.gputemp")

MIN_TARGET = 65          # the lowest target offered when the driver does not report a minimum


class _WinNvapi:
    INFO_VER, INFO_SIZE = 0x30578, 0x578
    STATUS_VER, STATUS_SIZE = 0x30548, 0x548

    def __init__(self):
        import ctypes
        self.ct = ctypes
        dll = ctypes.WinDLL("nvapi64.dll")
        qi = dll.nvapi_QueryInterface
        qi.restype, qi.argtypes = ctypes.c_void_p, [ctypes.c_uint]

        def fn(fid, *args):
            p = qi(fid)
            if not p:
                raise OSError(f"NVAPI function {fid:#x} not available")
            return ctypes.CFUNCTYPE(ctypes.c_int, *args)(p)

        fn(0x0150E828)()                                       # NvAPI_Initialize
        handles, count = (ctypes.c_void_p * 64)(), ctypes.c_uint(0)
        rc = fn(0xE5AC921F, ctypes.c_void_p, ctypes.c_void_p)(handles, ctypes.byref(count))
        if rc or not count.value:
            raise OSError(f"NvAPI_EnumPhysicalGPUs: {rc}")
        self.gpu = handles[0]
        self._get_info = fn(0x0D258BB5, ctypes.c_void_p, ctypes.c_void_p)
        self._get_status = fn(0xE9C425A1, ctypes.c_void_p, ctypes.c_void_p)
        self._set_status = fn(0x34C0B13D, ctypes.c_void_p, ctypes.c_void_p)

    def _info(self):
        buf = self.ct.create_string_buffer(self.INFO_SIZE)
        struct.pack_into("<I", buf, 0, self.INFO_VER)
        rc = self._get_info(self.gpu, buf)
        if rc or not buf.raw[4] & 1 or not buf.raw[5]:
            raise OSError(f"thermal policies info: {rc}")
        controller, = struct.unpack_from("<I", buf, 8)
        mn, df, mx = struct.unpack_from("<iii", buf, 8 + 0x0C)
        return controller, mn / 256, df / 256, mx / 256

    def info(self):
        controller, mn, df, mx = self._info()
        buf = self.ct.create_string_buffer(self.STATUS_SIZE)
        struct.pack_into("<IB", buf, 0, self.STATUS_VER, 1)
        struct.pack_into("<I", buf, 8, controller)
        cur = None
        if not self._get_status(self.gpu, buf):
            cur = struct.unpack_from("<i", buf, 8 + 8)[0] / 256
        return {"min": round(mn), "default": round(df), "max": round(mx), "current": round(cur) if cur else None}

    def set(self, temp):
        controller, mn, _df, mx = self._info()
        if not mn <= temp <= mx:
            raise ValueError(f"GPU temperature limit {round(mn)}..{round(mx)} °C")
        buf = self.ct.create_string_buffer(self.STATUS_SIZE)
        struct.pack_into("<IB", buf, 0, self.STATUS_VER, 1)
        struct.pack_into("<I", buf, 8, controller)
        self._get_status(self.gpu, buf)
        struct.pack_into("<IB", buf, 0, self.STATUS_VER, 1)
        struct.pack_into("<i", buf, 8 + 8, int(temp * 256))
        rc = self._set_status(self.gpu, buf)
        if rc:
            raise OSError(f"NvAPI_GPU_ClientThermalPoliciesSetStatus: {rc}")


class _NvidiaSmi:
    def __init__(self):
        self.exe = shutil.which("nvidia-smi")
        if not self.exe:
            raise OSError("nvidia-smi not found")
        self.default = None

    def _q(self):
        out = subprocess.run([self.exe, "-q", "-d", "TEMPERATURE"], capture_output=True, text=True,
                             timeout=5, check=False).stdout
        get = lambda k: (lambda m: int(m.group(1)) if m else None)(re.search(rf"{k}\s*:\s*(\d+)\s*C", out))  # noqa: E731
        return get("GPU Target Temperature"), get("GPU Max Operating Temp")

    def info(self):
        cur, mx = self._q()
        if cur is None:
            raise OSError("this GPU / driver does not report a target temperature")
        if self.default is None:
            self.default = cur
        mx = mx or max(cur, 87)
        return {"min": min(MIN_TARGET, cur), "default": self.default, "max": mx, "current": cur}

    def set(self, temp):
        r = subprocess.run([self.exe, "-gtt", str(int(temp))], capture_output=True, text=True, timeout=10, check=False)
        if r.returncode:
            raise OSError((r.stdout + r.stderr).strip() or f"nvidia-smi -gtt: {r.returncode}")


class GpuTargetTemperature:
    """Lazy wrapper: the backend is created on first use (nvidia-smi wakes a sleeping dGPU, so not at start)."""

    def __init__(self, mock=False):
        self.mock = mock
        self.backend = None
        self.error = None
        self.cache = None
        self.applied = None            # what we set last (None = driver default)
        self.lock = threading.Lock()

    def _be(self):
        if self.backend is None and self.error is None:
            try:
                if self.mock:
                    self.backend = _Mock()
                elif sys.platform == "win32":
                    self.backend = _WinNvapi()
                else:
                    self.backend = _NvidiaSmi()
            except Exception as e:  # noqa: BLE001
                self.error = str(e)
                log.info("GPU temperature limit unavailable: %s", e)
        return self.backend

    def info(self, refresh=False):
        with self.lock:
            if self.cache is not None and not refresh:
                return self.cache
            be = self._be()
            if not be:
                return None
            try:
                self.cache = be.info()
            except Exception as e:  # noqa: BLE001
                log.info("GPU temperature limit info: %s", e)
                self.cache = None
            return self.cache

    def apply(self, on, temp):
        """on: set temp; off: go back to the driver default (only if we changed it before)."""
        info = self.info()
        if not info:
            return False
        target = int(temp) if on else (info["default"] if self.applied is not None else None)
        if target is None or target == self.applied:
            return True
        with self.lock:
            try:
                self.backend.set(max(info["min"], min(info["max"], target)))
                self.applied = target if on else None
                log.info("GPU temperature limit %s", f"{target} °C" if on else "back to default")
                return True
            except Exception as e:  # noqa: BLE001
                log.warning("GPU temperature limit: %s", e)
                return False


class _Mock:
    def __init__(self):
        self.cur = 87

    def info(self):
        return {"min": 65, "default": 87, "max": 87, "current": self.cur}

    def set(self, temp):
        self.cur = temp
