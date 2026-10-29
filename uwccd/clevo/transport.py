"""Control Center 3.0 / Clevo — how a DCHU command reaches the firmware.

Every transport offers call(cmd, data, length) -> Reply: the firmware evaluates _DSM function `cmd` with a buffer
argument (`length` bytes of `data`, zero padded) and returns an integer or a buffer.
"""
import logging
import os
import struct
import sys
import threading
import uuid
from dataclasses import dataclass

log = logging.getLogger("uwccd.clevo")

DSM_UUID = uuid.UUID("93f224e4-fbdc-4bbf-add6-db71bdc0afad")
WIN_INTERFACE = uuid.UUID("86994c74-ad43-4812-b7e7-0c420b5c5fd7")    # device interface of the Control Center 3 driver
WIN_IOCTL = 0x322400
WIN_IN_SIZE = 0x420
WIN_OUT_SIZE = 0x40C
BUF = 256


class ClevoError(Exception):
    pass


@dataclass
class Reply:
    kind: str = "none"            # "int" | "buffer" | "none"
    value: int = 0
    data: bytes = b""

    def buffer(self, n=BUF):
        return (self.data + bytes(n))[:n]


def _pad(data, length):
    data = bytes(data or b"")
    if len(data) > BUF:
        raise ValueError("DCHU argument longer than 256 bytes")
    return data + bytes(max(0, length - len(data)))


def win_request(cmd, data, length=BUF):
    """Input of IOCTL 0x322400: _DSM UUID, revision, method name, function, one buffer argument (256 bytes)."""
    arg = _pad(data, BUF)[:BUF]
    head = DSM_UUID.bytes_le + struct.pack("<I4sIHHH", 0, b"_DSM", cmd, 4 + BUF, 2, BUF)
    return (head + arg).ljust(WIN_IN_SIZE, b"\0")


def win_reply(out):
    """ACPI_EVAL_OUTPUT_BUFFER: signature, length, count, then {u16 type, u16 length, data} per argument."""
    if len(out) < 12:
        return Reply()
    _sig, _ln, count = struct.unpack_from("<III", out, 0)
    off = 12
    for _ in range(min(count, 16)):
        if off + 4 > len(out):
            break
        t, ln = struct.unpack_from("<HH", out, off)
        body = out[off + 4:off + 4 + ln]
        if t == 0:
            return Reply("int", struct.unpack("<I", (body + bytes(4))[:4])[0])
        if t == 2:
            return Reply("buffer", data=bytes(body))
        off += 4 + max(4, ln)
    return Reply()


class WinDchu:
    """The driver of Control Center 3 (installed with the Clevo/OEM driver package; Control Center 3 itself may be
    closed). Opened through its device interface; one call at a time."""
    name = "windows-cc3-driver"

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.lock = threading.Lock()

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

        g = GUID.from_buffer_copy(WIN_INTERFACE.bytes_le)
        cfg = ctypes.WinDLL("cfgmgr32")
        size = wintypes.ULONG(0)
        cr = cfg.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), ctypes.byref(g), None, 0)
        if cr != 0 or size.value <= 1:
            raise ClevoError("Control Center 3 driver interface not present")
        buf = ctypes.create_unicode_buffer(size.value)
        cr = cfg.CM_Get_Device_Interface_ListW(ctypes.byref(g), None, buf, size, 0)
        if cr != 0 or not buf.value:
            raise ClevoError(f"Control Center 3 driver interface list failed (CR {cr})")
        self.path = buf.value
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.DeviceIoControl.restype = wintypes.BOOL
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                        wintypes.LPVOID]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.k32 = k32
        h = k32.CreateFileW(self.path, 0xC0000000, 3, None, 3, 0x80, None)
        if h in (None, wintypes.HANDLE(-1).value):
            raise ClevoError(f"cannot open the Control Center 3 driver (error {ctypes.get_last_error()})")
        self.h = h
        log.info("Clevo DCHU: Control Center 3 driver %s", self.path)

    def call(self, cmd, data=b"", length=4):
        ct = self.ct
        inb = ct.create_string_buffer(win_request(cmd, data, length), WIN_IN_SIZE)
        outb = ct.create_string_buffer(WIN_OUT_SIZE)
        got = ct.c_ulong(0)
        with self.lock:
            ok = self.k32.DeviceIoControl(self.h, WIN_IOCTL, inb, WIN_IN_SIZE, outb, WIN_OUT_SIZE,
                                          ct.byref(got), None)
        if not ok:
            raise ClevoError(f"DCHU 0x{cmd:02X}: DeviceIoControl error {ct.get_last_error()}")
        return win_reply(outb.raw[:got.value or WIN_OUT_SIZE])

    def close(self):
        try:
            self.k32.CloseHandle(self.h)
        except Exception:  # noqa: BLE001
            pass


