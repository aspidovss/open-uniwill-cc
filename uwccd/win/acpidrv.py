"""EC access through the OEM driver UWACPIDriver.sys — exactly as MyECIO.AcpiCtrl in GCUService:

  Read : DeviceIoControl(0x9C40A488, in = int32 addr,            out = 4 bytes, value = out & 0xFF)
  Write: DeviceIoControl(0x9C40A48C, in = int32 addr, int32 data, out = 4 bytes)
  SMRW : DeviceIoControl(0x9C40A500, in = {0xBB, key},           out = 4 bytes, value = out[0])
  Method: DeviceIoControl(0x9C40A504, in = {char[4] name, int32 arg}, out = 4 bytes) — MyEcCtrl.SetHWOC("PUWP", level)
          (the driver evaluates the INOU method; GCUService passes the name "PUWP" for the firmware's PWUP)
"""
import struct
import threading

from ..ec import ECBase, ECError
from . import winapi

DEVICE = r"\\.\ACPIDriver"
IOCTL_EC_READ = 0x9C40A488
IOCTL_EC_WRITE = 0x9C40A48C
IOCTL_SMAPC = 0x9C40A500
IOCTL_METHOD = 0x9C40A504


class WinAcpiDriverEC(ECBase):
    name = "ACPIDriver"
    write_delay = 0.010            # AcpiCtrl.DelayTime = 10 ms after every access
    read_delay = 0.010

    def __init__(self):
        super().__init__()
        try:
            self.h = winapi.open_device(DEVICE)
        except OSError as e:
            raise ECError(f"{DEVICE}: {e} — is the OEM driver UWACPIDriver installed?") from e
        self.io = threading.Lock()

    def _read(self, addr):
        with self.io:
            out = winapi.ioctl(self.h, IOCTL_EC_READ, struct.pack("<i", addr), 4)
        return (int.from_bytes(out[:4].ljust(4, b"\0"), "little")) & 0xFF

    def _write(self, addr, val):
        with self.io:
            winapi.ioctl(self.h, IOCTL_EC_WRITE, struct.pack("<ii", addr, val), 4)

    def _pwup(self, level):
        with self.io:
            try:
                winapi.ioctl(self.h, IOCTL_METHOD, b"PUWP" + struct.pack("<i", level), 4)
            except OSError as e:
                raise ECError(f"PWUP: {e}") from e

    def _smrw(self, key):
        with self.io:
            try:
                out = winapi.ioctl(self.h, IOCTL_SMAPC, bytes([0xBB, key]), 4)
            except OSError as e:
                raise ECError(f"SMRW: {e}") from e
        if not out:
            raise ECError("SMRW: empty reply")
        return out[0]

    def close(self):
        winapi.close(self.h)
