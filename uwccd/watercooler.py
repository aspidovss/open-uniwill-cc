"""Liquid cooler over Bluetooth LE — XMG Oasis Mk1 (LCT21001) / Mk2 (LCT22002) and their OEM twins
(Eluktronics Liquid Pad Pro, PC Specialist Liquid Series, TUXEDO Aquaris).

Linux counterpart of GCUService.MyFan.BTCooling.LiquidCooling. The command set was taken from the
original service and cross-checked against two community projects (independent implementation,
no code copied): tomups/watercooler-manager (Windows tray app) and anvme/watercooler-xmg-neo-linux
(headless Linux daemon, source of the temperature-tier idea).

Transport: Nordic UART Service. Every command is an 8-byte frame
    FE <cmd> <enable> <p1> <p2> <p3> <p4> EF
written to 6e400002; replies (firmware string, flow meter) arrive as notifications on 6e400003.
"""
import asyncio
import collections
import copy
import logging
import re
import threading
import time

from . import lc_curves as LCV
from . import regs as R
from . import store

log = logging.getLogger("uwccd.lc")

UART_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SYSTEM, FAN, PUMP, RGB, METER_PUSH, METER_QUERY, RGB_FX, LINE_OFF = 0x19, 0x1B, 0x1C, 0x1E, 0x31, 0x32, 0x33, 0x38
PUMP_CODE = {11: 0, 12: 1, 7: 2, 8: 3}          # LiquidCooling.PumpControl voltage -> selector
VOLTAGES = (7, 8, 11, 12)
PUMP_DUTY = 60                                   # the OEM service always runs the pump at 60 %
RGB_MODES = {"static": 0, "breathe": 1, "rainbow": 2, "breathe_rainbow": 3,
             "spiral": 4, "rotating_rainbow": 5, "color_wave": 6}
MK2_ONLY = ("spiral", "rotating_rainbow", "color_wave")
MODELS = {"LCT21001": "Mk1", "LCT22002": "Mk2"}
FW_RE = re.compile(r"(?:CoolingSystem FW V|MCU F/W Version: )(\d+(?:\.\d+)+)")

NO_TEMPS_PRESET = "medium"          # "auto" while the monitoring is off (EC Manager)
MODES = ("auto", "laptop", "ec", "low", "medium", "high", "manual", "off")
PRESETS = {"low": (25, 7), "medium": (50, 8), "high": (90, 11)}
# 7 V is the quietest but on some units the flow does not hold and the cooler switches itself off;
# the OEM service never runs below 8 V, so the tiers start there.
DEFAULT_TIERS = [{"below": 55, "fan": 25, "pump": 8}, {"below": 70, "fan": 50, "pump": 8},
                 {"below": 85, "fan": 75, "pump": 11}, {"below": 999, "fan": 90, "pump": 11}]
# "laptop" mode: the cooler follows the laptop's operating mode (Control Center X V5 behaviour)
LAPTOP_MODE_FAN = {0: 40, 1: 60, 2: 90, 3: 90}
LAPTOP_MODE_PUMP = 11
GUARD_FAN, GUARD_PUMP = 60, 11   # flow guard: no coolant flow -> pump 11 V, fan >= 60 %
HYSTERESIS = 3          # °C: step down a tier only when this much below its threshold
# Calm control (auto / ec modes): the temperature is averaged, a change must hold for a while, speeds ramp.
SMOOTH_WINDOW = 10.0    # s of temperature samples averaged
EMERGENCY_T = 95        # °C (average): step up at once
EMERGENCY_OVER = 8      # °C above the current tier's threshold: step up at once
FAN_STEP = 10           # % per control step (3 s) when ramping
FAN_DEADBAND = 3        # % — a curve change smaller than this is not sent (no hunting around a point)
EMERGENCY_JUMP = 25     # % — the curve asks this much more at once: no waiting
TEMP_SOURCES = ("max", "cpu", "gpu")
PUMP_IDLE = {"enabled": False, "off_below": 50, "off_after": 60, "on_above": 55, "on_after": 10, "min_run": 120}
METER_INTERVAL = 15.0
METER_TIMEOUT = 5.0
FLOW_GRACE = 5.0        # pump needs a few seconds before the flow sensor reports
BOOST_FAN, BOOST_PUMP = 60, 8   # OEM values for the Fn boost keys (0xCD / 0xCE)

DEFAULTS = {
    "enabled": False,            # keep connected / reconnect automatically
    "address": None, "name": None,
    "mode": "auto", "fan": 50, "pump": 8,
    "tiers": DEFAULT_TIERS,
    "rgb": {"on": True, "mode": "static", "color": [0, 128, 0]},   # LCSavingSettings default
    "notify_flow": True,
    "flow_guard": True,
    "boost_fan": False, "boost_pump": False,
    "temp_source": "max",          # max | cpu | gpu (GPU falls back to the CPU while the GPU sleeps)
    "delay_up": 10, "delay_down": 30, "smooth": True,
    "pump_idle": PUMP_IDLE,
    "curves": None,                # 1.6.8: fan curve + pump steps, common and per laptop mode (lc_curves.py)
    "profile": None,               # cooler profile the curves came from
    "profiles": [],                # own cooler profiles
}


