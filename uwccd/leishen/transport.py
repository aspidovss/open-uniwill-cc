"""Leishen / Thunderobot (Quanta chassis) — how a command reaches the firmware.

The firmware exposes one 32-byte WMI data block, GUID 644C5791-B7B0-4123-A90B-E93876E0DAAD (WMI class RW_GMWMI in
root\\WMI). Writing the block (ACPI WSAA) runs a command, reading it back (ACPI WQAA) returns the reply in the same
layout:

    u16 a0   0xFA00 = get, 0xFB00 = set   (reply: status; 0x1000 = command not known to this firmware)
    u16 a1   function (0x100 keyboard light, 0x200..0x207 hardware, 0x300 power mode, 0x400 hot-key events)
    u32 a2..a6, two reserved u32

Windows: the WMI driver built into Windows (no vendor driver).  Linux: acpi_call on the WMI device's WSAA / WQAA.
"""
import glob
import logging
import os
import queue
import struct
import sys
import threading

log = logging.getLogger("uwccd.leishen")

GUID = "644C5791-B7B0-4123-A90B-E93876E0DAAD"
WMI_CLASS = "RW_GMWMI"
SIZE = 32
GET, SET = 0xFA00, 0xFB00
UNKNOWN = 0x1000                   # the firmware's answer to a command it does not handle
FMT = "<HH7I"                      # a0, a1, a2..a6, rev0, rev1


class LeishenError(Exception):
    pass


def pack(a0, a1, a2=0, a3=0, a4=0, a5=0, a6=0):
    return struct.pack(FMT, a0 & 0xFFFF, a1 & 0xFFFF, *(int(x) & 0xFFFFFFFF for x in (a2, a3, a4, a5, a6)), 0, 0)


def unpack(b):
    v = struct.unpack(FMT, (bytes(b) + bytes(SIZE))[:SIZE])
    return {"a0": v[0], "a1": v[1], "a2": v[2], "a3": v[3], "a4": v[4], "a5": v[5], "a6": v[6]}


class WinGmWmi:
    """root\\WMI RW_GMWMI.BufferBytes through the WMI service; COM objects live in one worker thread."""
    name = "windows-wmi"

    def __init__(self, timeout=8.0):
        self.timeout = timeout
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.broken = None
        ready = queue.Queue()
        threading.Thread(target=self._loop, args=(ready,), daemon=True, name="leishen-wmi").start()
        ok, err = ready.get(timeout=30)
        if not ok:
            raise LeishenError(err)

    def _loop(self, ready):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            svc = win32com.client.GetObject("winmgmts:{impersonationLevel=impersonate}!\\\\.\\root\\WMI")
            if not list(svc.ExecQuery(f"SELECT * FROM {WMI_CLASS}")):
                raise LeishenError(f"{WMI_CLASS} has no instance")
        except Exception as e:  # noqa: BLE001
            ready.put((False, f"WMI class {WMI_CLASS} not available: {e}"))
            return
        ready.put((True, None))
        while True:
            buf, reply = self.q.get()
            if buf is None:
                break
            try:
                inst = list(svc.ExecQuery(f"SELECT * FROM {WMI_CLASS}"))[0]
                inst.Properties_("BufferBytes").Value = list(buf)
                inst.Put_()                                      # WSAA: the firmware runs the command
                inst = list(svc.ExecQuery(f"SELECT * FROM {WMI_CLASS}"))[0]
                reply.put((True, bytes(bytearray(inst.Properties_("BufferBytes").Value))))   # WQAA
            except Exception as e:  # noqa: BLE001
                reply.put((False, e))

    def call(self, buf):
        if self.broken:
            raise LeishenError(self.broken)
        reply = queue.Queue()
        with self.lock:
            self.q.put((bytes(buf), reply))
            try:
                ok, val = reply.get(timeout=self.timeout)
            except queue.Empty:
                self.broken = f"no answer from the firmware in {self.timeout:.0f} s"
                raise LeishenError(self.broken) from None
        if not ok:
            raise LeishenError(str(val))
        return val

    def close(self):
        self.q.put((None, None))


def linux_wmi_path():
    """ACPI path of the device that holds the data block, from the Linux WMI bus."""
    for d in glob.glob(f"/sys/bus/wmi/devices/{GUID}*"):
        for cand in (os.path.join(os.path.realpath(d), "..", "firmware_node", "path"),
                     os.path.join(os.path.realpath(os.path.join(d, "..")), "firmware_node", "path")):
            try:
                with open(cand) as f:
                    return f.read().strip()
            except OSError:
                continue
    return None


