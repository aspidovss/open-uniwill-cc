"""Thin ctypes layer over the Win32 calls the service and the tray need (no pywin32 required here)."""
import ctypes
import os
import uuid
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
kernel32.DeviceIoControl.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
kernel32.WriteFile.restype = wintypes.BOOL


def win_error(what):
    code = ctypes.get_last_error()
    return OSError(code, f"{what}: {ctypes.FormatError(code).strip()} (error {code})")


def open_device(path, access=GENERIC_READ | GENERIC_WRITE):
    h = kernel32.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if h in (None, INVALID_HANDLE_VALUE):
        raise win_error(f"CreateFile {path}")
    return h


def close(h):
    if h and h != INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(h)


def ioctl(h, code, inbuf, out_size):
    inb = ctypes.create_string_buffer(bytes(inbuf), len(inbuf))
    outb = ctypes.create_string_buffer(out_size)
    ret = wintypes.DWORD(0)
    if not kernel32.DeviceIoControl(h, code, inb, len(inbuf), outb, out_size, ctypes.byref(ret), None):
        raise win_error(f"DeviceIoControl 0x{code:08X}")
    return outb.raw[:ret.value]


def write_file(h, data):
    n = wintypes.DWORD(0)
    buf = ctypes.create_string_buffer(bytes(data), len(data))
    if not kernel32.WriteFile(h, buf, len(data), ctypes.byref(n), None):
        raise win_error("WriteFile")
    return n.value


kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetTickCount.restype = wintypes.DWORD
kernel32.GetTickCount64.restype = ctypes.c_ulonglong
kernel32.QueryUnbiasedInterruptTime.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID]
advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, wintypes.LPVOID, wintypes.DWORD,
                                           wintypes.LPVOID, wintypes.LPVOID]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]

# -- privileges (SeSystemEnvironmentPrivilege for UEFI variables) ---------------------------------------
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def enable_privilege(name):
    TOKEN_ADJUST_PRIVILEGES, TOKEN_QUERY, SE_PRIVILEGE_ENABLED = 0x20, 0x8, 0x2
    tok = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(tok)):
        raise win_error("OpenProcessToken")
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            raise win_error("LookupPrivilegeValue")
        tp = TOKEN_PRIVILEGES(1, (LUID_AND_ATTRIBUTES * 1)(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED)))
        ctypes.set_last_error(0)
        advapi32.AdjustTokenPrivileges(tok, False, ctypes.byref(tp), 0, None, None)
        if ctypes.get_last_error() != 0:            # ERROR_NOT_ALL_ASSIGNED
            raise win_error(f"AdjustTokenPrivileges {name}")
    finally:
        kernel32.CloseHandle(tok)


kernel32.GetFirmwareEnvironmentVariableExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
                                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetFirmwareEnvironmentVariableExW.restype = wintypes.DWORD
kernel32.SetFirmwareEnvironmentVariableExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
                                                       wintypes.DWORD, wintypes.DWORD]
kernel32.SetFirmwareEnvironmentVariableExW.restype = wintypes.BOOL


def get_firmware_var(name, guid):
    """-> (attributes, bytes) or raises OSError (ERROR_ENVVAR_NOT_FOUND = 203)."""
    buf = ctypes.create_string_buffer(4096)
    attrs = wintypes.DWORD(0)
    n = kernel32.GetFirmwareEnvironmentVariableExW(name, "{%s}" % guid, buf, len(buf), ctypes.byref(attrs))
    if n == 0:
        raise win_error(f"GetFirmwareEnvironmentVariable {name}")
    return attrs.value, buf.raw[:n]


def set_firmware_var(name, guid, data, attrs):
    buf = ctypes.create_string_buffer(bytes(data), len(data))
    if not kernel32.SetFirmwareEnvironmentVariableExW(name, "{%s}" % guid, buf, len(data), attrs):
        raise win_error(f"SetFirmwareEnvironmentVariable {name}")


# -- power ------------------------------------------------------------------------------------------------
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


def power_status():
    s = SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return None
    return s


def interrupt_times():
    """(wall-clock ms since boot incl. sleep, ms since boot excluding sleep) — a gap means suspend/resume."""
    unbiased = ctypes.c_ulonglong(0)
    kernel32.QueryUnbiasedInterruptTime(ctypes.byref(unbiased))
    return kernel32.GetTickCount64(), unbiased.value // 10000


# Windows 10/11 power mode slider (overlay schemes)
OVERLAY = {"power-saver": "961cc777-2547-4f9d-8174-7d86181b8a7a",
           "balanced": "00000000-0000-0000-0000-000000000000",
           "performance": "ded574b5-45a0-4f42-8737-46345c09c238"}


def set_power_overlay(name):
    powrprof = ctypes.WinDLL("powrprof")
    g = uuid.UUID(OVERLAY[name])
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(g.bytes_le)
    rc = powrprof.PowerSetActiveOverlayScheme(ctypes.byref(guid))
    if rc != 0:
        raise OSError(rc, f"PowerSetActiveOverlayScheme {name}: {rc}")


# -- input (tray) -------------------------------------------------------------------------------------------
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(li)):
        return 0
    return ((kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


def send_keys(*vks):
    """Press the virtual keys in order and release them in reverse (e.g. Win+Ctrl+F24 toggles the touchpad)."""
    KEYEVENTF_KEYUP = 2
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


VK_LWIN, VK_CONTROL, VK_F24 = 0x5B, 0x11, 0x87


def program_data():
    return os.environ.get("ProgramData", r"C:\ProgramData")
