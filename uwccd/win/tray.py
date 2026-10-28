"""ControlCenter.exe — the user-session part on Windows.

Lives in the notification area (hidden by default), starts with Windows, and:
  * opens the Control Center window (Microsoft Edge in app mode on the local web UI);
  * quick menu: mode, Fan Boost, keyboard backlight, liquid cooler, language, autostart;
  * shows notifications for service events (mode key, overheating, coolant flow, ...);
  * reports user idle time for the keyboard-backlight auto-off (a service cannot see input);
  * sends key presses, a small screen picture and audio levels while a BetterRGB effect needs them (fxinput.py);
  * toggles the touchpad with Win+Ctrl+F24 when the touchpad key is pressed.

  ControlCenter.exe            tray only (what the Run key starts)
  ControlCenter.exe --show     tray + open the window
  ControlCenter.exe --open     open the window of the running instance (or start it)
"""
import ctypes
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import winreg

import pystray
from PIL import Image, ImageDraw

from .. import agentcore, updates
from . import winapi, winplat
from .winplat import data_root

PORT = int(os.environ.get("UWCC_PORT", "47321"))
TOKEN_FILE = os.path.join(data_root(), "run", "token")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
RUN_NAME = "UWCC Control Center"
MUTEX = "Local\\UWCC-ControlCenter-Tray"
OPEN_EVENT = "Local\\UWCC-ControlCenter-Open"
EDGE = [os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")]

log = logging.getLogger("uwcc.tray")


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for p in (os.path.join(base, "uwccd", "web", name), os.path.join(base, "web", name),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", name)):
        if os.path.exists(p):
            return p
    return None


def make_icon(mode=None, offline=False):
    p = resource("icon.png")
    if p:
        img = Image.open(p).convert("RGBA").resize((64, 64))
    else:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), 14, fill=(14, 18, 21, 255), outline=(50, 219, 190, 255), width=4)
        d.polygon([(36, 12), (18, 36), (31, 36), (27, 52), (46, 26), (33, 26)], fill=(50, 219, 190, 255))
    d = ImageDraw.Draw(img)
    color = {0: (155, 231, 255), 1: (50, 219, 190), 2: (255, 138, 101), 3: (200, 160, 255)}.get(mode)
    if offline:
        color = (255, 93, 108)
    if color:
        d.ellipse((42, 42, 62, 62), fill=color + (255,), outline=(0, 0, 0, 255), width=2)
    return img


class Api:
    def __init__(self):
        self.token = None

    def _tok(self):
        if not self.token:
            with open(TOKEN_FILE) as f:
                self.token = f.read().strip()
        return self.token

    def call(self, path, body=None, timeout=15):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/{path}", method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-UWCC-Token": self._tok(), "Content-Type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self.token = None
            raise

    def events(self):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/events?client=tray&token={self._tok()}")
        return urllib.request.urlopen(req, timeout=60)


