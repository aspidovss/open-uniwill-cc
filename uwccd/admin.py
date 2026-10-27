"""Administrator unlock for the risky settings of EC Manager.

Every local user can read the ordinary API token (the tray and the window need it). Changing how the program reaches
the EC (OEM driver / WMI), accepting the WMI warning, ec_wmi.json, platform profiles and the self-check with writes
need a second key that only administrators can read:

    Windows: %ProgramData%\\UWCC\\run\\admin-token   (SYSTEM + Administrators only)
    Linux:   /run/uwcc/admin-token                  (root only, 0600)

A request carrying it (header X-UWCC-Admin) is allowed, and POST /api/admin/unlock with it opens these settings for
the window for UNLOCK_S seconds. The window asks the tray for it: the tray starts "uwccctl ec unlock" with a UAC
prompt; on Linux: sudo uwccctl ec unlock.
"""
import logging
import os
import secrets
import sys
import threading
import time

log = logging.getLogger("uwccd.admin")
UNLOCK_S = 600


def acl_admins_only(path):
    if sys.platform == "win32":
        import subprocess
        from .win.winplat import CREATE_NO_WINDOW
        subprocess.run(["icacls", path, "/inheritance:r", "/grant:r", "*S-1-5-18:F", "*S-1-5-32-544:F"],
                       capture_output=True, creationflags=CREATE_NO_WINDOW, check=False)
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


class Admin:
    def __init__(self, run_dir, emit=None):
        self.run_dir = run_dir
        self.emit = emit or (lambda *_: None)
        self.token = secrets.token_urlsafe(24)
        self.until = 0.0
        self.lock = threading.Lock()
        self.path = os.path.join(run_dir, "admin-token")
        try:
            os.makedirs(run_dir, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(self.token)
            acl_admins_only(self.path)
        except OSError as e:
            log.warning("admin token file: %s", e)

    def valid(self, tok):
        return bool(tok) and secrets.compare_digest(str(tok), self.token)

    def allowed(self, tok=None):
        return self.valid(tok) or time.time() < self.until

    def unlock(self, seconds=UNLOCK_S):
        with self.lock:
            self.until = time.time() + max(30, min(3600, int(seconds)))
        log.warning("EC Manager unlocked for %d s", int(self.until - time.time()))
        self.emit("admin", self.status())
        return self.status()

    def lock_now(self):
        with self.lock:
            self.until = 0.0
        self.emit("admin", self.status())
        return self.status()

    def status(self):
        left = max(0, int(self.until - time.time()))
        return {"unlocked": left > 0, "remaining": left, "until": self.until if left else None}
