"""UEFI variable "UniWillVariable" {9f33f85c-13ca-4fd1-9c4a-96217722c593}.

GCUService (UEFI_Firmware.dll) reads the variable, patches a byte range and writes the
whole variable back. The layout is the .NET NVRAM_STRUCT marshalled with default
sequential layout (natural alignment).  Because a wrong layout guess would scribble on
firmware settings, writes are only enabled after a plausibility check (see verify()).
"""
import errno
import logging
import os
import struct
import sys

IS_WIN = sys.platform == "win32"
if not IS_WIN:
    import fcntl

log = logging.getLogger("uwccd.nvram")

NAME = "UniWillVariable"
GUID = "9f33f85c-13ca-4fd1-9c4a-96217722c593"
EFIVARS = "/sys/firmware/efi/efivars"

# (name, size, count)  count>1 => byte array (ByValArray SizeConst)
FIELDS = [
    ("OemBoardSsid", 4, 1), ("SupportByte", 2, 1), ("ProjectID", 1, 1), ("KeyboardType", 1, 1),
    ("CustomerList", 1, 1), ("RGBLightbarMode", 1, 1), ("RGBLightbarMode_R", 1, 1),
    ("RGBLightbarMode_G", 1, 1), ("RGBLightbarMode_B", 1, 1), ("ColorCalibrationSupport", 1, 1),
    ("TDRdata", 1, 1), ("RGBKeyboard1A", 1, 8), ("RGBKeyboard08", 1, 8), ("SmartLightbar1A", 1, 8),
    ("SmartLightbar08", 1, 8), ("PowerMode", 1, 1), ("BatteryLimitation", 1, 1),
    ("ChargeMaximumLimit", 1, 1), ("ChargeMinimumLimit", 1, 1), ("MemoryOverClockSwitch", 1, 1),
    ("ICpuCoreVoltageValue", 2, 1), ("ICpuCoreVoltageMaximum", 2, 1), ("ICpuCoreVoltageMinimum", 2, 1),
    ("ICpuCoreVoltageOffsetValue", 2, 1), ("ICpuCoreVoltageOffsetMaximum", 2, 1),
    ("ICpuCoreVoltageOffsetMinimum", 2, 1), ("ICpuTauValue", 2, 1), ("ACpuOverClockSupport", 1, 1),
    ("ACpuFreqValue", 4, 1), ("ACpuFreqValueMaximum", 4, 1), ("ACpuFreqValueMinimum", 4, 1),
    ("ACpuVoltageValue", 4, 1), ("ACpuVoltageValueMaximum", 4, 1), ("ACpuVoltageValueMinimum", 4, 1),
    ("OverClockRecoveryFlag", 1, 1), ("ApExistFlag", 1, 1), ("ACRecoverySupport", 1, 1),
    ("ACRecoveryStatus", 1, 1), ("MemoryOverClockSupport", 1, 1), ("ApUseFlag", 1, 1),
    ("OemDisplayMode", 1, 1), ("ICpuCoreVoltageOffsetNegativeValue", 2, 1),
    ("ICpuCoreVoltageOffsetRangeType", 1, 1), ("FnKeyStatus", 1, 1), ("AudioCodecID", 4, 1),
    ("PowerPhase", 1, 1), ("ICpuCoreVoltageOffsetSupport", 1, 1), ("Reserved", 1, 0x4C),
]


def layout(packed=False):
    off, lay, maxal = 0, {}, 1
    for name, size, count in FIELDS:
        al = 1 if packed else size
        maxal = max(maxal, al)
        off = (off + al - 1) // al * al
        lay[name] = (off, size, count)
        off += size * count
    total = (off + maxal - 1) // maxal * maxal
    return lay, total