class LinuxDchu:
    """/dev/uwcc, ioctl UWCC_IOC_CLEVO (kernel/uwcc.c from 1.6.6)."""
    name = "uwcc-module"
    DEV = "/dev/uwcc"
    FMT = "<IIIII256s256s"
    IOC = (3 << 30) | (struct.calcsize(FMT) << 16) | (ord("u") << 8) | 5

    def __init__(self):
        import fcntl
        self.fcntl = fcntl
        self.lock = threading.Lock()
        self.fd = os.open(self.DEV, os.O_RDWR | os.O_CLOEXEC)
        try:
            self.call(0x10)               # capability bits: ENODEV without a Clevo interface, ENOTTY with an old module
        except OSError as e:
            os.close(self.fd)
            raise ClevoError(f"/dev/uwcc: {e}") from e

    def call(self, cmd, data=b"", length=4):
        length = max(1, min(BUF, length))
        buf = bytearray(struct.pack(self.FMT, cmd, length, 0, 0, 0, _pad(data, BUF), bytes(BUF)))
        with self.lock:
            self.fcntl.ioctl(self.fd, self.IOC, buf, True)
        _c, _l, kind, val, n, _in, out = struct.unpack(self.FMT, buf)
        if kind == 0:
            return Reply("int", val)
        if kind == 2:
            return Reply("buffer", data=bytes(out[:n]))
        return Reply()

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


class MockDchu:
    """Simulated Clevo firmware (tests, --mock with UWCC_MOCK_CLEVO=1): two fans, RGB keyboard, all features."""
    name = "mock"

    def __init__(self):
        self.log = []
        self.fan_mode = 0
        self.lock = threading.Lock()

    def call(self, cmd, data=b"", length=4):
        data = _pad(data, BUF)
        with self.lock:
            self.log.append((cmd, bytes(data[:max(4, length)])))
        if cmd == 0x10:
            return Reply("int", 0x01 | 0x10 | 0x80)                    # power modes, RGB keyboard, fan setting
        if cmd == 0x7A:
            return Reply("int", 0x01 | 0x10 | (1 << 28))               # fan speed, custom fan, KB LED sleep
        if cmd == 0x60:
            return Reply("int", 1 << 7)                                # anti-dust
        if cmd in (0x46, 0x52):
            return Reply("int", 0)
        if cmd == 0x0C:
            b = bytearray(BUF)
            struct.pack_into(">HHH", b, 2, 2156250 // 3200, 2156250 // 2900, 0)
            b[16], b[18], b[19], b[21] = 110, 58, 95, 51
            return Reply("buffer", data=bytes(b))
        if cmd == 0x0D:
            b = bytearray(BUF)
            b[12], b[14] = 2, 0
            b[16:22] = bytes([30, 0, 60, 102, 80, 191])
            b[24:30] = bytes([30, 0, 60, 89, 78, 178])
            return Reply("buffer", data=bytes(b))
        if cmd == 0x04:
            idx = data[1]
            txt = b"07.04$" + bytes(20)
            out = bytearray(BUF)
            out[1:6] = txt[(idx - 1) * 5:(idx - 1) * 5 + 5] if idx else b"\0" * 5
            return Reply("buffer", data=bytes(out))
        if cmd == 0x79 and data[3] == 0x01:
            self.fan_mode = data[0]
        return Reply("int", 0)

    def close(self):
        pass


def open_transport(mock=False):
    """The Clevo DCHU path of this machine, or None (with the reason) when there is none."""
    if mock:
        if os.environ.get("UWCC_MOCK_CLEVO") == "1":
            return MockDchu(), None
        return None, "mock: no Clevo interface (UWCC_MOCK_CLEVO=1 simulates one)"
    try:
        return (WinDchu() if sys.platform == "win32" else LinuxDchu()), None
    except FileNotFoundError:
        return None, "/dev/uwcc not present (kernel module not loaded)"
    except Exception as e:  # noqa: BLE001
        return None, str(e)
