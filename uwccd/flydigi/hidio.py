"""HID access for the Flydigi coolers: enumeration, open, read with a timeout, write.

Linux: /dev/hidraw* (sysfs for the IDs and the report descriptor). Windows: hid.dll / SetupAPI with overlapped I/O
(a read or write never blocks forever on a handle that died during sleep — the same concern THRM handles with a
non-blocking hidapi read, device.go monitorDeviceData).

The report format follows THRM internal/device/hid_report.go (MIT, Copyright (c) 2025 Tianli): Report ID 0x02 +
frame padded to 25 bytes; except on Linux for the one USB descriptor that declares unnumbered 31-byte output
reports (THRM issue #45), where the frame goes after a 0x00 report number. BS1 over USB uses its own 32-byte
layout (bs1_hid.go buildBS1HIDReport).
"""
import glob
import logging
import os
import select
import sys

from . import proto

log = logging.getLogger("uwccd.flydigi")

IS_WIN = sys.platform == "win32"

VENDOR_ID = 0x37D7                                  # device.go
PID_BS2, PID_BS2PRO, PID_BS3, PID_BS3PRO = 0x1001, 0x1002, 0x1003, 0x1004
# supportedHIDProductIDs: the order THRM tries them in
SUPPORTED_PIDS = (PID_BS2PRO, PID_BS3, PID_BS3PRO, PID_BS2)
MODEL = {PID_BS2: "BS2", PID_BS2PRO: "BS2 Pro", PID_BS3: "BS3", PID_BS3PRO: "BS3 Pro"}
BS1_VID, BS1_PID = 0x04A0, 0x2501                   # bs1_hid.go
BS1_VENDOR_USAGE_PAGE_MIN = 0xFF00
BS1_REPORT_LEN, BS1_OUTPUT_REPORT_ID = 32, 0x01
HID_CONTROL_REPORT_LEN = 25                         # debug.go hidControlReportLen
BUS_USB, BUS_BLUETOOTH = 0x03, 0x05

# hid_report.go flydigiUSBReportDescriptor: 32 input bytes, 31 output bytes, no Report ID item
FLYDIGI_USB_REPORT_DESCRIPTOR = bytes([
    0x06, 0xA0, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0x09, 0x03,
    0x15, 0x80, 0x25, 0x7F, 0x35, 0x00, 0x45, 0xFF,
    0x75, 0x08, 0x95, 0x20, 0x81, 0x02, 0x09, 0x05,
    0x15, 0x80, 0x25, 0x7F, 0x35, 0x00, 0x45, 0xFF,
    0x75, 0x08, 0x95, 0x1F, 0x91, 0x02, 0xC0,
])


def build_hid_report(frame, unnumbered_usb=False, report_len=HID_CONTROL_REPORT_LEN):
    """hidReportFormat.build"""
    if not unnumbered_usb:
        return proto.build_report(frame, report_len)
    if len(frame) > 31:
        raise ValueError(f"USB HID frame of {len(frame)} bytes does not fit the 31-byte output report")
    return (b"\0" + bytes(frame)).ljust(32, b"\0")


def build_bs1_hid_report(frame):
    """buildBS1HIDReport: [0]=0x01, frame without its checksum, 0x00, …, checksum in the last byte."""
    n = len(frame)
    if n < 2 or n >= BS1_REPORT_LEN:
        return None
    r = bytearray(BS1_REPORT_LEN)
    r[0] = BS1_OUTPUT_REPORT_ID
    r[1:n] = frame[:n - 1]
    r[n] = 0
    r[BS1_REPORT_LEN - 1] = frame[n - 1]
    return bytes(r)


def _usage_page(desc):
    """The first Usage Page item of a report descriptor."""
    i = 0
    while i < len(desc):
        b = desc[i]
        size = (0, 1, 2, 4)[b & 3]
        if b & 0xFC == 0x04:
            return int.from_bytes(desc[i + 1:i + 1 + size], "little")
        i += 1 + size
    return None


# -- enumeration ----------------------------------------------------------------------------------------------------
def enumerate_hid(vid, pids=None):
    """[{path, vid, pid, bus, name, usage_page, descriptor, output_len, input_len}] in the system's order."""
    return _enum_win(vid, pids) if IS_WIN else _enum_linux(vid, pids)


def _enum_linux(vid, pids):
    out = []
    for d in sorted(glob.glob("/sys/class/hidraw/hidraw*"), key=lambda p: int(p.rsplit("hidraw", 1)[1] or 0)):
        try:
            with open(os.path.join(d, "device", "uevent")) as f:
                ue = dict(line.strip().split("=", 1) for line in f if "=" in line)
            bus, v, p = (int(x, 16) for x in ue.get("HID_ID", "0:0:0").split(":"))
        except (OSError, ValueError):
            continue
        if v != vid or (pids is not None and p not in pids):
            continue
        try:
            with open(os.path.join(d, "device", "report_descriptor"), "rb") as f:
                desc = f.read()
        except OSError:
            desc = b""
        out.append({"path": "/dev/" + os.path.basename(d), "vid": v, "pid": p, "bus": bus,
                    "name": ue.get("HID_NAME", ""), "usage_page": _usage_page(desc), "descriptor": desc,
                    "output_len": None, "input_len": None})
    return out


def _enum_win(vid, pids):
    from ..win.hid import enumerate_devices
    out = []
    for d in enumerate_devices(vid, set(pids) if pids is not None else None):
        out.append({"path": d["node"], "vid": d["vid"], "pid": d["pid"], "bus": None, "name": "",
                    "usage_page": d.get("usage_page"), "descriptor": b"",
                    "output_len": d.get("output_len"), "input_len": d.get("input_len")})
    return out


