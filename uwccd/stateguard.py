"""1.9.2.1: /api/state never hangs, and a hang leaves a trace.

On 2026-11-20 a Windows laptop under memory pressure (nvidia-smi failing, PowerShell timing out) had one part of the
state block for good: the window and the tray waited for /api/state and showed "no connection" while the rest of the
service still worked; only a restart helped, and the log could not tell where it hung.

* ``PartGuard`` builds each part of the state in a worker thread with a time limit. A part that does not answer in
  ``PART_TIMEOUT_S`` is sent with its last value (its name in ``state["stale"]``); while it is still stuck the next
  requests do not wait for it again.
* ``Watchdog`` (a thread) looks at the stuck parts and the /api/state requests in flight: after ``DUMP_AFTER_S`` it
  writes the stacks of all threads to the log (once per hang), after ``RESTART_AFTER_S`` it restarts the service —
  what the user had to do by hand.
"""
import concurrent.futures as cf
import logging
import sys
import threading
import time
import traceback

log = logging.getLogger("uwccd.watchdog")

PART_TIMEOUT_S = 5.0
DUMP_AFTER_S = 30.0
RESTART_AFTER_S = 180.0


def thread_stacks():
    """The stacks of all threads of the process, as text for the log."""
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    for ident, frame in sys._current_frames().items():      # noqa: SLF001 — the documented way to get them
        out.append(f"--- thread {names.get(ident, '?')} ({ident})")
        out.extend(ln.rstrip("\n") for ln in traceback.format_stack(frame))
    return "\n".join(out)


class PartGuard:
    def __init__(self, timeout=PART_TIMEOUT_S, workers=32):
        self.timeout = timeout
        self.pool = cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="state-part")
        self.lock = threading.Lock()
        self.stuck = {}             # part name -> (future, since)
        self.last = {}              # part name -> last value
        self.inflight = {}          # request id -> since (the whole /api/state, also outside the parts)

    def call(self, name, fn):
        """fn() with a time limit; (value, stale). An exception of fn goes to the caller as before."""
        with self.lock:
            st = self.stuck.get(name)
            if st is not None:
                if not st[0].done():
                    return self.last.get(name), True
                del self.stuck[name]
                log.info("state part %s answers again after %.0f s", name, time.time() - st[1])
        fut = self.pool.submit(fn)
        try:
            v = fut.result(self.timeout)
        except cf.TimeoutError:
            with self.lock:
                self.stuck[name] = (fut, time.time())
            log.warning("state part %s does not answer in %.1f s — sent with its last value", name, self.timeout)
            return self.last.get(name), True
        with self.lock:
            self.last[name] = v
        return v, False

    def build(self, parts):
        """{name: fn} -> (dict of values, [names sent with the last value])."""
        out, stale = {}, []
        for name, fn in parts.items():
            out[name], old = self.call(name, fn)
            if old:
                stale.append(name)
        return out, stale

    # -- the whole request ------------------------------------------------------------------------------------------
    def enter(self):
        key = object()
        with self.lock:
            self.inflight[id(key)] = time.time()
        return key

    def leave(self, key):
        with self.lock:
            self.inflight.pop(id(key), None)

    def oldest(self):
        """(seconds, what) of the longest hang now, or (0, None)."""
        now = time.time()
        with self.lock:
            cands = [(now - since, f"state part {n}") for n, (f, since) in self.stuck.items() if not f.done()]
            cands += [(now - since, "/api/state request") for since in self.inflight.values()]
        return max(cands, default=(0.0, None))


class Watchdog(threading.Thread):
    def __init__(self, guard, restart, period=5.0, dump_after=DUMP_AFTER_S, restart_after=RESTART_AFTER_S):
        super().__init__(daemon=True, name="watchdog")
        self.guard, self.restart, self.period = guard, restart, period
        self.dump_after, self.restart_after = dump_after, restart_after
        self.stop = threading.Event()
        self.dumped = self.restarted = False

    def check(self):
        age, what = self.guard.oldest()
        if age < self.dump_after:
            self.dumped = False                 # the hang is over (or none): the next one is dumped again
            return None
        if not self.dumped:
            self.dumped = True
            log.error("%s has not answered for %.0f s — stacks of all threads:\n%s", what, age, thread_stacks())
            return "dump"
        if age >= self.restart_after and not self.restarted and self.restart is not None:
            self.restarted = True
            log.error("%s has not answered for %.0f s — restarting the service", what, age)
            self.restart(f"hung: {what}")
            return "restart"
        return None

    def run(self):
        while not self.stop.wait(self.period):
            try:
                self.check()
            except Exception:  # noqa: BLE001
                log.exception("watchdog")
