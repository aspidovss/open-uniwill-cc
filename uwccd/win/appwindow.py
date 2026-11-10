"""The Control Center window on Windows: Microsoft Edge in app mode, owned by the tray (1.7.7.0).

* One window: "Open" brings the running window to the front instead of starting a second one.
* Closing the window (✕) ends all its Edge processes (no background mode), so it uses no memory while only the tray
  runs; "Open" starts it again in about a second.
* The Edge processes run in a job object of the tray: "Close window" in the tray and the end of the tray close them too.
"""
import ctypes
import logging
import os
import subprocess
import threading
import time
from ctypes import wintypes

log = logging.getLogger("uwcc.window")

EDGE = [os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")]

# Only what the window needs: no background mode (nothing left after ✕), no extensions, sync or first-run pages.
EDGE_FLAGS = ["--window-size=1280,820", "--no-first-run", "--no-default-browser-check", "--disable-background-mode",
              "--disable-extensions", "--disable-sync", "--disable-features=Translate", "--renderer-process-limit=1"]

SW_RESTORE = 9
WM_CLOSE = 0x0010
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


class _IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]


class _BASIC(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class _EXT(ctypes.Structure):
    _fields_ = [("Basic", _BASIC), ("Io", _IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


def edge_path():
    return next((p for p in EDGE if os.path.exists(p)), None)


def profile_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "UWCC", "window")


class AppWindow:
    def __init__(self, on_change=lambda: None):
        self.on_change = on_change              # called when the window opens or closes (tray menu update)
        self.proc = None
        self.job = None
        self.lock = threading.Lock()
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        H = wintypes.HANDLE
        self.k32.CreateJobObjectW.restype = H
        self.k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.k32.SetInformationJobObject.argtypes = [H, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.k32.AssignProcessToJobObject.argtypes = [H, H]
        self.k32.TerminateJobObject.argtypes = [H, wintypes.UINT]
        self.k32.CloseHandle.argtypes = [H]
        self.u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    # state
    def alive(self):
        p = self.proc
        return bool(p) and p.poll() is None

    def _hwnds(self):
        """Visible top-level windows of the Edge browser process of this window."""
        if not self.alive():
            return []
        pid, found = self.proc.pid, []
        proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(h, _):
            p = wintypes.DWORD()
            self.u32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid and self.u32.IsWindowVisible(h) and self.u32.GetWindowTextLengthW(h):
                found.append(h)
            return True
        self.u32.EnumWindows(proto(cb), 0)
        return found

    # actions
    def open(self, url):
        """Brings the window to the front, or starts it. Returns False when Edge is missing (caller opens the URL)."""
        with self.lock:
            hw = self._hwnds()
            if hw:
                self.u32.ShowWindow(hw[0], SW_RESTORE)
                self.u32.SetForegroundWindow(hw[0])
                return True
            edge = edge_path()
            if not edge:
                return False
            self.proc = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={profile_dir()}"] + EDGE_FLAGS,
                                         close_fds=True)
            job = self._job(self.proc)
            threading.Thread(target=self._watch, args=(self.proc, job), daemon=True, name="window").start()
        self.on_change()
        return True

    def close(self):
        """Closes the window like ✕ (WM_CLOSE), then ends whatever of it is left."""
        with self.lock:
            for h in self._hwnds():
                self.u32.PostMessageW(h, WM_CLOSE, 0, 0)
            p, job = self.proc, self.job
        if p:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                pass
        if job and self.job == job:              # still open (the watcher ends and closes it otherwise)
            self.k32.TerminateJobObject(job, 0)      # renderer / GPU processes that did not exit with the window
        self.on_change()

    # internals
    def _job(self, proc):
        """Edge and its child processes in a job that ends with the tray (KILL_ON_JOB_CLOSE)."""
        try:
            job = self.k32.CreateJobObjectW(None, None)
            info = _EXT()
            info.Basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            self.k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))
            if not self.k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
                log.info("window: job not assigned (%s)", ctypes.get_last_error())
            self.job = job
            return job
        except Exception as e:  # noqa: BLE001
            log.info("window: job object: %s", e)
            return None

    def _watch(self, proc, job):
        t0 = time.time()
        proc.wait()
        if time.time() - t0 < 3:
            # Edge passed the URL to an Edge already running with this profile (e.g. left from an older version)
            log.info("window: Edge handed the window over to a running instance")
        if job:
            self.k32.TerminateJobObject(job, 0)     # what is left of this window
            self.k32.CloseHandle(job)
            if self.job == job:
                self.job = None
        self.on_change()
