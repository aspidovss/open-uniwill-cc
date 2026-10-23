"""Embedded-controller access backends.

GCUService talks to \\\\.\\ACPIDriver (UWACPIDriver.sys, ACPI\\INOU0000) with two IOCTLs:
  0x9C40A488 -> evaluates ECRR(addr)        (1 integer argument, returns value)
  0x9C40A48C -> evaluates ECRW(addr, data)  (2 integer arguments)
Here the same firmware methods are called either through our kernel module (/dev/uwcc)
or through the generic acpi_call module.
"""
import json
import logging
import os
import struct
import sys
import threading
import time

if sys.platform != "win32":
    import fcntl

log = logging.getLogger("uwccd.ec")

ACPI_HID = "INOU0000"


class ECError(Exception):
    pass


class ECBase:
    name = "base"
    write_delay = 0.010   # GCUService sleeps 10 ms after every access
    read_delay = 0.002

    def __init__(self):
        self.lock = threading.RLock()

    # raw ops implemented by subclasses
    def _read(self, addr):
        raise NotImplementedError

    def _write(self, addr, val):
        raise NotImplementedError

    def read(self, addr):
        with self.lock:
            v = self._read(addr) & 0xFF
            if self.read_delay:
                time.sleep(self.read_delay)
            return v

    def write(self, addr, val):
        with self.lock:
            self._write(addr, int(val) & 0xFF)
            if self.write_delay:
                time.sleep(self.write_delay)

    # helpers ------------------------------------------------------------
    def bit(self, addr, n):
        return (self.read(addr) >> n) & 1

    def set_bit(self, addr, n, on):
        with self.lock:
            v = self.read(addr)
            nv = (v | (1 << n)) if on else (v & ~(1 << n) & 0xFF)
            if nv != v:
                self.write(addr, nv)

    def update(self, addr, mask, value):
        """value is already shifted; keeps bits outside mask"""
        with self.lock:
            v = self.read(addr)
            self.write(addr, (v & ~mask & 0xFF) | (value & mask))

    def read16(self, lo, hi):
        return self.read(lo) | (self.read(hi) << 8)

    def _smrw(self, key):
        raise ECError("SMRW not supported by this backend")

    def _pwup(self, level):
        raise ECError("PWUP not supported by this backend")

    def pwup(self, level):
        """Firmware method INOU.PWUP(level): OC power level for liquid cooling (LiquidHWOC.SetOCLevel)."""
        with self.lock:
            return self._pwup(int(level) & 0x07)

    def smart_apc_table(self):
        """SmartApcTableCtrl.GetTableByDriver: SMRW(Buffer{0xBB, key}) for key 0..11, first byte of each
        reply -> SMAPCTABLE_STRUCT {PL1, PL2, PL4, TccOffset, ConfigurableTGP, DynamicBoost,
        TargetTemperature, DefaultTGP, DynamicBoostCpuTdp}. None when the firmware has no SMRW."""
        raw = []
        with self.lock:
            for key in range(12):
                raw.append(self._smrw(key))
        names = ("PL1", "PL2", "PL4", "TccOffset", "ConfigurableTGP", "DynamicBoost",
                 "TargetTemperature", "DefaultTGP", "DynamicBoostCpuTdp")
        return dict(zip(names, raw))

    def close(self):
        pass