class Nvram:
    def __init__(self, allow_write=True):
        self.path = os.path.join(EFIVARS, f"{NAME}-{GUID}")
        if IS_WIN:
            self.available = self._win_probe()
        else:
            self.available = os.path.exists(self.path)
        self.layout, self.size = layout(False)
        self.allow_write = allow_write
        self.verified = False

    # -- raw ---------------------------------------------------------------
    def _win_probe(self):
        from .win import winapi
        try:
            winapi.enable_privilege("SeSystemEnvironmentPrivilege")
            winapi.get_firmware_var(NAME, GUID)
            return True
        except OSError as e:
            log.info("UniWillVariable not readable: %s", e)
            return False

    def _raw(self):
        if IS_WIN:
            from .win import winapi
            attrs, data = winapi.get_firmware_var(NAME, GUID)
            return attrs.to_bytes(4, "little"), bytearray(data)
        with open(self.path, "rb") as f:
            data = f.read()
        return data[:4], bytearray(data[4:])

    def read_all(self):
        if not self.available:
            return None
        try:
            return self._raw()[1]
        except OSError as e:
            log.warning("read %s: %s", self.path, e)
            return None

    def get(self, field):
        data = self.read_all()
        if data is None:
            return None
        off, size, count = self.layout[field]
        if off + size * count > len(data):
            return None
        if count > 1:
            return list(data[off:off + count])
        return int.from_bytes(data[off:off + size], "little")

    def fields(self):
        data = self.read_all()
        if data is None:
            return {}
        out = {}
        for name, (off, size, count) in self.layout.items():
            if name == "Reserved" or off + size * count > len(data):
                continue
            out[name] = list(data[off:off + count]) if count > 1 else int.from_bytes(data[off:off + size], "little")
        return out

    def verify(self, ec_project_id=None):
        """Enable writes only if the variable looks like what GCUService expects."""
        data = self.read_all()
        if data is None:
            log.info("UniWillVariable not present — NVRAM features disabled")
            return False
        if len(data) < self.layout["FnKeyStatus"][0] + 1:
            log.warning("UniWillVariable is %d bytes, expected >= %d — NVRAM writes disabled", len(data), self.size)
            return False
        pm = self.get("PowerMode")
        ok = pm in (0, 1, 2, 3, 0xFF)
        if ec_project_id is not None:
            ok = ok and self.get("ProjectID") in (ec_project_id & 0xFF, 0, 0xFF)
        self.verified = ok
        if not ok:
            log.warning("UniWillVariable layout check failed (PowerMode=%s) — NVRAM writes disabled", pm)
        return ok

    def set(self, field, value):
        if not (self.available and self.allow_write and self.verified):
            return False
        off, size, count = self.layout[field]
        try:
            attrs, data = self._raw()
            if off + size * count > len(data):
                return False
            new = int(value).to_bytes(size, "little")
            if data[off:off + size] == new:
                return True
            data[off:off + size] = new
            if IS_WIN:
                from .win import winapi
                winapi.set_firmware_var(NAME, GUID, bytes(data), int.from_bytes(attrs, "little"))
                log.info("NVRAM %s=%s", field, value)
                return True
            self._clear_immutable()
            fd = os.open(self.path, os.O_WRONLY)
            try:
                os.write(fd, attrs + bytes(data))
            finally:
                os.close(fd)
            log.info("NVRAM %s=%s", field, value)
            return True
        except OSError as e:
            log.warning("NVRAM write %s failed: %s", field, e)
            return False

    def _clear_immutable(self):
        FS_IOC_GETFLAGS, FS_IOC_SETFLAGS, FS_IMMUTABLE_FL = 0x80086601, 0x40086602, 0x10
        try:
            fd = os.open(self.path, os.O_RDONLY)
            try:
                buf = bytearray(8)
                fcntl.ioctl(fd, FS_IOC_GETFLAGS, buf, True)
                flags = struct.unpack("<i", bytes(buf[:4]))[0]   # kernel copies an int
                if flags & FS_IMMUTABLE_FL:
                    fcntl.ioctl(fd, FS_IOC_SETFLAGS, struct.pack("<iI", flags & ~FS_IMMUTABLE_FL, 0))
            finally:
                os.close(fd)
        except OSError as e:
            if e.errno not in (errno.ENOTTY, errno.EINVAL):
                log.debug("chattr -i: %s", e)
