"""MSI Afterburner integration (Windows, experimental): every mode can switch an Afterburner profile slot.

The overclock / undervolt itself stays in MSI Afterburner, where the user saves it into the slots 1-5; this program only
tells it which slot to apply, with its documented command line `MSIAfterburner.exe -Profile<N>` (a running Afterburner
takes the command over; a closed one starts and applies it). Nothing of Afterburner is used or shipped.

Afterburner runs elevated, so the command is started by the service (LocalSystem) in the session of the signed-in user
with that user's full (linked) token: no UAC prompt, and the command reaches the Afterburner window of that session.
When the service does not run as LocalSystem (development, a test), it is started directly.

When:
  * the mode changes (the window, the tray, the rules, the Fn mode key, AC / battery) — the slot of the new mode;
  * the service starts, and Afterburner starts later (its own start-up profile would win otherwise);
  * by hand: the tray, `uwccctl afterburner N`.
Settings: afterburner (on by default); afterburner_profiles {"M": slot, "M.P": slot} — the slot 1-5 of mode M, or of its
preset P (0-based: Office 1 / 2, Gaming 1 / 2, Turbo 1 / 2, Custom 1-5); a preset without its own entry uses the one
of its mode, 0 = "do not change" for that preset; nothing set = the profile is not changed. afterburner_launch (on):
start Afterburner when it is not running, off = skip until it runs. afterburner_default: the slot that holds the
stock settings (saved there after Reset in Afterburner) — the *Default* button, and -1 in afterburner_profiles
("Default") means that slot, whatever it is set to. *Restore default settings* clears afterburner_profiles.
"""
import logging
import os
import subprocess
import sys
import threading
import time

log = logging.getLogger("uwccd.afterburner")