def model_of(name):
    for k in MODELS:
        if k.lower() in (name or "").lower():
            return k
    return None


def frame(cmd, en=0, p1=0, p2=0, p3=0, p4=0):
    return bytes([0xFE, cmd, en & 0xFF, p1 & 0xFF, p2 & 0xFF, p3 & 0xFF, p4 & 0xFF, 0xEF])


# ------------------------------------------------------------------------------------------- links
class BleakLink:
    """BlueZ through bleak (python3-bleak)."""

    def __init__(self):
        import bleak  # noqa: F401  (ImportError -> feature unavailable)
        self.bleak = bleak
        self.client = None

    async def scan(self, timeout=8.0):
        found = await self.bleak.BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for dev, adv in found.values():
            name = dev.name or getattr(adv, "local_name", None) or ""
            if model_of(name):
                out.append({"address": dev.address, "name": name, "rssi": getattr(adv, "rssi", None),
                            "model": model_of(name)})
        return sorted(out, key=lambda d: -(d["rssi"] or -999))

    async def connect(self, address, on_notify, on_lost):
        dev = await self.bleak.BleakScanner.find_device_by_address(address, timeout=10.0)
        if dev is None:
            raise LookupError("cooler not found — is it powered on and within range?")
        client = self.bleak.BleakClient(dev, disconnected_callback=lambda _c: on_lost(), timeout=15.0)
        await asyncio.wait_for(client.connect(), 20)
        try:
            await client.start_notify(UART_RX, lambda _s, data: on_notify(bytes(data)))
        except BaseException:
            await client.disconnect()
            raise
        self.client = client
        return dev.name or ""

    @property
    def connected(self):
        return bool(self.client and self.client.is_connected)

    async def write(self, data):
        await asyncio.wait_for(self.client.write_gatt_char(UART_TX, bytes(data)), 5)

    async def disconnect(self):
        c, self.client = self.client, None
        if c and c.is_connected:
            await c.disconnect()


class MockLink:
    """Simulated LCT22002 for --mock and the tests."""

    DEVICES = [{"address": "C0:FF:EE:22:00:02", "name": "CoolingSystem LCT22002", "rssi": -48, "model": "LCT22002"}]
    last = None
    flow_ok = True

    def __init__(self):
        self.sent = []
        self.on_notify = self.on_lost = None
        self._conn = False
        self.pump_on = False
        MockLink.last = self

    async def scan(self, timeout=8.0):
        await asyncio.sleep(0.2)
        return copy.deepcopy(self.DEVICES)

    async def connect(self, address, on_notify, on_lost):
        d = next((d for d in self.DEVICES if d["address"].lower() == address.lower()), None)
        if not d:
            raise LookupError("cooler not found — is it powered on and within range?")
        self.on_notify, self.on_lost, self._conn = on_notify, on_lost, True
        return d["name"]

    @property
    def connected(self):
        return self._conn

    async def write(self, data):
        if not self._conn:
            raise ConnectionError("not connected")
        data = bytes(data)
        self.sent.append(data)
        loop = asyncio.get_running_loop()
        if data == b"sw":
            loop.call_later(0.02, self.on_notify, b"MCU F/W Version: 2.0.0.4")
        elif len(data) == 8 and data[1] == PUMP:
            self.pump_on = data[2] == 1 and data[3] > 0
        elif len(data) == 8 and data[1] == SYSTEM and data[3] == 1:
            self.pump_on = False
        elif len(data) == 8 and data[1] == METER_QUERY:
            ok = 2 if (self.pump_on and MockLink.flow_ok) else 0
            loop.call_later(0.02, self.on_notify, bytes([0xFE, METER_QUERY, 0x00, ok, 0xEF]))

    async def disconnect(self):
        self._conn = False


