"""The laptop's own interface when there is no Uniwill embedded controller: Control Center 3.0 / Clevo (also on Tongfang
laptops with Control Center 3.x) or Leishen / Thunderobot. One face of it for the main pages (Mode selection, Fan
settings, Keyboard backlight), the tray, the automation rules and uwccctl.

The modes keep the numbers of the Uniwill ones where they mean about the same (0 quiet / office, 1 balanced / gaming,
2 performance / turbo), so the rules, the tray icon and the history work unchanged; 3 is the fourth mode of Clevo
(power saving), Leishen has three. Both modules stay experimental: their commands are sent only after "Allow
commands" (settings clevo_writes / leishen_writes), which the window asks for in its banner.
"""
import logging

log = logging.getLogger("uwccd.altplat")

CLEVO_MODES = ((0, "quiet"), (1, "entertainment"), (2, "performance"), (3, "powersave"))
LEISHEN_MODES = ((0, "office"), (1, "gaming"), (2, "performance"))
NAMES = {"clevo": "Control Center 3.0 / Clevo", "leishen": "Leishen / Thunderobot"}


class AltPlatform:
    def __init__(self, kind, module):
        self.kind = kind
        self.mod = module
        self.table = CLEVO_MODES if kind == "clevo" else LEISHEN_MODES

    @property
    def name(self):
        return NAMES[self.kind]

    def writes_allowed(self):
        return self.mod.writes_allowed()

    def mode_id(self):
        """The current mode by its module name (Clevo: the last one set here, its firmware does not report it)."""
        if self.kind == "clevo":
            return self.mod.state().get("power_mode")
        try:
            return self.mod.mode()
        except Exception as e:  # noqa: BLE001
            log.debug("mode: %s", e)
            return None

    def mode_index(self):
        cur = self.mode_id()
        return next((i for i, m in self.table if m == cur), None)

    def index_of(self, mode):
        """A mode number or a module name ("performance") -> its number; ValueError when there is none here."""
        if isinstance(mode, str) and not mode.lstrip("-").isdigit():
            for i, m in self.table:
                if m == mode:
                    return i
            raise ValueError(f"mode {mode} ({', '.join(m for _, m in self.table)})")
        i = int(mode)
        if i not in dict(self.table):
            raise ValueError(f"mode {i} is not available here ({', '.join(str(n) for n, _ in self.table)})")
        return i

    def set_mode(self, mode):
        i = self.index_of(mode)
        name = dict(self.table)[i]
        if self.kind == "clevo":
            self.mod.set_power_mode(name)
        else:
            self.mod.set_mode(name)
        self.mod.emit(self.kind, {})
        return i

    def status(self):
        return {"platform": self.kind, "name": self.name, "level": "experimental",
                "modes": [{"index": i, "id": m} for i, m in self.table], "mode": self.mode_index(),
                "mode_id": self.mode_id(), "writes": self.writes_allowed()}


def alt_platform(svc):
    """The AltPlatform of this laptop, or None when the Uniwill EC (or nothing) is what the program works with."""
    reason = (getattr(svc, "ec_info", None) or {}).get("reason")
    if reason == "clevo_only" and getattr(svc, "clevo", None) is not None and svc.clevo.present:
        return AltPlatform("clevo", svc.clevo)
    if reason == "leishen_only" and getattr(svc, "leishen", None) is not None and svc.leishen.present:
        return AltPlatform("leishen", svc.leishen)
    return None


def clevo_monitor_fans(clevo):
    """Clevo fans in the format of the Monitor page / history."""
    def fans():
        try:
            fs = {f["fan"]: f for f in clevo.fans()}
        except Exception as e:  # noqa: BLE001  (the monitor keeps running without the fans)
            log.debug("Clevo fans: %s", e)
            return {"cpu_duty": None, "cpu_rpm": 0}
        c, g = fs.get("cpu") or {}, fs.get("gpu1") or {}
        d = {"cpu_duty": c.get("duty"), "cpu_rpm": c.get("rpm") or 0}
        if g:
            d.update(gpu_duty=g.get("duty"), gpu_rpm=g.get("rpm") or 0)
        return d
    return fans