IS_WIN = sys.platform == "win32"
EXE = "MSIAfterburner.exe"
SLOTS = (1, 2, 3, 4, 5)
DEFAULT = -1                # in afterburner_profiles: "the Default slot" (setting afterburner_default)
POLL_S = 2.0
LATE_START_S = 8.0          # Afterburner started after us: let it load its own start-up profile first, then ours
UNINSTALL = (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Afterburner",
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Afterburner")


def find():
    """{"path", "version"} of the installed MSI Afterburner, or None."""
    if not IS_WIN:
        return None
    import winreg
    for key in UNINSTALL:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                vals = {}
                for name in ("InstallLocation", "DisplayIcon", "UninstallString", "DisplayVersion"):
                    try:
                        vals[name] = str(winreg.QueryValueEx(k, name)[0])
                    except OSError:
                        pass
        except OSError:
            continue
        dirs = [vals.get("InstallLocation")] + [os.path.dirname(vals[n].strip('"')) for n in ("DisplayIcon",
                                                                                               "UninstallString")
                                                 if vals.get(n)]
        for d in filter(None, dirs):
            p = os.path.join(d.strip('"'), EXE)
            if os.path.isfile(p):
                return {"path": p, "version": vals.get("DisplayVersion") or _file_version(p)}
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        p = os.path.join(os.environ.get(env, ""), "MSI Afterburner", EXE)
        if os.environ.get(env) and os.path.isfile(p):
            return {"path": p, "version": _file_version(p)}
    return None


def _file_version(path):
    try:
        import win32api
        info = win32api.GetFileVersionInfo(path, "\\")
        ms, ls = info["FileVersionMS"], info["FileVersionLS"]
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:  # noqa: BLE001
        return None


def running():
    """Is MSI Afterburner running (in any session)?"""
    if not IS_WIN:
        return False
    try:
        from .win import winplat
        return bool(winplat.wmi_query(f"SELECT ProcessId FROM Win32_Process WHERE Name = '{EXE}'"))
    except Exception as e:  # noqa: BLE001
        log.debug("process list: %s", e)
        return False


def _is_system():
    try:
        import win32api
        import win32security
        tok = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
        sid = win32security.GetTokenInformation(tok, win32security.TokenUser)[0]
        return win32security.ConvertSidToStringSid(sid) == "S-1-5-18"
    except Exception:  # noqa: BLE001
        return False


def run_in_user_session(cmd):
    """Starts cmd (list) in the active user's session with the user's full token; returns the process id.
    LookupError when nobody is signed in (the service tries again later)."""
    import win32con
    import win32process
    import win32profile
    import win32security
    import win32ts
    session = win32ts.WTSGetActiveConsoleSessionId()
    if session == 0xFFFFFFFF:
        raise LookupError("no user is signed in")
    try:
        token = win32ts.WTSQueryUserToken(session)
    except Exception as e:  # noqa: BLE001  (error 1008: nobody signed in to that session yet)
        raise LookupError(f"no user token for session {session}: {e}") from e
    try:                         # an administrator with UAC on: the elevated twin of the token (no prompt)
        linked = win32security.GetTokenInformation(token, win32security.TokenLinkedToken)
        if linked:
            token = linked
    except Exception:  # noqa: BLE001  (UAC off or not an administrator: the token is already the full one)
        pass
    env = win32profile.CreateEnvironmentBlock(token, False)
    si = win32process.STARTUPINFO()
    si.lpDesktop = "winsta0\\default"
    si.dwFlags = win32con.STARTF_USESHOWWINDOW
    si.wShowWindow = win32con.SW_SHOWMINNOACTIVE
    line = subprocess.list2cmdline(cmd)
    _h, _t, pid, _tid = win32process.CreateProcessAsUser(
        token, None, line, None, None, False,
        win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_UNICODE_ENVIRONMENT, env,
        os.path.dirname(cmd[0]), si)
    return pid


def default_runner(cmd):
    if IS_WIN and _is_system():
        return run_in_user_session(cmd)
    return subprocess.Popen(cmd, close_fds=True).pid


class Afterburner:
    """Follows the mode and applies its Afterburner slot."""

    def __init__(self, store, mode_fn, emit=lambda *a: None, runner=None, finder=find, is_running=running,
                 available=IS_WIN):
        self.available = available
        self.store = store
        self.mode_fn = mode_fn              # () -> (mode number, preset index or None) now, or None
        self.emit = emit
        self.runner = runner or default_runner
        self.finder = finder
        self.is_running = is_running
        self.install = None
        self.last = {}                      # {"slot", "mode", "time", "error"}
        self.seen_mode = None
        self.was_running = None
        self.pending = None                 # a slot still to apply (nobody signed in yet, Afterburner closed)
        self.lock = threading.Lock()
        self.stop_ev = threading.Event()

    # settings
    def enabled(self):
        return self.store.get("afterburner", True) is not False

    def launch(self):
        return self.store.get("afterburner_launch", True) is not False

    @staticmethod
    def key(mode, preset=None):
        return str(int(mode)) if preset is None else f"{int(mode)}.{int(preset)}"

    def profiles(self):
        """{"M" | "M.P": slot}: checked entries only; 0 (a preset's "do not change") only for presets."""
        raw = self.store.get("afterburner_profiles") or {}
        out = {}
        for k, v in raw.items():
            try:
                parts = [int(x) for x in str(k).split(".")]
                v = int(v)
            except (TypeError, ValueError):
                continue
            if not 0 <= parts[0] <= 3 or len(parts) > 2 or (len(parts) == 2 and not 0 <= parts[1] <= 4):
                continue
            if v in SLOTS or v == DEFAULT or (v == 0 and len(parts) == 2):
                out[self.key(*parts)] = v
        return out

    def default_slot(self):
        try:
            v = int(self.store.get("afterburner_default") or 0)
        except (TypeError, ValueError):
            return None
        return v if v in SLOTS else None

    def set_default(self, slot):
        if slot in (None, "", "none", 0):
            self.store.set("afterburner_default", None)
            return
        slot = int(slot)
        if slot not in SLOTS:
            raise ValueError(f"profile {slot} (1-5)")
        self.store.set("afterburner_default", slot)

    def reset(self):
        """*Restore default settings*: no mode or preset changes the Afterburner profile any more."""
        self.store.set("afterburner_profiles", {})

    def slot_for(self, mode, preset=None):
        """The Afterburner slot of this mode / preset, or None (do not change)."""
        p = self.profiles()
        v = p[self.key(mode, preset)] if preset is not None and self.key(mode, preset) in p else p.get(self.key(mode))
        if v == DEFAULT:
            return self.default_slot()
        return v or None

    def set_profile(self, mode, slot, preset=None):
        """slot 1-5 or None ("do not change"); preset None = the whole mode."""
        mode = int(mode)
        if not 0 <= mode <= 3:
            raise ValueError(f"mode {mode}")
        if preset is not None and not 0 <= int(preset) <= 4:
            raise ValueError(f"preset {preset}")
        p = dict(self.profiles())
        k = self.key(mode, preset)
        if slot in ("default", DEFAULT):
            p[k] = DEFAULT                # follows afterburner_default
        elif slot in (None, "", "keep", 0):
            if preset is None:
                p.pop(k, None)
            else:
                p[k] = 0                  # explicit: this preset does not change it, even when its mode does
        else:
            slot = int(slot)
            if slot not in SLOTS:
                raise ValueError(f"profile {slot} (1-5)")
            p[k] = slot
        self.store.set("afterburner_profiles", p)
        cur = self.seen_mode
        if cur is not None and cur[0] == mode and (preset is None or cur[1] == int(preset)):
            new = self.slot_for(*cur)
            if new:                                    # the slot of what runs now changed: apply it now
                self.request(new, mode, "setting")

    # applying
    def apply(self, slot, why="manual", mode=None):
        """Sends -Profile<slot> now. Returns the result dict (also kept in self.last)."""
        slot = int(slot)
        if slot not in SLOTS:
            raise ValueError(f"profile {slot} (1-5)")
        inst = self.install or self.finder()
        self.install = inst
        res = {"slot": slot, "mode": mode, "why": why, "time": time.time(), "error": None}
        if not inst:
            res["error"] = "MSI Afterburner is not installed"
        elif not self.is_running() and not self.launch():
            res["error"] = "not running (starting it is off)"
        else:
            try:
                self.runner([inst["path"], f"-Profile{slot}"])
                log.info("Afterburner profile %s (%s)", slot, why)
            except LookupError:
                raise
            except Exception as e:  # noqa: BLE001
                res["error"] = str(e)
                log.warning("Afterburner profile %s: %s", slot, e)
        with self.lock:
            self.last = res
        self.emit("afterburner", {"slot": slot, "error": res["error"]})
        return res

    def request(self, slot, mode, why):
        try:
            res = self.apply(slot, why, mode)
            self.pending = slot if res["error"] and res["error"].startswith("not running") else None
        except LookupError as e:                       # nobody signed in yet: again at the next check
            log.debug("Afterburner: %s", e)
            self.pending = slot

    def check(self):
        """One step of the watcher: a new mode, Afterburner started late, or a slot still to apply."""
        if not self.enabled():
            self.seen_mode = None
            return
        try:
            cur = self.mode_fn()
        except Exception:  # noqa: BLE001
            cur = None
        run = self.is_running()
        started = self.was_running is False and run
        self.was_running = run
        if cur is None or cur[0] is None:
            return
        cur = (int(cur[0]), None if cur[1] is None else int(cur[1]))
        mode = cur[0]
        slot = self.slot_for(*cur)
        if cur != self.seen_mode:
            self.seen_mode = cur
            if slot:
                self.request(slot, mode, "start" if self.last == {} else "mode")
            else:
                self.pending = None
            return
        if slot and started:                           # Afterburner started after us: its start-up profile first
            time.sleep(LATE_START_S)
            self.request(slot, mode, "afterburner started")
        elif slot and self.pending:
            self.request(slot, mode, "retry")

    def start(self):
        if not self.available:
            return
        self.install = self.finder()
        threading.Thread(target=self._loop, daemon=True, name="afterburner").start()

    def _loop(self):
        while not self.stop_ev.wait(POLL_S):
            try:
                if self.install is None and int(time.time()) % 60 < POLL_S:    # installed while we run
                    self.install = self.finder()
                if self.install:
                    self.check()
            except Exception as e:  # noqa: BLE001
                log.warning("Afterburner: %s", e)

    def stop(self):
        self.stop_ev.set()

    def status(self):
        inst = self.install
        with self.lock:
            last = dict(self.last)
        return {"available": self.available, "found": bool(inst), "path": (inst or {}).get("path"),
                "version": (inst or {}).get("version"), "running": bool(inst) and bool(self.was_running),
                "enabled": self.enabled(), "launch": self.launch(),
                "profiles": self.profiles(), "default": self.default_slot(),
                "now": list(self.seen_mode) if self.seen_mode else None,
                "last": last or None,
                "experimental": True}