class LinuxAcpiCall:
    """acpi_call module: <device>.WSAA(0, buffer), then <device>.WQAA(0)."""
    name = "acpi_call"
    PROC = "/proc/acpi/call"

    def __init__(self):
        self.path = linux_wmi_path()
        if not self.path:
            raise LeishenError(f"WMI block {GUID} not found")
        if not os.path.exists(self.PROC):
            raise LeishenError("/proc/acpi/call missing (modprobe acpi_call)")
        self.lock = threading.Lock()

    def _acpi(self, cmd):
        with open(self.PROC, "w") as f:
            f.write(cmd)
        with open(self.PROC, "rb") as f:
            out = f.read().split(b"\0")[0].decode(errors="replace").strip()
        if out.startswith("Error"):
            raise LeishenError(f"{cmd}: {out}")
        return out

    def call(self, buf):
        with self.lock:
            self._acpi(f"{self.path}.WSAA 0 b{bytes(buf).hex()}")
            out = self._acpi(f"{self.path}.WQAA 0")
        vals = [int(x, 0) for x in out.strip("{} \n").split(",") if x.strip()]
        return bytes(v & 0xFF for v in vals[:SIZE])

    def close(self):
        pass


class MockGmWmi:
    """Simulated firmware of a Thunderobot R16 (board NLY) for tests and --mock (UWCC_MOCK_LEISHEN=1)."""
    name = "mock"

    def __init__(self, rgb=False):
        self.rgb = rgb or os.environ.get("UWCC_MOCK_LEISHEN_RGB") == "1"
        self.apmd, self.omcc, self.ufa = 1, 0, [0xFF, 0xFF, 0xFF]
        self.win_lock, self.kb_level, self.led = 0, 0, {}
        self.log = []
        self.reply = bytes(SIZE)

    def call(self, buf):
        r = unpack(buf)
        self.log.append(r)
        a0, a1 = r["a0"], r["a1"]
        out = dict(r)
        if a0 == GET:
            if a1 == 0x200:
                manual = self.omcc and self.ufa[0] != 0xFF
                out.update(a2=56, a3=44, a4=2400 if manual else 2100, a5=2000, a6={0: 1, 1: 2, 2: 0}[self.kb_level])
                self.omcc = 1
            elif a1 == 0x201:
                out.update(a0=0x200, a1=0, a2=0x34 if self.rgb else 0x35)
            elif a1 == 0x202:
                out.update(a0=0x114, a2=0, a3=1, a4=1, a5=1, a6=1)
            elif a1 == 0x203:
                out.update(a0=0, a1=0, a2=3, a3=0, a4=3)
            elif a1 == 0x204:
                out.update(a0=0, a1=0, a2=1)
            elif a1 == 0x205:
                out.update(a0=0, a1=0, a2=4)
            elif a1 == 0x206:
                out.update(a2=self.omcc, a3=self.omcc, a4=0)
            elif a1 == 0x207:
                out.update(a0=0, a1=0, a2=44, a3=1800)
            elif a1 == 0x300:
                out.update(a2=self.apmd)
            else:
                out.update(a0=UNKNOWN)
        elif a0 == SET:
            if a1 == 0x300 and r["a2"] in (0, 1, 2):
                self.apmd = r["a2"]
            elif a1 == 0x205:
                self.ufa = [r["a2"] & 0xFF, r["a3"] & 0xFF, r["a4"] & 0xFF]
            elif a1 == 0x206:
                self.omcc = r["a3"] & 0xFF          # the firmware writes a2, then a3
            elif a1 == 0x200 and r["a2"] == 0:
                self.win_lock = 1 if r["a6"] else 0
            elif a1 == 0x100:
                self.led[r["a2"]] = r["a3"]
                self.kb_level = {0: 2, 1: 0, 2: 1}.get((r["a3"] >> 24) & 0x0F, self.kb_level)
                out = unpack(bytes(SIZE))
            elif a1 not in (0x202, 0x203, 0x204, 0x400):
                out.update(a0=UNKNOWN)
        else:
            out.update(a0=UNKNOWN)
        return pack(out["a0"], out["a1"], out["a2"], out["a3"], out["a4"], out["a5"], out["a6"])

    def close(self):
        pass


def open_transport(mock=False):
    if mock:
        if os.environ.get("UWCC_MOCK_LEISHEN") == "1":
            return MockGmWmi(), None
        return None, "mock: no Leishen interface (UWCC_MOCK_LEISHEN=1 simulates one)"
    try:
        return (WinGmWmi() if sys.platform == "win32" else LinuxAcpiCall()), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)
