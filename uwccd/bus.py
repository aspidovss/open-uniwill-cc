"""Event bus of the service (1.8.0.0).

One place through which every event of the service passes. Modules do not call each other on events: they publish
with `bus.emit(kind, data)` and subscribe with `bus.subscribe(kind, fn)`. The same events go out to the clients
(window, tray, agent, scripts) as the `/api/events` stream, documented in docs/API.md — EVENTS below is that
contract. Commands to the hardware stay ordinary method calls (they need order, locks and a result), the bus only
carries notifications.
"""
import json
import logging
import queue
import threading
import time

log = logging.getLogger("uwcc.bus")

# The event contract: kind -> what it tells. New events are added here first (docs/API.md repeats this table).
EVENTS = {
    "status": "something changed: re-read /api/state",
    "mode": "laptop mode applied {mode, slot?, osd}",
    "fanboost": "Fan Boost switched {on, osd?}",
    "setting": "a setting changed {key, value}",
    "monitor": "sensor sample (only on /api/events?monitor=1 clients)",
    "battery": "battery settings changed",
    "keyboard": "keyboard backlight state (status dict)",
    "kb_level": "keyboard backlight level for the OSD {level}",
    "lightbar": "light bar state",
    "lc": "liquid cooler: connection, config, flow, hwoc {event, ...}",
    "ac": "power source changed {online}",
    "overheat": "temperature held over the limit {sensor, temp, limit, boost}",
    "overheat_boost": "Fan Boost turned on because of overheating {sensor, temp}",
    "load_rule": "an automation rule applied something {rule, mode, slot}",
    "launch": "Fn launch key pressed",
    "osd": "show an on-screen notification {code}",
    "wmi": "raw firmware event with fan control off {code}",
    "update": "an update is available {version, url, optional}",
    "update_install": "the tray should download and install {version}",
    "toast": "text the window shows once {text, error?}",
    "reveal": "the tray shows a downloaded file {name}",
    "restarting": "the service is restarting {reason}",
    "busy": "long operation progress {ops}",
    "admin": "administrator unlock state (status dict)",
    "admin_request": "the window asks the tray for the UAC prompt",
    "selfcheck": "self-check progress {stage, ...}",
    "selfcheck_backup": "self-check saved an EC snapshot",
    "selfcheck_restore": "self-check put the EC snapshot back",
    "detect": "platform detection finished (status dict)",
    "afterburner": "an Afterburner profile was applied {slot, error}",
    "clevo": "Control Center 3.0 / Clevo state changed",
    "leishen": "Leishen / Thunderobot state changed",
    "modules": "a module was enabled or disabled {name, enabled, running}",
}


class EventBus:
    """Internal subscriptions (sync callbacks) + the SSE queues of connected clients."""

    def __init__(self):
        self.lock = threading.Lock()
        self._subs = {}                  # kind -> [fn]; "*" matches every kind
        self._queues = []                # SSE listeners (json strings)
        self._unknown = set()            # unknown kinds already warned about

    # -- internal subscribers -------------------------------------------------------------------
    def subscribe(self, kind, fn):
        """fn(kind, data) is called on every `kind` event ("*": on all), on the emitter's thread: return fast,
        never write to the EC from here — start a thread or set an event for your own loop instead."""
        with self.lock:
            self._subs.setdefault(kind, []).append(fn)
        return lambda: self.unsubscribe(kind, fn)

    def unsubscribe(self, kind, fn):
        with self.lock:
            if fn in self._subs.get(kind, []):
                self._subs[kind].remove(fn)

    # -- SSE listeners --------------------------------------------------------------------------
    def listen(self):
        q = queue.Queue(maxsize=200)
        with self.lock:
            self._queues.append(q)
        return q

    def unlisten(self, q):
        with self.lock:
            if q in self._queues:
                self._queues.remove(q)

    # -- publishing -----------------------------------------------------------------------------
    def emit(self, kind, data):
        if kind not in EVENTS and kind not in self._unknown:
            self._unknown.add(kind)
            log.warning("event %r is not in bus.EVENTS — add it there and to docs/API.md", kind)
        with self.lock:
            subs = list(self._subs.get(kind, ())) + list(self._subs.get("*", ()))
            queues = list(self._queues)
        for fn in subs:
            try:
                fn(kind, data)
            except Exception:  # noqa: BLE001
                log.exception("event subscriber %s(%s)", getattr(fn, "__name__", fn), kind)
        msg = json.dumps({"type": kind, "data": data, "t": time.time()})
        for q in queues:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass
