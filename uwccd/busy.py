"""Long operations the window must wait for (WMI path: switching a mode takes seconds, a fan curve ~15 s).

    with svc.busy.task("apply", label="turbo", blocking=True):
        ...
        svc.busy.progress("apply", 40)

blocking=True  — the window covers itself with "Applying…" and the API refuses other mode / profile changes;
blocking=False — work in the background (the fan curve after a mode change): the window keeps working, only the
                 mode cards and the fan page wait.
Every change is sent to the window as the event "busy" (list of running operations).
"""
import contextlib
import threading
import time


class Busy:
    def __init__(self, emit=None):
        self.emit = emit or (lambda *_: None)
        self.lock = threading.RLock()
        self.ops = {}                 # op -> {"op", "label", "blocking", "started", "progress", "eta", "depth"}
        self._last_emit = {}

    def _send(self, force=False):
        self.emit("busy", {"ops": self.state()})

    @contextlib.contextmanager
    def task(self, op, label=None, blocking=True, eta=None):
        with self.lock:
            cur = self.ops.get(op)
            if cur:
                cur["depth"] += 1
                if label:
                    cur["label"] = label
            else:
                self.ops[op] = {"op": op, "label": label, "blocking": bool(blocking), "started": time.time(),
                                "progress": None, "eta": eta, "depth": 1}
                self._send()
        try:
            yield self
        finally:
            with self.lock:
                cur = self.ops.get(op)
                if cur:
                    cur["depth"] -= 1
                    if cur["depth"] <= 0:
                        del self.ops[op]
                        self._send()

    def progress(self, op, pct, label=None):
        with self.lock:
            cur = self.ops.get(op)
            if not cur:
                return
            pct = max(0, min(100, int(pct)))
            if label:
                cur["label"] = label
            if cur["progress"] == pct:
                return
            cur["progress"] = pct
            last = self._last_emit.get(op, -100)
            if pct >= 100 or pct - last >= 5 or pct < last:
                self._last_emit[op] = pct
                self._send()

    def state(self):
        with self.lock:
            now = time.time()
            return [{k: v for k, v in o.items() if k != "depth"} | {"elapsed": round(now - o["started"], 1)}
                    for o in self.ops.values()]

    def blocking(self):
        with self.lock:
            return next((dict(o) for o in self.ops.values() if o["blocking"]), None)

    def active(self, op):
        with self.lock:
            return op in self.ops
