"""Windows, user session (tray program): input for the BetterRGB effects of the service.

The service runs as SYSTEM in session 0 and cannot see the keyboard, the screen or the audio of the user. While an
effect needs them (the answer of POST /api/keyboard/fx/input lists what it needs), this thread sends:
  * keys    — names of newly pressed keys (GetAsyncKeyState, 60 times a second) for the reactive effects;
  * screen  — a 64 x 24 picture of the main screen (GDI StretchBlt, 15 times a second) for Screen ambient;
  * volume / mic / audio — master volume, microphone and playback peak levels (Core Audio) for the top-row bar.
Nothing is written to disk; nothing is sent while no effect needs it.
"""
import base64
import ctypes
import logging
import time
import uuid
from ctypes import POINTER, byref, c_float, c_int, c_void_p, wintypes

from ..lighting.fx import VK

log = logging.getLogger("uwcc.fxinput")

SCREEN_W, SCREEN_H = 64, 24


# ----------------------------------------------------------------------------------- keys
class Keys:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32")
        self.user32.GetAsyncKeyState.argtypes = [c_int]
        self.user32.GetAsyncKeyState.restype = ctypes.c_short
        self.down = set()

    def poll(self):
        pressed = []
        for vk, name in VK.items():
            if self.user32.GetAsyncKeyState(vk) & 0x8000:
                if vk not in self.down:
                    self.down.add(vk)
                    pressed.append(name)
            else:
                self.down.discard(vk)
        return pressed


# ----------------------------------------------------------------------------------- screen
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class Screen:
    """GDI capture of the primary screen, scaled down to SCREEN_W x SCREEN_H by the graphics driver (HALFTONE)"""

    def __init__(self):
        u, g = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
        u.GetDC.restype = wintypes.HDC
        u.GetDC.argtypes = [wintypes.HWND]
        u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        g.CreateCompatibleDC.restype = wintypes.HDC
        g.CreateCompatibleDC.argtypes = [wintypes.HDC]
        g.CreateDIBSection.restype = wintypes.HBITMAP
        g.CreateDIBSection.argtypes = [wintypes.HDC, c_void_p, wintypes.UINT, POINTER(c_void_p), wintypes.HANDLE,
                                       wintypes.DWORD]
        g.SelectObject.restype = wintypes.HGDIOBJ
        g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        g.StretchBlt.argtypes = [wintypes.HDC, c_int, c_int, c_int, c_int, wintypes.HDC, c_int, c_int, c_int, c_int,
                                 wintypes.DWORD]
        g.SetStretchBltMode.argtypes = [wintypes.HDC, c_int]
        g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        g.DeleteDC.argtypes = [wintypes.HDC]
        self.u, self.g = u, g
        self.screen = u.GetDC(None)
        self.mem = g.CreateCompatibleDC(self.screen)
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), SCREEN_W, -SCREEN_H, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = c_void_p()
        self.bmp = g.CreateDIBSection(self.mem, byref(bi), 0, byref(self.bits), None, 0)
        if not (self.screen and self.mem and self.bmp and self.bits):
            self.close()
            raise OSError("GDI capture could not be prepared")
        self.old = g.SelectObject(self.mem, self.bmp)
        g.SetStretchBltMode(self.mem, 4)                      # HALFTONE
        g.SetBrushOrgEx.argtypes = [wintypes.HDC, c_int, c_int, c_void_p]
        g.SetBrushOrgEx(self.mem, 0, 0, None)

    def grab(self):
        w, h = self.u.GetSystemMetrics(0), self.u.GetSystemMetrics(1)     # SM_CXSCREEN / SM_CYSCREEN
        if not self.g.StretchBlt(self.mem, 0, 0, SCREEN_W, SCREEN_H, self.screen, 0, 0, w, h,
                                 0x00CC0020 | 0x40000000):              # SRCCOPY | CAPTUREBLT
            return None
        raw = ctypes.string_at(self.bits.value, SCREEN_W * SCREEN_H * 4)
        rgb = bytearray(SCREEN_W * SCREEN_H * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]       # BGRA -> RGB
        return {"w": SCREEN_W, "h": SCREEN_H, "rgb": base64.b64encode(bytes(rgb)).decode()}

    def close(self):
        if getattr(self, "old", None):
            self.g.SelectObject(self.mem, self.old)
        if getattr(self, "bmp", None):
            self.g.DeleteObject(self.bmp)
        if getattr(self, "mem", None):
            self.g.DeleteDC(self.mem)
        if getattr(self, "screen", None):
            self.u.ReleaseDC(None, self.screen)
        self.bmp = self.mem = self.screen = self.old = None


# ----------------------------------------------------------------------------------- audio (Core Audio over ctypes)
class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, s):
        return cls.from_buffer_copy(uuid.UUID(s).bytes_le)


