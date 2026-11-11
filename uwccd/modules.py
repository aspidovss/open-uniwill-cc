"""Module registry of the service (1.8.0.0).

Every optional part of the service is registered here under one small interface: name, start, stop, running,
enabled. The window (Switches → Service modules), `uwccctl modules` and the API (`/api/module`) switch modules on
and off; the choice is kept in the settings (key "modules": {name: false}) and honoured at the next start too.

Two kinds of modules:
  * live=True  — stop() and start() work while the service runs: the switch acts at once;
  * live=False — the module is woven into the service start: the switch takes effect at the next service start.

Core parts (EC access, fans/modes, switches, battery, the API itself) are not modules: they cannot be turned off.
"""
import logging
import threading

log = logging.getLogger("uwcc.modules")


class Modules:
    def __init__(self, settings_store, emit=lambda *a: None):
        self.st = settings_store
        self.emit = emit
        self.entries = {}                 # name -> dict, insertion order = display order
        self.lock = threading.Lock()

    # -- registration (service start) -------------------------------------------------------------
    def register(self, name, title, *, start=None, stop=None, running=None, available=True, live=None, note=""):
        """start/stop: callables (None: nothing to do); running: () -> bool; available: this laptop has the
        hardware / OS for it; live: switch acts at once (default: both start and stop given)."""
        self.entries[name] = {"name": name, "title": title, "start": start, "stop": stop, "running": running,
                              "available": bool(available), "note": note,
                              "live": (start is not None and stop is not None) if live is None else live}

    # -- state ------------------------------------------------------------------------------------
    def enabled(self, name):
        return bool((self.st.get("modules") or {}).get(name, True))

    def running(self, name):
        e = self.entries.get(name)
        if not e or not e["available"]:
            return False
        try:
            return bool(e["running"]()) if e["running"] else self.enabled(name)
        except Exception:  # noqa: BLE001
            return False

    def status(self):
        return [{"name": n, "title": e["title"], "available": e["available"], "enabled": self.enabled(n),
                 "running": self.running(n), "live": e["live"], "note": e["note"]}
                for n, e in self.entries.items()]

    # -- switching ---------------------------------------------------------------------------------
    def set_enabled(self, name, on):
        e = self.entries.get(name)
        if not e:
            raise KeyError(name)
        on = bool(on)
        with self.lock:
            cur = dict(self.st.get("modules") or {})
            cur[name] = on
            self.st.set("modules", cur)
            if e["available"] and e["live"]:
                try:
                    if on and e["start"] and not self.running(name):
                        e["start"]()
                    elif not on and e["stop"]:
                        e["stop"]()
                except Exception:  # noqa: BLE001
                    log.exception("module %s -> %s", name, on)
        log.info("module %s: %s%s", name, "on" if on else "off", "" if e["live"] else " (next service start)")
        self.emit("modules", {"name": name, "enabled": on, "running": self.running(name), "live": e["live"]})

    def start_enabled(self):
        """Service start: start the enabled live modules, skip the disabled ones."""
        for n, e in self.entries.items():
            if e["available"] and e["start"] and self.enabled(n):
                try:
                    e["start"]()
                except Exception:  # noqa: BLE001
                    log.exception("module %s start", n)
