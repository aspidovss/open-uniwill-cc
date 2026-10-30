"""The system power profile: the Windows power mode slider (and battery saver) or power-profiles-daemon on Linux.

Read every few seconds. Used by Automation: "Follow the system power profile" switches the laptop's mode when the
profile changes (changes the program made itself are ignored), and the rules can test it.
"""
import logging
import shutil
import subprocess
import sys
import threading
import time

log = logging.getLogger("uwccd.sysprofile")

PROFILES = ("power-saver", "balanced", "performance")
OWN_S = 15          # a profile the program set itself within this time is not followed back


class SystemProfile(threading.Thread):
    POLL = 3.0

    def __init__(self, svc):
        super().__init__(daemon=True, name="sysprofile")
        self.svc = svc
        self.stop = threading.Event()
        self.profile = None          # power-saver | balanced | performance | None (unknown)
        self.saver = None            # Windows battery saver on / off; None on Linux
        self.available = None
        self._own = (None, 0.0)

    def note_set(self, prof):
        """The program set this profile itself (Follow the mode with the system power profile)."""
        self._own = (prof, time.time())

    @staticmethod
    def read():
        if sys.platform == "win32":
            from .win.winapi import battery_saver, get_power_overlay
            return get_power_overlay(), battery_saver()
        if not shutil.which("powerprofilesctl"):
            return None, None
        r = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=5, check=False)
        p = r.stdout.strip()
        return (p if p in PROFILES else None), None

    def needed(self):
        """On Linux powerprofilesctl runs only when something uses the profile (Windows: a cheap call)."""
        if sys.platform == "win32":
            return True
        st = self.svc.settings_store
        if st.get("ppd_follow"):
            return True
        return any(c.get("metric") in ("sys_profile", "saver") for r in (st.get("load_rules") or [])
                   for c in r.get("conditions") or [])

    def poll(self):
        try:
            p, sv = self.read()
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.debug("system power profile: %s", e)
            p, sv = None, None
        self.available = p is not None
        old, self.profile, self.saver = self.profile, p, sv
        if p and old and p != old:
            own, at = self._own
            if own == p and time.time() - at < OWN_S:
                return
            log.info("system power profile: %s -> %s", old, p)
            rules = getattr(self.svc, "rules", None)
            if rules is not None:
                rules.follow_system(p)

    def run(self):
        while not self.stop.is_set():
            if self.needed():
                self.poll()
            self.stop.wait(self.POLL)

    def status(self):
        return {"available": self.available, "profile": self.profile, "saver": self.saver,
                "os": "windows" if sys.platform == "win32" else "linux"}