class Tray:
    def __init__(self, show):
        self.api = Api()
        self.state = None
        self.lang = "en"
        self.offline_since = None
        self.offline_notified = False
        self.icon = pystray.Icon("uwcc", make_icon(offline=True), "Control Center", menu=pystray.Menu(self.menu_items))
        self.show_at_start = show
        self.idle_sent = None

    # -- helpers -----------------------------------------------------------------------------
    def T(self, key, *a):
        return agentcore.T(self.lang, key, *a)

    def refresh(self):
        try:
            self.state = self.api.call("state")
            self.lang = self.state["settings"].get("lang", "en")
            self.offline_since = None
            self.offline_notified = False
        except (OSError, ValueError):
            self.state = None
            self.offline_since = self.offline_since or time.time()
        self.update_icon()

    def update_icon(self):
        st = self.state
        if not st:
            self.icon.icon = make_icon(offline=True)
            self.icon.title = "Control Center — " + self.T("offline")
        else:
            mode = st["power"]["mode"] if st["platform"].get("fan_control") else None
            self.icon.icon = make_icon(mode)
            name = self.mode_name(mode) if mode is not None else ""
            lc = st.get("liquid") or {}
            extra = f" · 💧 {lc.get('pump') or 0} V / {lc.get('fan') or 0}%" if lc.get("connected") else ""
            self.icon.title = f"Control Center — {name}{extra}"[:127]
        try:
            self.icon.update_menu()
        except Exception:  # noqa: BLE001
            pass

    def mode_name(self, m):
        return {0: self.T("mode0"), 1: self.T("mode1"), 2: self.T("mode2"), 3: self.T("custom")}.get(m, "")

    def act(self, path, body):
        def run():
            try:
                self.api.call(path, body)
            except Exception as e:  # noqa: BLE001
                self.icon.notify(str(e), "Control Center")
            self.refresh()
        threading.Thread(target=run, daemon=True).start()

    # -- window ---------------------------------------------------------------------------------
    def open_window(self, *_):
        try:
            url = f"http://127.0.0.1:{PORT}/#token={self.api._tok()}"
        except OSError:
            self.icon.notify(self.T("svc_down_body"), self.T("svc_down"))
            return
        edge = next((p for p in EDGE if os.path.exists(p)), None)
        if edge:
            prof = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "UWCC", "window")
            subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={prof}", "--window-size=1280,820",
                              "--no-first-run", "--disable-features=Translate"], close_fds=True)
        else:
            os.startfile(url)       # noqa: S606

    # -- autostart (HKLM Run from the installer, per-user on/off like Task Manager) -------------------
    def autostart_enabled(self, *_):
        hk = self._run_entry()
        if hk is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as k:
                v = winreg.QueryValueEx(k, RUN_NAME)[0]
                return not (v and v[0] & 1)          # 02 = enabled, 03 = disabled
        except OSError:
            return True

    @staticmethod
    def _run_entry():
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, RUN_KEY) as k:
                    winreg.QueryValueEx(k, RUN_NAME)
                    return root
            except OSError:
                continue
        return None

    def toggle_autostart(self, *_):
        on = not self.autostart_enabled()
        if self._run_entry() is None:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as k:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_BINARY, bytes([2 if on else 3]) + bytes(11))
        self.icon.update_menu()

    # -- menu ----------------------------------------------------------------------------------
    def menu_items(self):
        st, T, I = self.state, self.T, pystray.MenuItem
        items = [I(T("open"), self.open_window, default=True), pystray.Menu.SEPARATOR]
        if not st:
            items.append(I(self.offline_text(), None, enabled=False))
            if self.offline_since and time.time() - self.offline_since >= 60:
                items.append(I(T("svc_restart"), self.restart_service))
        else:
            p = st["power"]
            if st["platform"].get("fan_control"):
                modes = [0, 1] + ([2] if p.get("turbo_support") else []) + ([3] if p.get("custom_support") else [])
                items.append(I(T("mode"), pystray.Menu(*[
                    I(self.mode_name(m), (lambda m: lambda *_: self.act("mode", {"mode": m}))(m),
                      checked=(lambda m: lambda *_: (self.state or {}).get("power", {}).get("mode") == m)(m), radio=True)
                    for m in modes])))
                items.append(I(T("boost"), lambda *_: self.act("fanboost", {"on": not self.state["power"]["fan_boost"]}),
                               checked=lambda *_: bool((self.state or {}).get("power", {}).get("fan_boost"))))
            kb = st.get("keyboard") or {}
            if kb.get("kind") not in (None, "none"):
                items.append(I(T("kb"), lambda *_: self.act("keyboard/power", {"on": not self.state["keyboard"]["power"]}),
                               checked=lambda *_: bool((self.state or {}).get("keyboard", {}).get("power"))))
            lc = st.get("liquid") or {}
            if lc.get("available") and (lc.get("connected") or (lc.get("config") or {}).get("address")):
                cur = (lc.get("config") or {}).get("mode")
                sub = [I(f"{lc.get('name') or ''} · " + (f"{lc.get('fan')}% / {lc.get('pump')} V" if lc.get("connected")
                                                         else T("not_connected")), None, enabled=False)]
                for m in ("auto", "laptop", "low", "medium", "high", "off"):
                    sub.append(I(T("lc_" + m), (lambda m: lambda *_: self.act("lc/config", {"mode": m}))(m),
                                 checked=(lambda m: lambda *_: cur == m)(m), radio=True))
                sub.append(pystray.Menu.SEPARATOR)
                if lc.get("connected"):
                    sub.append(I(T("lc_disconnect"), lambda *_: self.act("lc/disconnect", {})))
                else:
                    sub.append(I(T("lc_connect"), lambda *_: self.act("lc/connect", {"address": self.state["liquid"]["config"]["address"]})))
                items.append(I(T("lc"), pystray.Menu(*sub)))
            items.append(pystray.Menu.SEPARATOR)
            items.append(I(T("lang"), pystray.Menu(
                I("English", lambda *_: self.act("setting", {"key": "lang", "value": "en"}), checked=lambda *_: self.lang == "en", radio=True),
                I("Русский", lambda *_: self.act("setting", {"key": "lang", "value": "ru"}), checked=lambda *_: self.lang == "ru", radio=True))))
        upd = (st or {}).get("update") or {}
        if upd.get("newer") and upd.get("setup"):
            items.append(I(T("upd_install", upd.get("latest")), lambda *_: self.act("update/download", {})))
        items.append(I(T("upd_check"), self.check_updates))
        items.append(I(T("github"), lambda *_: os.startfile(updates.REPO_URL)))
        items.append(I(T("autostart"), self.toggle_autostart, checked=self.autostart_enabled))
        items.append(I(T("exit"), lambda *_: self.icon.stop()))
        return items

    # -- background loops ---------------------------------------------------------------------
    def events_loop(self):
        while True:
            try:
                self.refresh()
                if not self.state:
                    raise OSError("offline")
                with self.api.events() as r:
                    for raw in r:
                        line = raw.decode(errors="ignore").strip()
                        if not line.startswith("data:"):
                            continue
                        ev = json.loads(line[5:])
                        t = ev.get("type")
                        if t == "monitor":
                            continue
                        self.on_event(ev)
            except Exception:  # noqa: BLE001
                if self.offline_since and time.time() - self.offline_since > 60 and not self.offline_notified:
                    self.offline_notified = True
                    self.icon.notify(self.T("svc_down_body"), self.T("svc_down"))
                time.sleep(3)

    @staticmethod
    def service_state():
        """State of the uwccd service from the SCM (users may query it)."""
        try:
            import win32serviceutil
            return {1: "stopped", 2: "starting", 3: "stopping", 4: "running"}.get(win32serviceutil.QueryServiceStatus("uwccd")[1], "unknown")
        except Exception:  # noqa: BLE001
            return "missing"

    def offline_text(self):
        st = self.service_state()
        return self.T({"stopped": "svc_stopped", "starting": "svc_starting", "missing": "svc_missing"}.get(st, "offline"))

    RESTART_PS = winplat.RESTART_PS

    def restart_service(self, *_):
        """Restart uwccd with administrator rights (UAC prompt): stop, kill if it hangs, start; then wait for it."""
        def run():
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe",
                                                     f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{self.RESTART_PS}"',
                                                     None, 0)
            if rc <= 32:                 # 5: the UAC prompt was declined
                self.icon.notify(" ", self.T("svc_restart_cancel"))
                return
            self.icon.notify(" ", self.T("svc_restarting"))
            for _ in range(45):
                time.sleep(1)
                try:
                    self.api.call("state", timeout=3)
                    self.icon.notify(" ", self.T("svc_restarted"))
                    self.refresh()
                    return
                except Exception:  # noqa: BLE001
                    continue
            self.icon.notify(self.T("svc_restart_fail_body"), self.T("svc_restart_fail"))
        threading.Thread(target=run, daemon=True).start()

    def admin_unlock(self):
        """EC Manager asked for administrator rights: uwccctl ec unlock with a UAC prompt (SYSTEM-only key)."""
        if getattr(self, "_unlocking", False):
            return
        self._unlocking = True
        try:
            exe = os.path.join(os.path.dirname(sys.executable), "uwccctl.exe")
            if not os.path.exists(exe):
                self.icon.notify(exe, self.T("admin_fail"))
                return
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "ec unlock", None, 0)
            if rc <= 32:                 # 5: the UAC prompt was declined
                self._try(lambda: self.api.call("admin/declined", {}, timeout=5))
                self.icon.notify(" ", self.T("admin_declined"))
        finally:
            self._unlocking = False

    def check_updates(self, *_):
        def run():
            try:
                r = self.api.call("update/check", {}, timeout=40)
                if r.get("error"):
                    self.icon.notify(str(r["error"]), self.T("upd_failed"))
                elif not r.get("newer"):
                    self.icon.notify(" ", self.T("upd_latest", r.get("current")))
                # a newer version is announced by the "update" event of the service
            except Exception as e:  # noqa: BLE001
                self.icon.notify(str(e), self.T("upd_failed"))
            self.refresh()
        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def downloads_dir():
        """The user's Downloads folder (FOLDERID_Downloads), also when it was moved to another drive."""
        try:
            import uuid
            from ctypes import wintypes
            guid = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")
            buf = (ctypes.c_byte * 16).from_buffer_copy(guid.bytes_le)
            p = ctypes.c_wchar_p()
            sh = ctypes.windll.shell32
            sh.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
            if sh.SHGetKnownFolderPath(ctypes.byref(buf), 0, None, ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                return path
        except Exception:  # noqa: BLE001
            pass
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def install_update(self, d):
        """update_install: download to Downloads, verify against SHA256SUMS.txt, start it (UAC prompt)."""
        if getattr(self, "_installing", False):
            return
        self._installing = True
        report = lambda **kw: self._try(lambda: self.api.call("update/progress", kw, timeout=5))   # noqa: E731
        path = None
        try:
            report(state="downloading", percent=0)
            path = updates.download_verified(d["setup"], d["sums"], self.downloads_dir(),
                                             lambda pct: report(state="downloading", percent=pct))
            report(state="verified", path=path)
            self.icon.notify(path, self.T("upd_ready", d.get("version", "")))
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, None, os.path.dirname(path), 1)
            if rc <= 32:                       # 5 = the UAC prompt was declined
                report(state="declined", path=path)
                self.icon.notify(path, self.T("upd_manual"))
                subprocess.Popen(f'explorer /select,"{path}"')
            else:
                report(state="started", path=path)
        except Exception as e:  # noqa: BLE001
            report(state="error", error=str(e), path=path)
            self.icon.notify(str(e), self.T("upd_err"))
        finally:
            self._installing = False

    @staticmethod
    def _try(fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return None

    def on_event(self, ev):
        t = ev.get("type")
        if t == "reveal":
            name = os.path.basename(str((ev.get("data") or {}).get("name", "")))
            path = os.path.join(self.downloads_dir(), name)
            self._try(lambda: subprocess.Popen(f'explorer /select,"{path}"' if os.path.exists(path)
                                               else f'explorer "{self.downloads_dir()}"'))
        if t == "update_install":
            threading.Thread(target=self.install_update, args=(ev.get("data") or {},), daemon=True).start()
        if t == "admin_request":
            threading.Thread(target=self.admin_unlock, daemon=True).start()
        osd = bool((self.state or {}).get("settings", {}).get("osd", True))
        for title, body, _critical in agentcore.describe(ev, osd, self.lang):
            if title:
                self.icon.notify(body or " ", title)
        if t == "touchpad":
            winapi.send_keys(winapi.VK_LWIN, winapi.VK_CONTROL, winapi.VK_F24)
        elif t == "launch":
            self.open_window()
        if t in ("status", "mode", "fanboost", "lc", "setting", "keyboard", "ac", "update"):
            self.refresh()

    def idle_loop(self):
        """KeyboardCloseTimer on Windows: GetLastInputInfo in the user session -> POST /api/idle."""
        while True:
            time.sleep(2)
            try:
                timeout = int(((self.state or {}).get("settings") or {}).get("kb_timeout") or 0)
                idle = timeout > 0 and winapi.idle_seconds() >= timeout
                if idle != self.idle_sent:
                    self.api.call("idle", {"idle": idle}, timeout=5)
                    self.idle_sent = idle
            except Exception:  # noqa: BLE001
                self.idle_sent = None

    def fx_loop(self):
        """BetterRGB effects: input from this session (only while the running effect needs it)"""
        from . import fxinput
        fxinput.run(lambda body: self.api.call("keyboard/fx/input", body, timeout=3))

    def open_request_loop(self):
        """Another ControlCenter.exe --open signals this event."""
        kernel32 = _k32()
        h = kernel32.CreateEventW(None, False, False, OPEN_EVENT)
        while h:
            if kernel32.WaitForSingleObject(h, 0xFFFFFFFF) == 0:
                self.open_window()

    def run(self):
        def setup(icon):
            icon.visible = True
            for f in (self.events_loop, self.idle_loop, self.open_request_loop, self.fx_loop):
                threading.Thread(target=f, daemon=True).start()
            if self.show_at_start:
                threading.Timer(1.5, self.open_window).start()
        self.icon.run(setup=setup)


def _k32():
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    for fn in ("CreateMutexW", "CreateEventW", "OpenEventW"):
        getattr(k, fn).restype = wintypes.HANDLE
    k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    k.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k.SetEvent.argtypes = [wintypes.HANDLE]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def setup_logging():
    """The GUI exe has no console (sys.stderr is None): log to %LOCALAPPDATA%\\UWCC\\tray.log."""
    d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "UWCC")
    try:
        os.makedirs(d, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(os.path.join(d, "tray.log"), maxBytes=500_000, backupCount=1,
                                                 encoding="utf-8")
    except OSError:
        h = logging.NullHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])


def main():
    setup_logging()
    args = sys.argv[1:]
    kernel32 = _k32()
    mutex = kernel32.CreateMutexW(None, False, MUTEX)
    already = ctypes.get_last_error() == 183          # ERROR_ALREADY_EXISTS
    if already:
        if "--open" in args or "--show" in args or not args:
            ev = kernel32.OpenEventW(0x0002, False, OPEN_EVENT)     # EVENT_MODIFY_STATE
            if ev:
                kernel32.SetEvent(ev)
        return 0
    Tray(show="--show" in args or "--open" in args).run()
    kernel32.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
