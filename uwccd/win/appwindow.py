"""The Control Center window on Windows: Microsoft Edge in app mode, owned by the tray (1.7.7.0, reworked in 1.7.7.1).

* One window: "Open" brings the running window to the front instead of starting a second one.
* Closing the window (✕) ends all its Edge processes (no background mode), so it uses no memory while only the tray
  runs; "Open" starts it again in about a second.
* The Edge processes run in a job object of the tray. The job is used to find the window's processes and to end them
  with "Close the window" and when the tray exits — never just because the first Edge process has exited: Edge may
  hand its work to another process of its own (1.7.7.0 ended the window right after it opened in that case).
* Anything unexpected here falls back to the plain start of 1.7.6 (Edge without a job), so the window always opens.
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
              "--disable-extensions", "--disable-sync", "--disable-features=Translate"]

SW_RESTORE = 9
WM_CLOSE = 0x0010
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x0800
JobObjectBasicAccountingInformation = 1
JobObjectBasicProcessIdList = 3
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


class _ACCT(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]


class _PIDS(ctypes.Structure):
    _fields_ = [("NumberOfAssignedProcesses", wintypes.DWORD), ("NumberOfProcessIdsInList", wintypes.DWORD),
                ("ProcessIdList", ctypes.c_size_t * 64)]


def edge_path():
    return next((p for p in EDGE if os.path.exists(p)), None)


def profile_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "UWCC", "window")


def plain_start(url):
    """1.7.6 behaviour: Edge in app mode, nothing tracked. False without Edge."""
    edge = edge_path()
    if not edge:
        return False
    subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={profile_dir()}"] + EDGE_FLAGS, close_fds=True)
    return True


class AppWindow:
    def __init__(self, on_change=lambda: None):
        self.on_change = on_change              # called when the window opens or closes (tray menu update)
        self.job = None
        self.pid = None
        self.lock = threading.Lock()
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        H, P = wintypes.HANDLE, ctypes.c_void_p
        k, u = self.k32, self.u32
        k.CreateJobObjectW.restype = H
        k.CreateJobObjectW.argtypes = [P, wintypes.LPCWSTR]
        k.SetInformationJobObject.argtypes = [H, ctypes.c_int, P, wintypes.DWORD]
        k.QueryInformationJobObject.argtypes = [H, ctypes.c_int, P, wintypes.DWORD, P]
        k.AssignProcessToJobObject.argtypes = [H, H]
        k.TerminateJobObject.argtypes = [H, wintypes.UINT]
        k.CloseHandle.argtypes = [H]
        u.EnumWindows.argtypes = [P, wintypes.LPARAM]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    # state
    def _active(self):
        """Number of running processes of the window (0 when closed)."""
        job = self.job
        if not job:
            return 0
        a = _ACCT()
        if not self.k32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation, ctypes.byref(a),
                                                  ctypes.sizeof(a), None):
            return 0
        return a.ActiveProcesses

    def alive(self):
        try:
            return self._active() > 0
        except Exception:  # noqa: BLE001
            return False

    def _pids(self):
        job = self.job
        if not job:
            return set()
        lst = _PIDS()
        self.k32.QueryInformationJobObject(job, JobObjectBasicProcessIdList, ctypes.byref(lst), ctypes.sizeof(lst), None)
        return {int(lst.ProcessIdList[i]) for i in range(min(lst.NumberOfProcessIdsInList, 64))}

    def _hwnds(self):
        """Visible titled top-level windows of the window's processes."""
        pids = self._pids()
        if not pids:
            return []
        found = []
        proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(h, _):
            p = wintypes.DWORD()
            self.u32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value in pids and self.u32.IsWindowVisible(h) and self.u32.GetWindowTextLengthW(h):
                found.append(h)
            return True
        fn = proto(cb)
        self.u32.EnumWindows(ctypes.cast(fn, ctypes.c_void_p), 0)
        return found

    # actions
    def open(self, url):
        """Brings the window to the front, or starts it. Returns False when Edge is missing (caller opens the URL)."""
        try:
            with self.lock:
                if self.alive():
                    hw = self._hwnds()
                    if hw:
                        self.u32.ShowWindow(hw[0], SW_RESTORE)
                        self.u32.SetForegroundWindow(hw[0])
                        return True
                    log.info("window: running but no window found, starting it again")
                edge = edge_path()
                if not edge:
                    return False
                self._drop_job()
                proc = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={profile_dir()}"] + EDGE_FLAGS,
                                        close_fds=True)
                self.pid = proc.pid
                self.job = self._job(proc)
                log.info("window: Edge %s started%s", proc.pid, "" if self.job else " (no job)")
            threading.Thread(target=self._watch, daemon=True, name="window").start()
        except Exception:  # noqa: BLE001
            log.exception("window: tracked start failed, plain start")
            return plain_start(url)
        self.on_change()
        return True

    def close(self):
        """Closes the window like ✕ (WM_CLOSE), then ends whatever of it is left after 5 s."""
        try:
            for h in self._hwnds():
                self.u32.PostMessageW(h, WM_CLOSE, 0, 0)
            for _ in range(25):
                if not self.alive():
                    break
                time.sleep(0.2)
            if self.alive() and self.job:
                log.info("window: ending %s process(es) left", self._active())
                self.k32.TerminateJobObject(self.job, 0)
        except Exception:  # noqa: BLE001
            log.exception("window: close")
        self.on_change()

    # internals
    def _job(self, proc):
        """A job that ends the window's processes with the tray (KILL_ON_JOB_CLOSE). None if not possible."""
        job = self.k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _EXT()
        info.Basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
        self.k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))
        if not self.k32.AssignProcessToJobObject(job, int(proc._handle)):
            log.info("window: job not assigned (error %s)", ctypes.get_last_error())
            self.k32.CloseHandle(job)
            return None
        return job

    def _drop_job(self):
        """Forgets the job of a window that has ended (its handle is closed; nothing is running in it)."""
        if self.job and not self._active():
            self.k32.CloseHandle(self.job)
            self.job = None

    def _watch(self):
        """Tells the tray when the window has closed (all its processes ended)."""
        time.sleep(2)
        while self.alive():
            time.sleep(2)
        log.info("window: closed")
        self.on_change()