CLSID_MMDeviceEnumerator = GUID.of("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID.of("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioEndpointVolume = GUID.of("5CDF2C82-841E-4546-9722-0CF74078229A")
IID_IAudioMeterInformation = GUID.of("C02216F6-8C67-4B5B-9D00-D008E73E0064")
CLSCTX_ALL = 0x17


def _method(obj, index, *argtypes):
    """IUnknown-based COM call: the index-th function of the object's vtable"""
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(vtbl[index])
    return lambda *a: fn(obj, *a)


def _release(obj):
    if obj:
        try:
            ctypes.WINFUNCTYPE(wintypes.ULONG, c_void_p)(ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents[2])(obj)
        except OSError:
            pass


class Audio:
    def __init__(self):
        self.ole = ctypes.WinDLL("ole32")
        self.ole.CoInitializeEx(None, 0)                     # COINIT_MULTITHREADED, this thread only
        self.enum = c_void_p()
        self.ole.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, byref(IID_IMMDeviceEnumerator),
                                  byref(self.enum))
        if not self.enum:
            raise OSError("MMDeviceEnumerator not available")
        self.objs = {}
        self.refreshed = 0.0

    def _activate(self, flow, iid):
        dev = c_void_p()
        try:
            _method(self.enum, 4, c_int, c_int, POINTER(c_void_p))(flow, 1, byref(dev))   # GetDefaultAudioEndpoint
        except OSError:                   # no such device (no microphone)
            return None
        if not dev:
            return None
        out = c_void_p()
        try:
            _method(dev, 3, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p))(byref(iid), CLSCTX_ALL, None,
                                                                                        byref(out))
        except OSError:
            out = c_void_p()
        _release(dev)
        return out if out else None

    def refresh(self):
        """the default devices may change (headphones): take them again every few seconds"""
        for o in self.objs.values():
            _release(o)
        self.objs = {"volume": self._activate(0, IID_IAudioEndpointVolume),
                     "audio": self._activate(0, IID_IAudioMeterInformation),
                     "mic": self._activate(1, IID_IAudioMeterInformation)}
        self.refreshed = time.monotonic()

    def read(self, wanted):
        if time.monotonic() - self.refreshed > 3:
            self.refresh()
        out = {}
        v = self.objs.get("volume")
        if v and "volume" in wanted:
            level, mute = c_float(), wintypes.BOOL()
            try:
                _method(v, 9, POINTER(c_float))(byref(level))               # GetMasterVolumeLevelScalar
                _method(v, 15, POINTER(wintypes.BOOL))(byref(mute))         # GetMute
                out["volume"] = 0.0 if mute.value else float(level.value)
            except OSError:
                self.refreshed = 0
        for key in ("audio", "mic"):
            m = self.objs.get(key)
            if m and key in wanted:
                peak = c_float()
                try:
                    _method(m, 3, POINTER(c_float))(byref(peak))            # GetPeakValue
                    out[key] = float(peak.value)
                except OSError:
                    self.refreshed = 0
        return out

    def close(self):
        for o in self.objs.values():
            _release(o)
        _release(self.enum)
        self.objs, self.enum = {}, None


# ----------------------------------------------------------------------------------- loop
def run(post):
    """post(body) -> answer of /api/keyboard/fx/input ({"needs": [...]}); runs forever in a daemon thread"""
    needs, asked = [], 0.0
    keys = screen = audio = None
    next_screen = next_audio = 0.0
    while True:
        now = time.monotonic()
        body = {}
        try:
            if "keys" in needs:
                keys = keys or Keys()
                pressed = keys.poll()
                if pressed:
                    body["keys"] = pressed
            if "screen" in needs and now >= next_screen:
                next_screen = now + 1 / 15.0
                if screen is None:
                    screen = Screen()
                shot = screen.grab()
                if shot:
                    body["screen"] = shot
            elif "screen" not in needs and screen:
                screen.close()
                screen = None
            wanted = {k for k in ("volume", "mic", "audio") if k in needs}
            if wanted and now >= next_audio:
                next_audio = now + 0.1
                if audio is None:
                    audio = Audio()
                body["metrics"] = audio.read(wanted)
            elif not wanted and audio:
                audio.close()
                audio = None
        except Exception as e:  # noqa: BLE001
            log.warning("fx input: %s", e)
            if screen:
                screen.close()
            keys = screen = None
            audio = None
            next_screen = next_audio = now + 5
        if body or now - asked > 2.0:
            try:
                needs = list((post(body) or {}).get("needs") or [])
            except Exception:  # noqa: BLE001
                needs = []
            asked = now
        time.sleep(1 / 60.0 if needs else 1.0)
