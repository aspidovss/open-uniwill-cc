"""Background workers: WMI hot-key events, EC polling fallback, input idle timer, app binding."""
import glob
import logging
import os
import select
import struct
import sys
import threading
import time

from . import regs as R

log = logging.getLogger("uwccd.events")


class HotkeyEvents(threading.Thread):
    """Reads AcpiTest_EventULong codes from /dev/uwcc (kernel module) and dispatches them."""

    def __init__(self, handler, dev="/dev/uwcc"):
        super().__init__(daemon=True, name="hotkeys")
        self.handler = handler
        self.dev = dev
        self.stop = threading.Event()
        self.available = os.path.exists(dev)

    def run(self):
        if not self.available:
            return
        try:
            fd = os.open(self.dev, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        except OSError as e:
            log.warning("events: %s", e)
            self.available = False
            return
        p = select.poll()
        p.register(fd, select.POLLIN)
        while not self.stop.is_set():
            if not p.poll(1000):
                continue
            try:
                data = os.read(fd, 64)
            except BlockingIOError:
                continue
            except OSError as e:
                log.warning("events read: %s", e)
                time.sleep(1)
                continue
            for i in range(0, len(data) - 3, 4):
                code = struct.unpack_from("<I", data, i)[0]
                log.info("WMI event 0x%02X", code)
                try:
                    self.handler(code)
                except Exception:  # noqa: BLE001
                    log.exception("event 0x%02X", code)


class ECPoller(threading.Thread):
    """Fallback when no event source exists: watch EC bits that the firmware toggles itself,
    plus AC adapter and suspend/resume (CLOCK_BOOTTIME vs CLOCK_MONOTONIC)."""

    def __init__(self, ec, monitor, on_change, use_ec_bits):
        super().__init__(daemon=True, name="poller")
        self.ec = ec
        self.monitor = monitor
        self.on_change = on_change
        self.use_ec_bits = use_ec_bits
        self.stop = threading.Event()

    @staticmethod
    def _clocks():
        """(time without suspend, time with suspend) in seconds."""
        if sys.platform == "win32":
            from .win.winapi import interrupt_times
            wall, unbiased = interrupt_times()
            return unbiased / 1000.0, wall / 1000.0
        return time.monotonic(), time.clock_gettime(time.CLOCK_BOOTTIME)

    def run(self):
        last = {}
        mono, boot = self._clocks()
        while not self.stop.wait(2.0):
            m2, b2 = self._clocks()
            if (b2 - boot) - (m2 - mono) > 5:
                self.on_change("resume", None)
            mono, boot = m2, b2
            cur = {"ac": self.monitor.ac_online()}
            if self.use_ec_bits:
                try:
                    cur["boost"] = bool(self.ec.read(R.FAN_MODE) & 0x40)
                    cur["winkey"] = bool(self.ec.read(R.STATUS_768) & 0x01)
                    cur["fnlock"] = bool(self.ec.read(R.FN_LOCK) & 0x10)
                except Exception:  # noqa: BLE001
                    pass
            for k, v in cur.items():
                if k in last and last[k] != v:
                    try:
                        self.on_change(k, v)
                    except Exception:  # noqa: BLE001
                        log.exception("poll %s", k)
            last = cur


class IdleTimer(threading.Thread):
    """KeyboardCloseTimer: notifies idle(True) after N seconds without input, idle(False) on input."""

    def __init__(self, get_timeout, callback):
        super().__init__(daemon=True, name="idle")
        self.get_timeout = get_timeout
        self.callback = callback
        self.stop = threading.Event()
        self.fds = {}

    def _rescan(self):
        wanted = set()
        for ev in glob.glob("/dev/input/event*"):
            name = os.path.basename(ev)
            caps = "/sys/class/input/%s/device/capabilities/ev" % name
            try:
                ev_bits = int(open(caps).read().strip(), 16)
            except (OSError, ValueError):
                continue
            if ev_bits & (1 << 1) or ev_bits & (1 << 2) or ev_bits & (1 << 3):   # EV_KEY / EV_REL / EV_ABS
                wanted.add(ev)
        for ev in list(self.fds):
            if ev not in wanted:
                os.close(self.fds.pop(ev))
        for ev in wanted - set(self.fds):
            try:
                self.fds[ev] = os.open(ev, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            except OSError:
                pass

    def run(self):
        last_input = time.monotonic()
        idle = False
        rescan = 0
        while not self.stop.is_set():
            timeout = self.get_timeout() or 0
            if timeout <= 0:
                if idle:
                    idle = False
                    self.callback(False)
                for fd in self.fds.values():
                    os.close(fd)
                self.fds = {}
                self.stop.wait(3)
                continue
            if time.monotonic() > rescan:
                self._rescan()
                rescan = time.monotonic() + 30
            fds = list(self.fds.values())
            try:
                r, _, _ = select.select(fds, [], [], 1.0) if fds else ([], [], [])
            except OSError:
                self._rescan()
                continue
            if not fds:
                time.sleep(1)
            if r:
                for fd in r:
                    try:
                        while os.read(fd, 24 * 64):
                            pass
                    except (BlockingIOError, OSError):
                        pass
                last_input = time.monotonic()
                if idle:
                    idle = False
                    self.callback(False)
            elif not idle and time.monotonic() - last_input >= timeout:
                idle = True
                self.callback(True)


class AppBinding(threading.Thread):
    """GaingProfileBinding: switch operating mode while a bound program is running."""

    def __init__(self, get_rules, set_mode, get_mode):
        super().__init__(daemon=True, name="appbind")
        self.get_rules = get_rules
        self.set_mode = set_mode
        self.get_mode = get_mode
        self.stop = threading.Event()
        self.active = None
        self.prev_mode = None

    @staticmethod
    def running():
        if sys.platform == "win32":
            from .win.winplat import process_names
            return process_names()
        names = set()
        for p in glob.glob("/proc/[0-9]*/comm"):
            try:
                names.add(open(p).read().strip().lower())
            except OSError:
                pass
        for p in glob.glob("/proc/[0-9]*/cmdline"):
            try:
                exe = open(p, "rb").read().split(b"\0")[0].decode(errors="ignore")
                if exe:
                    names.add(os.path.basename(exe).lower())
            except OSError:
                pass
        return names

    def run(self):
        while not self.stop.wait(3):
            rules = [r for r in (self.get_rules() or []) if r.get("enabled", True) and r.get("process")]
            if not rules and self.active is None:
                continue
            procs = self.running()
            hit = next((r for r in rules if r["process"].lower() in procs), None)
            try:
                if hit and (self.active is None or self.active["process"] != hit["process"]):
                    if self.active is None:
                        self.prev_mode = self.get_mode()
                    self.active = hit
                    log.info("app binding: %s -> mode %s", hit["process"], hit["mode"])
                    self.set_mode(int(hit["mode"]))
                elif not hit and self.active is not None:
                    log.info("app binding: %s exited, back to mode %s", self.active["process"], self.prev_mode)
                    self.active = None
                    if self.prev_mode is not None:
                        self.set_mode(self.prev_mode)
            except Exception:  # noqa: BLE001
                log.exception("app binding")