# -- transports -----------------------------------------------------------------------------------------------------
class HidrawDevice:
    def __init__(self, info):
        self.info = info
        self.fd = os.open(info["path"], os.O_RDWR | os.O_NONBLOCK)

    def read(self, timeout):
        """One input report, or None after `timeout` seconds."""
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        try:
            return os.read(self.fd, 64)
        except BlockingIOError:
            return None
        except InterruptedError:                 # isInterruptedHIDRead: the connection is still fine
            return None

    def write(self, report):
        n = os.write(self.fd, bytes(report))
        if n < len(report):                         # writeHIDReport: a short write is an error
            raise OSError(f"HID write {n}/{len(report)} bytes")

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p), ("Offset", wintypes.DWORD),
                    ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]

    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.HANDLE]
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                              ctypes.POINTER(OVERLAPPED)]
    _k32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                               ctypes.POINTER(OVERLAPPED)]
    _k32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED), ctypes.POINTER(wintypes.DWORD),
                                         wintypes.BOOL]
    _k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k32.WaitForSingleObject.restype = wintypes.DWORD
    _k32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
    _k32.ResetEvent.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _INVALID = wintypes.HANDLE(-1).value
    ERROR_IO_PENDING, WAIT_OBJECT_0, WAIT_TIMEOUT = 997, 0, 0x102
    WRITE_TIMEOUT_MS = 1000

    class WinHidDevice:
        def __init__(self, info):
            self.info = info
            h = _k32.CreateFileW(info["path"], 0xC0000000, 3, None, 3, 0x40000000, None)   # RW, share RW, overlapped
            if h in (None, _INVALID):
                raise ctypes.WinError(ctypes.get_last_error())
            self.h = h
            self.ilen = info.get("input_len") or 64
            self.olen = info.get("output_len") or 0
            self.rev = _k32.CreateEventW(None, True, False, None)
            self.wev = _k32.CreateEventW(None, True, False, None)
            self.rov = OVERLAPPED(hEvent=self.rev)
            self.rbuf = ctypes.create_string_buffer(self.ilen)
            self.pending = False

        def read(self, timeout):
            if not self.pending:
                _k32.ResetEvent(self.rev)
                n = wintypes.DWORD(0)
                if _k32.ReadFile(self.h, self.rbuf, self.ilen, ctypes.byref(n), ctypes.byref(self.rov)):
                    return self.rbuf.raw[:n.value]
                err = ctypes.get_last_error()
                if err != ERROR_IO_PENDING:
                    raise ctypes.WinError(err)
                self.pending = True
            if _k32.WaitForSingleObject(self.rev, int(timeout * 1000)) != WAIT_OBJECT_0:
                return None                              # the read stays pending for the next call
            self.pending = False
            n = wintypes.DWORD(0)
            if not _k32.GetOverlappedResult(self.h, ctypes.byref(self.rov), ctypes.byref(n), False):
                raise ctypes.WinError(ctypes.get_last_error())
            return self.rbuf.raw[:n.value]

        def write(self, report):
            data = bytes(report)
            if self.olen and len(data) < self.olen:      # hidapi pads to OutputReportByteLength as well
                data = data.ljust(self.olen, b"\0")
            elif self.olen and len(data) > self.olen and not data[self.olen:].strip(b"\0"):
                data = data[:self.olen]                  # a shorter report: only padding is dropped
            buf = ctypes.create_string_buffer(data, len(data))
            _k32.ResetEvent(self.wev)
            ov = OVERLAPPED(hEvent=self.wev)
            n = wintypes.DWORD(0)
            if not _k32.WriteFile(self.h, buf, len(data), ctypes.byref(n), ctypes.byref(ov)):
                err = ctypes.get_last_error()
                if err != ERROR_IO_PENDING:
                    raise ctypes.WinError(err)
                if _k32.WaitForSingleObject(self.wev, WRITE_TIMEOUT_MS) != WAIT_OBJECT_0:
                    _k32.CancelIoEx(self.h, ctypes.byref(ov))
                    _k32.GetOverlappedResult(self.h, ctypes.byref(ov), ctypes.byref(n), True)
                    raise TimeoutError("HID write timed out")
                if not _k32.GetOverlappedResult(self.h, ctypes.byref(ov), ctypes.byref(n), False):
                    raise ctypes.WinError(ctypes.get_last_error())
            if n.value < len(data):
                raise OSError(f"HID write {n.value}/{len(data)} bytes")

        def close(self):
            h, self.h = self.h, None
            if not h:
                return
            if self.pending:
                n = wintypes.DWORD(0)
                _k32.CancelIoEx(h, ctypes.byref(self.rov))
                _k32.GetOverlappedResult(h, ctypes.byref(self.rov), ctypes.byref(n), True)
                self.pending = False
            _k32.CloseHandle(h)
            _k32.CloseHandle(self.rev)
            _k32.CloseHandle(self.wev)


def open_device(info):
    return WinHidDevice(info) if IS_WIN else HidrawDevice(info)


def unnumbered_usb(info):
    """hidReportFormatForDescriptor: only on Linux, only over USB, only for the known descriptor."""
    return (not IS_WIN and info.get("bus") == BUS_USB
            and bytes(info.get("descriptor") or b"") == FLYDIGI_USB_REPORT_DESCRIPTOR)
