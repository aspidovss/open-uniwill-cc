"""HID access for the ITE keyboard controller through SetupAPI + hid.dll (no third-party library)."""
import ctypes
import logging
from ctypes import wintypes

from . import winapi

log = logging.getLogger("uwccd.hid")

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
HIDP_STATUS_SUCCESS = 0x00110000


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wintypes.DWORD),
                ("Reserved", ctypes.c_size_t)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT), ("ProductID", wintypes.USHORT),
                ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT), ("InputReportByteLength", wintypes.USHORT),
                ("OutputReportByteLength", wintypes.USHORT), ("FeatureReportByteLength", wintypes.USHORT),
                ("Reserved", wintypes.USHORT * 17), ("Counts", wintypes.USHORT * 10)]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOLEAN
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_GetFeature.restype = wintypes.BOOLEAN
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.POINTER(GUID), wintypes.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                                      wintypes.LPVOID]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]


def _caps(h):
    pp = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
        return None
    try:
        caps = HIDP_CAPS()
        if hid.HidP_GetCaps(pp, ctypes.byref(caps)) != HIDP_STATUS_SUCCESS:
            return None
        return caps
    finally:
        hid.HidD_FreePreparsedData(pp)


def enumerate_devices(vid, pids):
    """[{node: device path, pid, usage_page, feature_len, output_len}] for the given VID/PIDs."""
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev in (None, winapi.INVALID_HANDLE_VALUE):
        return []
    out = []
    try:
        i = 0
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA()
            ifd.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), i, ctypes.byref(ifd)):
                break
            i += 1
            need = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifd), None, 0, ctypes.byref(need), None)
            if not need.value:
                continue
            buf = ctypes.create_string_buffer(need.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 8 on 64-bit, 6 on 32-bit
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifd), buf, need, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            try:
                h = winapi.open_device(path, 0)            # attributes/caps need no access rights
            except OSError:
                continue
            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                if not hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
                    continue
                if attrs.VendorID != vid or attrs.ProductID not in pids:
                    continue
                caps = _caps(h)
                out.append({"node": path, "pid": attrs.ProductID,
                            "usage_page": caps.UsagePage if caps else None,
                            "feature_len": caps.FeatureReportByteLength if caps else 9,
                            "output_len": caps.OutputReportByteLength if caps else 65})
            finally:
                winapi.close(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return out


class WinHidTransport:
    """feature() / get_feature() / output() with the same semantics as the Linux hidraw transport."""

    def __init__(self, dev):
        self.dev = dev
        self.h = winapi.open_device(dev["node"])
        self.flen = dev.get("feature_len") or 9
        self.olen = dev.get("output_len") or 65

    def feature(self, data):
        buf = bytes(data)[:self.flen].ljust(self.flen, b"\0")
        b = ctypes.create_string_buffer(buf, len(buf))
        if not hid.HidD_SetFeature(self.h, b, len(buf)):
            raise winapi.win_error("HidD_SetFeature")

    def get_feature(self, size=9):
        n = max(size, self.flen)
        b = ctypes.create_string_buffer(n)
        if not hid.HidD_GetFeature(self.h, b, n):
            raise winapi.win_error("HidD_GetFeature")
        return bytearray(b.raw[:size])

    def output(self, data):
        buf = bytes(data)[:self.olen].ljust(self.olen, b"\0")
        winapi.write_file(self.h, buf)

    def close(self):
        winapi.close(self.h)