# ------------------------------------------------------------------------------------------ manager
class LiquidCooler:
    def __init__(self, ec, temp_fn, emit, mock=False, mode_fn=None):
        self.ec = ec
        self.temp_fn = temp_fn
        self.no_temps = lambda: False      # monitoring switched off completely (EC Manager): no temperatures
        self.mode_fn = mode_fn or (lambda: None)
        self.guard = False
        self._guard_mode = None
        self._lost_once = False
        self.emit = emit
        self.mock = mock
        self.path = store.path("liquid.json")
        self.cfg = copy.deepcopy(DEFAULTS)
        saved = store.load_json(self.path, {}) or {}
        self.cfg.update(saved)
        self.cfg["pump_idle"] = {**PUMP_IDLE, **(self.cfg.get("pump_idle") or {})}
        if LCV.migrate(self.cfg, DEFAULT_TIERS, stored=bool(saved)):     # 1.6.7 and older: tiers -> curves
            log.info("liquid cooler: temperature tiers converted to curves")
            try:
                store.save_json(self.path, self.cfg)
            except OSError:
                pass
        self.lock = threading.Lock()
        self.factory = MockLink if mock else BleakLink
        self.reason = None
        try:
            self.factory()
        except ImportError:
            self.reason = "bleak"           # python3-bleak missing
        self.available = self.reason is None
        self.ec_support = bool(ec.read(R.LC_SUPPORT) & 0x80)
        self.ec_table = bool(ec.read(R.LC_TABLE_SUPPORT) & 0x20)
        self.loop = None
        self.thread = None
        self.link = None
        self._reset_runtime()
        self.status_ = "idle"
        self.error = None
        self.scan_result = []
        self.suspended = False
        self._stop = False
        self._next_try = 0.0
        self._backoff = 10.0
        self._ready = threading.Event()

    def _reset_runtime(self):
        self.name = self.model = self.fw = self.fw_raw = None
        self.cur = (None, None)        # fan %, pump V actually sent
        self.pump_running = False
        self.meter = None
        self.flow = "idle"
        self.flow_deadline = 0.0
        self.priming = None
        self.tier = None
        self.curve_key = None          # which curve set drives the cooler now (common / office / ...)
        self.curve_raw = None          # what the curve asks for at the averaged temperature
        self.temp = None
        self.ec_target = None
        self.guard = False
        self.temp_avg = None
        self._temps = collections.deque()
        self._pending = None           # (direction, since) of a tier / EC target change waiting for its delay
        self._settled = None           # EC targets accepted so far
        self._emergency = False
        self._idle = False             # pump stopped because it is cool
        self._idle_mark = None         # since when the idle condition (cool / hot again) holds
        self._pump_on_since = 0.0

    # -- thread / loop plumbing -------------------------------------------------------------------
    def start(self):
        if not self.available or self.thread:
            return
        self.thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True, name="liquid")
        self.thread.start()
        self._ready.wait(5)

    def stop(self):
        if not self.loop:
            return
        try:
            self.call(self._disconnect(), timeout=8)
        except Exception:  # noqa: BLE001
            pass
        self._stop = True
        self._wake_up()

    def call(self, coro, timeout=30):
        if not self.loop:
            coro.close()
            raise NotImplementedError("liquid cooling is unavailable: python3-bleak is not installed")
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def _wake_up(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self._wake.set)

    def _changed(self, event="state", **extra):
        try:
            self.emit("lc", {"event": event, **extra})
        except Exception:  # noqa: BLE001
            pass

    def _save(self):
        store.save_json(self.path, self.cfg)

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._wlock = asyncio.Lock()
        self._fw_evt = asyncio.Event()
        self._meter_evt = asyncio.Event()
        self._monitor_task = None
        self._prime_task = None
        self._ready.set()
        while not self._stop:
            try:
                if self.link is None:
                    if (self.cfg["enabled"] and self.cfg["address"] and not self.suspended
                            and time.monotonic() >= self._next_try):
                        try:
                            await self._connect(self.cfg["address"])
                        except Exception as e:  # noqa: BLE001
                            self.error = str(e) or type(e).__name__
                            self.status_ = "idle"
                            self._next_try = time.monotonic() + self._backoff
                            log.info("cooler connect failed (%s), next try in %.0f s", self.error, self._backoff)
                            self._backoff = min(self._backoff * 2, 120.0)
                            self._changed()
                elif self.priming is None:
                    await self._apply_speed()
            except Exception as e:  # noqa: BLE001
                log.warning("cooler: %s", e)
                await self._lost_link(str(e))
            try:
                await asyncio.wait_for(self._wake.wait(), 3)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    # -- connection ---------------------------------------------------------------------------------
    async def _connect(self, address):
        self.status_ = "connecting"
        self.error = None
        self._changed()
        link = self.factory()
        name = await link.connect(address, self._notify_threadsafe, self._lost_threadsafe)
        self._reset_runtime()
        self.link = link
        self.name, self.model = name, model_of(name)
        try:
            self._fw_evt.clear()
            try:
                await self._write(b"sw")
                await asyncio.wait_for(self._fw_evt.wait(), 3)
            except asyncio.TimeoutError:
                pass                               # old firmware may not answer, control still works
            self.status_ = "connected"
            self._set_ec_flag(True)
            log.info("cooler connected: %s [%s] fw %s", name, address, self.fw or "?")
            await self._apply_rgb()
            await self._apply_speed(force=True)
        except BaseException:
            self.link = None
            self._set_ec_flag(False)
            self._reset_runtime()
            try:
                await link.disconnect()
            except Exception:  # noqa: BLE001
                pass
            raise
        self._backoff = 10.0
        if self.cfg["name"] != name:
            self.cfg["name"] = name
            self._save()
        self._monitor_task = asyncio.create_task(self._monitor())
        again, self._lost_once = self._lost_once, False
        self._changed("connected", name=name, again=again)

    def _set_ec_flag(self, on):
        """LiquidCooling.SetECSupport: bit1 of 0x7C7 — only on laptops that declare cooler support."""
        if self.ec_support:
            try:
                self.ec.set_bit(R.LC_CONNECTED, 1, on)
            except Exception as e:  # noqa: BLE001
                log.warning("EC 0x7C7: %s", e)

    def _lost_threadsafe(self):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._lost_link("link lost")))

    async def _lost_link(self, why):
        if self.link is None:
            return
        link, self.link = self.link, None
        self._cancel_tasks()
        try:
            await link.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self._set_ec_flag(False)
        self._reset_runtime()
        self.status_ = "idle"
        self.error = why
        self._lost_once = True
        self._next_try = time.monotonic() + 5
        log.warning("cooler disconnected: %s", why)
        self._changed("disconnected", unexpected=True)

    def _cancel_tasks(self):
        for t in (self._monitor_task, self._prime_task):
            if t and not t.done():
                t.cancel()
        self._monitor_task = self._prime_task = None

    async def _disconnect(self):
        """User disconnect / shutdown / suspend. Sleep first unless the firmware is known not to need it
        (plain disconnect already stops all outputs on Mk2 2.0.0.4)."""
        if self.link is None:
            return
        link = self.link
        self._cancel_tasks()
        sleep = not (self.model == "LCT22002" and self.fw == "2.0.0.4")
        try:
            if sleep and link.connected:
                await self._write(frame(SYSTEM, 0, 1))
                await asyncio.sleep(0.35)
        except Exception:  # noqa: BLE001
            pass
        self.link = None
        try:
            await link.disconnect()
        except Exception:  # noqa: BLE001
            pass
        self._set_ec_flag(False)
        self._reset_runtime()
        self.status_ = "idle"
        self._changed("disconnected")

    # -- I/O ---------------------------------------------------------------------------------------
    async def _write(self, data):
        async with self._wlock:
            if self.link is None or not self.link.connected:
                raise ConnectionError("cooler is not connected")
            await self.link.write(data)

    def _notify_threadsafe(self, data):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._on_notify, data)

    def _on_notify(self, data):
        if not data:
            return
        if data[0] == 0xFE:
            if len(data) in (5, 8) and data[-1] == 0xEF and data[1] in (METER_PUSH, METER_QUERY):
                self.meter = data[3]
                self._meter_evt.set()
                self._update_flow()
            return
        try:
            txt = data.decode("utf-8").strip("\x00\r\n ")
        except UnicodeDecodeError:
            return
        m = FW_RE.fullmatch(txt)
        if m:
            self.fw, self.fw_raw = m.group(1), txt
            self._fw_evt.set()

    async def _fan(self, duty):
        await self._write(frame(FAN, 1, duty) if duty > 0 else frame(FAN))

    async def _pump(self, volt, duty=PUMP_DUTY):
        if volt and duty:
            await self._write(frame(PUMP, 1, duty, PUMP_CODE[volt]))
        else:
            await self._write(frame(PUMP))
        running = bool(volt and duty)
        if running and not self.pump_running:
            self.meter = None
            self.flow_deadline = time.monotonic() + FLOW_GRACE
            self.loop.call_later(FLOW_GRACE + 0.2, self._update_flow)
        self.pump_running = running
        self._update_flow()

    def _update_flow(self):
        if self.priming is not None:
            new = "priming"
        elif not self.pump_running:
            new = "idle"
        elif self.meter == 2:
            new = "ok"
        elif time.monotonic() < self.flow_deadline:
            new = "starting"
        elif self.meter is None:
            new = "unknown"
        else:
            new = "fault"
        if new != self.flow:
            self.flow = new
            if new == "fault":
                log.warning("cooler reports no coolant flow (meter state %s)", self.meter)
                if self.cfg.get("flow_guard", True) and not self.guard and self.link is not None:
                    self.guard = True
                    self._guard_mode = self.mode_fn()
                    log.warning("flow guard: pump %d V, fan >= %d %%", GUARD_PUMP, GUARD_FAN)
                    self._wake_up()
                if self.cfg["notify_flow"]:
                    self._changed("flow_fault")
                    return
            self._changed()

    async def _monitor(self):
        """Get_Meter_State every 15 s while the pump runs."""
        while self.link is not None:
            if self.pump_running and self.priming is None:
                self._meter_evt.clear()
                try:
                    await self._write(frame(METER_QUERY))
                    await asyncio.wait_for(self._meter_evt.wait(), METER_TIMEOUT)
                except asyncio.TimeoutError:
                    self.meter = None
                self._update_flow()
            await asyncio.sleep(METER_INTERVAL)

    # -- speed policy -------------------------------------------------------------------------------
    # -- calm control ----------------------------------------------------------------------------
    @staticmethod
    def _now():
        return time.monotonic()

    def _read_temp(self):
        try:
            return self.temp_fn(self.cfg.get("temp_source", "max"))
        except TypeError:                         # a plain temperature function (tests)
            return self.temp_fn()

    def _sample_temp(self):
        """Current temperature -> the value decisions use (average over SMOOTH_WINDOW when smoothing)."""
        t, now = self._read_temp(), self._now()
        if t is not None:
            self.temp = t
            self._temps.append((now, t))
        while self._temps and now - self._temps[0][0] > SMOOTH_WINDOW:
            self._temps.popleft()
        if not self._temps:
            self.temp_avg = None
        elif not self.cfg.get("smooth", True):
            self.temp_avg = self._temps[-1][1]
        else:
            self.temp_avg = round(sum(v for _, v in self._temps) / len(self._temps), 1)
        return self.temp_avg

    def _wait(self, direction, urgent=False):
        """True when a change in `direction` (up / down) has been wanted for its delay (or is urgent)."""
        if urgent:
            self._pending = None
            self._emergency = True
            return True
        now = self._now()
        if not self._pending or self._pending[0] != direction:
            self._pending = (direction, now)
        delay = int(self.cfg.get("delay_up" if direction == "up" else "delay_down", 0))
        if now - self._pending[1] >= delay:
            self._pending = None
            return True
        return False

    def _settle_tier(self, raw, avg, tiers):
        cur = self.tier
        if cur is None or raw == cur:
            self._pending = None
            return raw
        up = raw > cur
        urgent = up and (avg >= EMERGENCY_T or avg >= min(tiers[cur]["below"], 200) + EMERGENCY_OVER)
        return raw if self._wait("up" if up else "down", urgent) else cur

    @staticmethod
    def _vidx(v):
        return VOLTAGES.index(v) if v in VOLTAGES else -1

    def _settle_pair(self, raw, avg):
        cur = self._settled
        if cur is None or raw == cur:
            self._pending = None
            self._settled = raw
            return raw
        up = raw[0] > cur[0] or self._vidx(raw[1]) > self._vidx(cur[1])
        if self._wait("up" if up else "down", up and avg is not None and avg >= EMERGENCY_T):
            self._settled = raw
        return self._settled

    def _pump_idle(self, pump, avg):
        """Stop the pump while it is cool (auto / ec modes, when enabled)."""
        pi = self.cfg.get("pump_idle") or PUMP_IDLE
        if not pi.get("enabled"):
            self._idle, self._idle_mark = False, None
            return pump
        if avg is None or not pump:
            return 0 if self._idle else pump
        now = self._now()
        if self._idle:
            if avg >= EMERGENCY_T:
                self._idle, self._idle_mark = False, None
            elif avg >= pi["on_above"]:
                self._idle_mark = self._idle_mark or now
                if now - self._idle_mark >= pi["on_after"]:
                    self._idle, self._idle_mark = False, None
            else:
                self._idle_mark = None
        elif avg < pi["off_below"]:
            self._idle_mark = self._idle_mark or now
            if now - self._idle_mark >= pi["off_after"] and now - self._pump_on_since >= pi["min_run"]:
                self._idle, self._idle_mark = True, None
                log.info("cooler pump stopped: %.1f °C is below %d °C", avg, pi["off_below"])
        else:
            self._idle_mark = None
        return 0 if self._idle else pump

    def _ramp(self, fan, pump):
        """Move towards the target gradually: fan by FAN_STEP, pump one voltage step per control step."""
        cf, cp = self.cur
        if cf is not None and fan is not None and abs(fan - cf) > FAN_STEP:
            fan = cf + FAN_STEP if fan > cf else cf - FAN_STEP
        if cp and pump and cp in VOLTAGES and pump in VOLTAGES:
            i, j = VOLTAGES.index(cp), VOLTAGES.index(pump)
            if abs(i - j) > 1:
                pump = VOLTAGES[i + (1 if j > i else -1)]
        return fan, pump

    def _curve_for(self, mode, laptop_mode):
        curves = self.cfg.get("curves")
        if mode == "laptop":
            return LCV.for_mode(curves, laptop_mode)
        return "common", LCV.full(curves)["common"]

    def _curve_target(self, cs, avg):
        """(fan, pump) from the curve set at the averaged temperature, with deadband, hysteresis for the pump
        steps and the up / down delays."""
        cur = self._settled
        if avg is None:                           # no temperature yet: keep what runs, or the curve at 60 °C
            if cur is None:
                self._settled = (LCV.fan_at(cs, 60), cs["pump"][LCV.pump_index(cs, 60)][1])
            return self._settled
        raw_f = LCV.fan_at(cs, avg)
        raw_p = cs["pump"][LCV.pump_index(cs, avg)][1]
        if cur is not None and self._vidx(raw_p) < self._vidx(cur[1]):      # a pump step down needs HYSTERESIS
            raw_p = max(raw_p, cs["pump"][LCV.pump_index(cs, avg + HYSTERESIS)][1], key=self._vidx)
        self.curve_raw = (raw_f, raw_p)
        if cur is not None and raw_p == cur[1] and abs(raw_f - cur[0]) < FAN_DEADBAND:
            self._pending = None
            return cur
        if cur is None:
            self._settled = (raw_f, raw_p)
            return self._settled
        up = raw_f > cur[0] or self._vidx(raw_p) > self._vidx(cur[1])
        urgent = up and (avg >= EMERGENCY_T or raw_f - cur[0] >= EMERGENCY_JUMP)
        if self._wait("up" if up else "down", urgent):
            self._settled = (raw_f, raw_p)
        return self._settled

    def _tier_index(self, t, tiers):
        for i, tr in enumerate(tiers):
            if t < tr["below"]:
                return i
        return len(tiers) - 1

    def target(self):
        """(fan %, pump V) for the current mode. Pump 0 = off."""
        c = self.cfg
        m = c["mode"]
        self.ec_target = None
        laptop_mode = self.mode_fn()
        self._emergency = False
        calm = False
        if self.guard and laptop_mode != self._guard_mode:    # the laptop's mode changed -> guard ends
            self.guard = False
        if m not in ("auto", "laptop", "ec"):
            self.curve_key = self.curve_raw = None
        if m == "off":
            fan, pump = 0, 0
        elif m in PRESETS:
            fan, pump = PRESETS[m]
        elif m == "manual":
            fan, pump = int(c["fan"]), int(c["pump"])
        elif m in ("auto", "laptop") and self.no_temps():   # no temperatures: a flat curve, otherwise a preset
            key, cs = self._curve_for(m, laptop_mode)
            self.curve_key, self.curve_raw = key, None
            fan, pump = ((cs["fan"][0][1], cs["pump"][0][1]) if LCV.is_flat(cs) else PRESETS[NO_TEMPS_PRESET])
        else:
            fan = pump = None
            calm = True
            avg = self._sample_temp()
            if m == "ec" and self.ec_table:
                f, p = self.ec.read(R.LC_EC_FAN), self.ec.read(R.LC_EC_PUMP)
                if f & 0x80 and p & 0x80 and (p & 0x7F) in (0, *VOLTAGES):
                    self.ec_target = (min(100, f & 0x7F), p & 0x7F)
                    if self.curve_key is not None:
                        self._settled, self.curve_key, self.curve_raw = None, None, None
                    fan, pump = self._settle_pair(self.ec_target, avg)
            if fan is None:                       # "auto", "laptop", or the EC publishes nothing: the curves
                key, cs = self._curve_for(m, laptop_mode)
                if key != self.curve_key:         # another curve set (laptop mode changed): no waiting
                    self._settled, self._pending, self.curve_key = None, None, key
                fan, pump = self._curve_target(cs, avg)
            pump = self._pump_idle(pump, avg)
        if calm and c.get("smooth", True) and not self._emergency and not self.guard:
            fan, pump = self._ramp(fan, pump)
        if m != "off":
            if c["boost_fan"]:
                fan = max(fan, BOOST_FAN)
            if c["boost_pump"] and pump:
                pump = max(pump, BOOST_PUMP, key=lambda v: VOLTAGES.index(v))
            if self.guard and pump:
                pump = max(pump, GUARD_PUMP, key=lambda v: VOLTAGES.index(v))
                fan = max(fan, GUARD_FAN)
        return fan, pump

    async def _apply_speed(self, force=False):
        fan, pump = self.target()
        if force or fan != self.cur[0]:
            await self._fan(fan)
            self.cur = (fan, self.cur[1])
            log.info("cooler fan %d%% (mode %s)", fan, self.cfg["mode"])
            self._changed()
        if force or pump != self.cur[1]:
            if pump and not self.cur[1]:
                self._pump_on_since = self._now()
            await self._pump(pump)
            self.cur = (self.cur[0], pump)
            log.info("cooler pump %s (mode %s)", f"{pump} V" if pump else "off", self.cfg["mode"])
            self._changed()

    async def _apply_rgb(self):
        rgb = self.cfg["rgb"]
        mk2 = self.model == "LCT22002"
        if mk2:
            await self._write(frame(RGB_FX))       # an active Mk2 effect overrides the base colour
        if not rgb["on"]:
            await self._write(frame(RGB))
            return
        mode = rgb["mode"]
        if mode in MK2_ONLY and not mk2:
            mode = "static"
        r, g, b = rgb["color"]
        base = 0 if mode in MK2_ONLY else RGB_MODES[mode]
        await self._write(frame(RGB, 1, r, g, b, base))
        if mk2 and mode != "static":
            await self._write(frame(RGB_FX, 1, r, g, b, RGB_MODES[mode]))

    async def _prime(self):
        """InputWaterMode: 8 cycles of pump off 0.5 s / 100 % at 8 V 5.5 s / off 2.5 s, fan 50 %."""
        try:
            self.priming = 0
            self._update_flow()
            await self._write(frame(SYSTEM, 1, 4, 0x50))
            await self._fan(50)
            self.cur = (50, self.cur[1])
            for i in range(8):
                self.priming = i + 1
                self._changed()
                await self._pump(0)
                await asyncio.sleep(0.5)
                await self._pump(8, duty=100)
                await asyncio.sleep(5.5)
                await self._pump(0)
                await asyncio.sleep(2.5)
        finally:
            self.priming = None
            self.cur = (None, None)
            if self.link is not None:
                try:
                    await self._write(frame(SYSTEM, 0, 4, 0))
                finally:
                    self._prime_task = None
                    self._wake.set()
            self._changed("prime_done")

    # -- public API (called from HTTP threads) --------------------------------------------------------
    def scan(self):
        async def run():
            self.status_ = "scanning" if self.link is None else self.status_
            self._changed()
            try:
                self.scan_result = await self.factory().scan()
            finally:
                if self.status_ == "scanning":
                    self.status_ = "idle"
                self._changed()
            return self.scan_result
        return self.call(run(), timeout=30)

    def connect(self, address):
        address = str(address).strip()
        if not re.fullmatch(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}", address):
            raise ValueError("bad Bluetooth address")

        async def run():
            if self.link is not None:
                await self._disconnect()
            self.suspended = False
            try:
                await self._connect(address)
            except Exception:
                self.status_ = "idle"
                self._changed()
                raise
            self.cfg.update(enabled=True, address=address)
            self._save()
        self.call(run(), timeout=60)

    def disconnect(self, forget=False):
        async def run():
            self.cfg["enabled"] = False
            if forget:
                self.cfg["address"] = self.cfg["name"] = None
            self._save()
            await self._disconnect()
        self.call(run(), timeout=15)

    def configure(self, b):
        c = copy.deepcopy(self.cfg)
        if "mode" in b:
            if b["mode"] not in MODES:
                raise ValueError("mode")
            if b["mode"] == "ec" and not self.ec_table:
                raise ValueError("this laptop's EC does not publish cooler targets")
            c["mode"] = b["mode"]
        if "fan" in b:
            f = int(b["fan"])
            if not 0 <= f <= 100:
                raise ValueError("fan 0..100")
            c["fan"] = f
        if "pump" in b:
            p = int(b["pump"])
            if p not in (0, *VOLTAGES):
                raise ValueError("pump voltage 0/7/8/11/12")
            c["pump"] = p
        if "tiers" in b:                          # 1.6.7 and older: tiers become the common curve
            c["tiers"] = self._check_tiers(b["tiers"])
            c["curves"] = LCV.full(c.get("curves"))
            c["curves"]["common"] = LCV.from_tiers(c["tiers"])
        if "curves" in b:
            c["curves"] = LCV.check_curves(b["curves"], c.get("curves"))
        if "temp_source" in b:
            if b["temp_source"] not in TEMP_SOURCES:
                raise ValueError("temperature source: max / cpu / gpu")
            c["temp_source"] = b["temp_source"]
        for k in ("delay_up", "delay_down"):
            if k in b:
                v = int(b[k])
                if not 0 <= v <= 300:
                    raise ValueError("delay 0..300 s")
                c[k] = v
        if "smooth" in b:
            c["smooth"] = bool(b["smooth"])
        if "pump_idle" in b:
            c["pump_idle"] = self._check_idle({**c["pump_idle"], **b["pump_idle"]})
        if any(k in b for k in ("mode", "fan", "pump")):
            self.guard = False                       # a choice by hand ends the flow guard
        for k in ("notify_flow", "flow_guard", "boost_fan", "boost_pump"):
            if k in b:
                c[k] = bool(b[k])
        if "rgb" in b:
            r = b["rgb"]
            rgb = dict(c["rgb"])
            if "on" in r:
                rgb["on"] = bool(r["on"])
            if "mode" in r:
                if r["mode"] not in RGB_MODES:
                    raise ValueError("rgb mode")
                if r["mode"] in MK2_ONLY and self.model and self.model != "LCT22002":
                    raise ValueError("this lighting effect needs an Mk2 (LCT22002) cooler")
                rgb["mode"] = r["mode"]
            if "color" in r:
                col = [int(x) for x in r["color"]]
                if len(col) != 3 or not all(0 <= x <= 255 for x in col):
                    raise ValueError("color")
                rgb["color"] = col
            c["rgb"] = rgb
        with self.lock:
            rgb_changed = c["rgb"] != self.cfg["rgb"]
            self.cfg = c
            self._save()
        if self.loop and self.link is not None:
            if rgb_changed:
                self.call(self._apply_rgb(), timeout=10)
            self._wake_up()
        self._changed()

    def profile(self, b):
        """Cooler profiles: apply / save / copy / remove / rename."""
        with self.lock:
            c = copy.deepcopy(self.cfg)
            pid = LCV.profile_action(c, b)
            self.cfg = c
            self._save()
        self._wake_up()
        self._changed()
        return pid

    @staticmethod
    def _check_idle(pi):
        out = {"enabled": bool(pi["enabled"])}
        for k, lo, hi in (("off_below", 30, 85), ("on_above", 32, 95), ("off_after", 10, 900), ("on_after", 0, 120),
                          ("min_run", 0, 1800)):
            v = int(pi[k])
            if not lo <= v <= hi:
                raise ValueError(f"pump idle {k}: {lo}..{hi}")
            out[k] = v
        if out["on_above"] < out["off_below"] + 2:
            raise ValueError("the pump must restart at least 2 °C above the temperature it stops at")
        return out

    @staticmethod
    def _check_tiers(tiers):
        if not isinstance(tiers, list) or not 1 <= len(tiers) <= 8:
            raise ValueError("1..8 tiers")
        out, last = [], -1
        for i, t in enumerate(tiers):
            below, fan, pump = int(t["below"]), int(t["fan"]), int(t["pump"])
            if i == len(tiers) - 1:
                below = 999
            if below <= last or not 20 <= below <= 999:
                raise ValueError("tier temperatures must increase (20..110 °C)")
            if not 0 <= fan <= 100 or pump not in (0, *VOLTAGES):
                raise ValueError("tier fan 0..100 %, pump off/7/8/11/12 V")
            out.append({"below": below, "fan": fan, "pump": pump})
            last = below
        return out

    def toggle_boost(self, which):
        key = "boost_fan" if which == "fan" else "boost_pump"
        self.cfg[key] = not self.cfg[key]
        self._save()
        self._wake_up()
        self._changed("boost", which=which, on=self.cfg[key])

    def prime(self, stop=False):
        async def run():
            if stop:
                if self._prime_task:
                    self._prime_task.cancel()
                return
            if self.link is None:
                raise ConnectionError("cooler is not connected")
            if self._prime_task and not self._prime_task.done():
                return
            self._prime_task = asyncio.create_task(self._prime())
        self.call(run(), timeout=10)

    def suspend(self):
        """system-sleep pre: put the cooler to sleep and drop the link (reconnects on resume)."""
        if not self.loop:
            return

        async def run():
            self.suspended = True
            await self._disconnect()
        self.call(run(), timeout=10)

    def resume(self):
        if not self.loop:
            return
        self.suspended = False
        self._next_try = time.monotonic() + 3      # give BlueZ a moment after wake-up
        self._backoff = 10.0
        self._wake_up()

    def status(self):
        c = self.cfg
        return {
            "available": self.available, "reason": self.reason,
            "status": "connected" if self.link is not None else self.status_,
            "connected": self.link is not None,
            "error": self.error,
            "name": self.name or c.get("name"), "model": self.model, "generation": MODELS.get(self.model),
            "fw": self.fw, "fw_raw": self.fw_raw,
            "fan": self.cur[0], "pump": self.cur[1], "flow": self.flow, "priming": self.priming,
            "guard": self.guard, "laptop_mode_fan": LAPTOP_MODE_FAN,
            "temp": self.temp, "tier": self.tier, "ec_target": self.ec_target,
            "temp_avg": self.temp_avg, "pump_idle": self._idle,
            "pending": ({"dir": self._pending[0],
                         "left": max(0, round(int(c.get("delay_up" if self._pending[0] == "up" else "delay_down", 0))
                                              - (self._now() - self._pending[1])))} if self._pending else None),
            "ec_support": self.ec_support, "ec_table": self.ec_table, "suspended": self.suspended,
            "no_temps": bool(self.cfg.get("mode") == "auto" and self.no_temps()), "no_temps_preset": NO_TEMPS_PRESET,
            "config": copy.deepcopy(c), "scan": self.scan_result,
            "presets": {k: {"fan": v[0], "pump": v[1]} for k, v in PRESETS.items()},
            "rgb_modes": list(RGB_MODES), "mk2_only": list(MK2_ONLY), "voltages": list(VOLTAGES),
            "default_tiers": DEFAULT_TIERS,
            "curve_key": self.curve_key, "curve_raw": self.curve_raw,
            "curves": LCV.full(c.get("curves")), "curve_keys": list(LCV.CURVE_KEYS),
            "pump_levels": list(LCV.PUMP_LEVELS), "max_fan_points": LCV.MAX_FAN_POINTS,
            "max_pump_steps": LCV.MAX_PUMP_STEPS,
            "profiles": [{"id": p["id"], "name": p["name"], "builtin": p["builtin"]} for p in LCV.profiles(c)],
            "profile": c.get("profile"), "profile_modified": LCV.modified(c),
        }