class KernelModuleEC(ECBase):
    """/dev/uwcc provided by the uwcc kernel module (kernel/uwcc.c)."""
    name = "uwcc-module"
    DEV = "/dev/uwcc"
    # struct uwcc_ec { __u16 addr; __u16 data; }  — _IOWR('u', 1, ...) / _IOW('u', 2, ...)
    IOC_READ = (3 << 30) | (4 << 16) | (ord("u") << 8) | 1
    IOC_WRITE = (1 << 30) | (4 << 16) | (ord("u") << 8) | 2
    # struct uwcc_smrw { __u8 in[4]; __u8 out[4]; } — _IOWR('u', 3, ...)
    IOC_SMRW = (3 << 30) | (8 << 16) | (ord("u") << 8) | 3
    # __u32 level — _IOW('u', 4, __u32)
    IOC_PWUP = (1 << 30) | (4 << 16) | (ord("u") << 8) | 4

    def __init__(self):
        super().__init__()
        self.fd = os.open(self.DEV, os.O_RDWR | os.O_CLOEXEC)

    def _read(self, addr):
        buf = bytearray(struct.pack("<HH", addr, 0))
        fcntl.ioctl(self.fd, self.IOC_READ, buf, True)
        return struct.unpack("<HH", buf)[1]

    def _write(self, addr, val):
        fcntl.ioctl(self.fd, self.IOC_WRITE, struct.pack("<HH", addr, val))

    def _smrw(self, key):
        buf = bytearray([0xBB, key, 0, 0, 0, 0, 0, 0])
        try:
            fcntl.ioctl(self.fd, self.IOC_SMRW, buf, True)
        except OSError as e:          # ENOTTY: module from 1.0 without SMRW; ENODEV: no such method
            raise ECError(f"SMRW: {e}") from e
        return buf[4]

    def _pwup(self, level):
        try:
            fcntl.ioctl(self.fd, self.IOC_PWUP, struct.pack("<I", level))
        except OSError as e:          # ENOTTY: module older than 1.5.0; ENODEV: no PWUP in this firmware
            raise ECError(f"PWUP: {e}") from e

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


def find_acpi_path(hid=ACPI_HID):
    base = "/sys/bus/acpi/devices"
    try:
        for d in sorted(os.listdir(base)):
            if d.split(":")[0].upper() == hid:
                with open(os.path.join(base, d, "path")) as f:
                    return f.read().strip()
    except OSError:
        pass
    return None


class AcpiCallEC(ECBase):
    """Fallback through the acpi_call module (package acpi-call-dkms)."""
    name = "acpi_call"
    PROC = "/proc/acpi/call"

    def __init__(self, path=None):
        super().__init__()
        self.path = path or find_acpi_path()
        if not self.path:
            raise ECError("ACPI device INOU0000 not found")
        if not os.path.exists(self.PROC):
            raise ECError("/proc/acpi/call missing (modprobe acpi_call)")

    def _call(self, cmd):
        with open(self.PROC, "w") as f:
            f.write(cmd)
        with open(self.PROC, "rb") as f:
            out = f.read().split(b"\0")[0].decode(errors="replace").strip()
        if out.startswith("Error"):
            raise ECError(f"{cmd}: {out}")
        return out

    def _read(self, addr):
        out = self._call(f"{self.path}.ECRR 0x{addr:x}")
        return int(out, 0)

    def _write(self, addr, val):
        self._call(f"{self.path}.ECRW 0x{addr:x} 0x{val:x}")

    def _smrw(self, key):
        out = self._call(f"{self.path}.SMRW bBB{key:02X}0000")
        nums = [int(x, 0) for x in out.strip("{} ").replace(" ", "").split(",") if x]
        if not nums:
            raise ECError(f"SMRW: unexpected reply {out!r}")
        return nums[0] & 0xFF

    def _pwup(self, level):
        self._call(f"{self.path}.PWUP 0x{level:x}")


class MockEC(ECBase):
    """Simulated EC for development (state kept in a JSON file)."""
    name = "mock"
    write_delay = 0
    read_delay = 0

    DEFAULTS = {
        0x740: 0x18, 0x456: 0x80, 0x771: 0x01, 0x772: 0x01, 0x7D2: 0x08, 0x7D3: 0x31,
        0x49F: 0x1A, 0x78E: 0x40, 0x782: 0x10, 0x751: 0x00, 0x766: 0x00,
        0x730: 80, 0x731: 80, 0x732: 215, 0x734: 35, 0x735: 35, 0x736: 215,
        0x7A7: 95, 0x7A8: 95, 0x7A9: 215, 0x738: 56, 0x75B: 70, 0x75C: 64,
        0x464: 0x0D, 0x465: 0x48, 0x46B: 0x10, 0x46C: 0x0C, 0x4A6: 23, 0x4A7: 0,
        0x408: 0x60, 0x409: 0x3B, 0x7B9: 0x00, 0x7D0: 0x00, 0x742: 0x24, 0x73C: 0x19,
    }

    # SMAPCTABLE of a mid-range RTX laptop: PL1 120, PL2 140, PL4 175 W, TCC offset up to 15 °C,
    # cTGP +25 W over a 115 W base, Dynamic Boost 15 W
    SMAPC = [120, 140, 175, 15, 25, 15, 87, 115, 0, 0, 0, 0]

    def __init__(self, path=os.path.join(os.environ.get("TEMP", "/tmp"), "uwcc-mock-ec.json")):
        super().__init__()
        self.path = path
        self.mem = dict(self.DEFAULTS)
        if os.environ.get("UWCC_MOCK_PROJECT"):          # e.g. 0x16 -> non-commercial PH6TQxx
            self.mem[0x740] = int(os.environ["UWCC_MOCK_PROJECT"], 0)
            self.mem.update({0x7D8: 5, 0x7D9: 15, 0x7DA: 5, 0x733: 0, 0x737: 0, 0x7AA: 0})
        try:
            with open(path) as f:
                self.mem.update({int(k): v for k, v in json.load(f).items()})
        except (OSError, ValueError):
            pass
        self._seed_tables()

    def _seed_tables(self):
        if 0xF20 in self.mem:
            return
        cpu = [(0, 48, 0), (54, 50, 30), (59, 64, 30), (63, 68, 35), (67, 68, 45), (70, 74, 50),
               (74, 78, 58), (78, 82, 66), (82, 86, 75), (86, 90, 85), (90, 255, 100)]
        for i in range(16):
            up, down, duty = cpu[i] if i < len(cpu) else (255, 255, 0)
            nxt_up = cpu[i + 1][0] if i + 1 < len(cpu) else 255
            self.mem[0xF00 + i] = nxt_up if i < 15 else 255
            if i < 15:
                self.mem[0xF11 + i] = down
            self.mem[0xF20 + i] = duty * 2 if i < len(cpu) else 255
            self.mem[0xF30 + i] = self.mem[0xF00 + i]
            if i < 15:
                self.mem[0xF41 + i] = down
            self.mem[0xF50 + i] = self.mem[0xF20 + i]

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump({str(k): v for k, v in self.mem.items()}, f)
        except OSError:
            pass

    def _read(self, addr):
        # fan RPM jitter for a live-looking monitor
        if addr in (0x75B, 0x75C):
            import random
            return max(0, min(200, self.mem.get(addr, 0) + random.randint(-4, 4)))
        return self.mem.get(addr, 0)

    def _smrw(self, key):
        return self.SMAPC[key]

    def _pwup(self, level):
        self.pwup_calls = getattr(self, "pwup_calls", []) + [level]

    def _write(self, addr, val):
        self.mem[addr] = val
        if addr == 0xF5E and val == 0xC9:   # default fan table handshake: EC acknowledges
            self.mem[0xF5D] = 0
            self.mem[0xF5E] = 0
        self._save()


def open_ec(prefer=None):
    """Pick the best available backend. prefer: 'module' | 'acpi_call' | 'mock'."""
    if sys.platform == "win32" and prefer != "mock":
        from .win.acpidrv import WinAcpiDriverEC
        order = [WinAcpiDriverEC]
    else:
        order = {"module": [KernelModuleEC, AcpiCallEC],
                 "acpi_call": [AcpiCallEC, KernelModuleEC],
                 "mock": [MockEC]}.get(prefer or "module", [KernelModuleEC, AcpiCallEC])
    errors = []
    for cls in order:
        try:
            ec = cls()
            log.info("EC backend: %s", ec.name)
            return ec
        except Exception as e:  # noqa: BLE001
            errors.append(f"{cls.name}: {e}")
    raise ECError("no EC backend available: " + "; ".join(errors))
