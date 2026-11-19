"""Device managers of the Flydigi coolers.

Port of THRM (MIT, Copyright (c) 2025 Tianli, https://github.com/TIANLI0/THRM):
  * HidCooler  <- internal/device/device.go (Manager), response.go, query.go — BS2 / BS2 Pro / BS3 / BS3 Pro;
  * BS1Cooler  <- internal/device/ble.go (BLEManager), bs1_hid.go — BS1 over Bluetooth LE or USB HID.

The control logic is THRM's, step by step: realtime mode is entered once and the same target is not sent twice;
a target of 0 RPM keeps the realtime session (no 0x24 after it); waking from 0 runs the firmware's own motor start
(0x24, the current fixed gear by 0x08, 450 ms, 0x23, at least 1700 RPM for 450 ms, then the target) and the
tachometer is checked 3 s later; three failed realtime writes are followed by a read-only 0x25 probe before the
link is dropped; commands that rewrite the firmware's data flash (0x0C, 0x0D, 0x26, 0x48) are spaced 150 ms
apart and skipped when the device already holds the value; gear selections are checked against the controller's
capability tier and confirmed by the 0xEF status.
"""
import asyncio
import collections
import logging
import threading
import time

from . import hidio, proto as P

log = logging.getLogger("uwccd.flydigi")

# device.go constants
MAX_CONSECUTIVE_READ_ERRORS = 20
MAX_CONSECUTIVE_REALTIME_WRITE_ERRORS = 3
REALTIME_WAKE_KICK_RPM = 1700
REALTIME_WAKE_KICK_DURATION = 0.45
REALTIME_WAKE_VERIFY_DELAY = 3.0
GEAR_SELECTION_VERIFY_TIMEOUT = 1.4
HID_READ_POLL_INTERVAL = 0.1
HID_READ_ERROR_RETRY_DELAY = 0.5
GEAR_RPM_SLOT_COUNT = 4
FLASH_WRITE_SPACING = 0.15
REALTIME_WRITE_ERROR_DECAY = 120.0
DEVICE_RESPONSE_TIMEOUT = 0.9            # response.go
HID_LINK_ALIVE_WINDOW = 3.0              # link_health.go
FIRMWARE_VERSION_QUERY_ATTEMPTS, FIRMWARE_VERSION_RETRY_DELAY = 3, 0.08
# bs1_hid.go / ble.go
BS1_HID_IDLE_TIMEOUT = 20.0
BS1_HID_PROBE_TIMEOUT = 2.0
BS1_MODE_SWITCH_DELAY = 0.05
BS1_KEEPALIVE_INTERVAL = 3.0
DEFAULT_BLE_SCAN_TIMEOUT = 10.0
BS1_SERVICE_FALLBACK_DELAY = 3.0
BS1_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
BS1_WRITE_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"
BS1_NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
BS1_DEVICE_NAME = "Flydigi BS1"

HID_DETAILED_QUERY_COMMANDS = (P.CMD_QUERY_FIRMWARE_VERSION, P.CMD_QUERY_CONFIG_STATE, P.CMD_QUERY_DEVICE_ID,
                               P.CMD_QUERY_CONTROLLER_CAPABILITY, P.CMD_QUERY_RUNTIME_PROFILE,
                               P.CMD_QUERY_IDENTITY_BLOCK, P.CMD_QUERY_RPM_STATE, P.CMD_QUERY_GEAR_RPM_TABLE,
                               P.CMD_QUERY_WORK_MODE, P.CMD_RGB_STATUS)
BASIC_DEVICE_SETTINGS_QUERY_COMMANDS = (P.CMD_QUERY_GEAR_RPM_TABLE, P.CMD_QUERY_WORK_MODE, P.CMD_RGB_STATUS)


class DeviceError(Exception):
    pass


class ResponseBroker:
    """response.go responseBroker: frames from the read loop go to the command waiting for that exact reply."""

    def __init__(self):
        self.lock = threading.Lock()
        self.waiters = collections.defaultdict(list)

    def register(self, command):
        w = {"command": command, "event": threading.Event(), "frame": None}
        with self.lock:
            self.waiters[command].append(w)
        return w

    def cancel(self, w):
        with self.lock:
            q = self.waiters.get(w["command"])
            if q and w in q:
                q.remove(w)
            if not q:
                self.waiters.pop(w["command"], None)

    def deliver(self, frame):
        if frame is None or not frame.checksum_ok:
            return False
        with self.lock:
            q = self.waiters.get(frame.command)
            if not q:
                return False
            w = q.pop(0)
            if not q:
                self.waiters.pop(frame.command, None)
        w["frame"] = frame
        w["event"].set()
        return True

    def wait(self, w, timeout=DEVICE_RESPONSE_TIMEOUT):
        try:
            if not w["event"].wait(timeout if timeout and timeout > 0 else DEVICE_RESPONSE_TIMEOUT):
                raise TimeoutError(f"no reply to command 0x{w['command']:02X}")
            return w["frame"]
        finally:
            self.cancel(w)


def validate_ack(frame, *accepted):
    """response.go validateACK"""
    if not frame.payload:
        raise DeviceError(f"command 0x{frame.command:02X} returned an empty ACK")
    st = frame.payload[0]
    if st not in accepted:
        raise DeviceError(f"command 0x{frame.command:02X} refused by the firmware: status {st} "
                          f"({P.ack_status_name(frame.command, st)})")


def realtime_recovery_needs_disconnect(probe_ok, recent_response):
    return not probe_ok and not recent_response


class BaseCooler:
    """What both managers share: the cached 0xEF status and the change callback."""
    kind = "hid"
    model = "?"

    def __init__(self, on_update=None, on_lost=None):
        self.on_update = on_update or (lambda: None)
        self.on_lost = on_lost or (lambda: None)
        self.status = None             # decoded 0xEF (proto.decode_status) + "t"
        self.connected = False
        self.info = {}

    def _publish(self, st):
        st["t"] = time.time()
        self.status = st
        try:
            self.on_update()
        except Exception:  # noqa: BLE001
            log.exception("flydigi update")


# =================================================================================================================
class HidCooler(BaseCooler):
    """BS2 / BS2 Pro / BS3 / BS3 Pro over HID (USB or Bluetooth HID after pairing in the system)."""
    kind = "hid"

    def __init__(self, dev_info, on_update=None, on_lost=None):
        super().__init__(on_update, on_lost)
        self.pid = dev_info["pid"]
        self.model = hidio.MODEL.get(self.pid, "Unknown")
        self.transport = "bluetooth" if dev_info.get("bus") == hidio.BUS_BLUETOOTH else \
            "usb" if dev_info.get("bus") == hidio.BUS_USB else "hid"
        self.dev = hidio.open_device(dev_info)
        self.unnumbered = hidio.unnumbered_usb(dev_info)
        if self.unnumbered:
            log.info("USB HID with unnumbered output reports: 31 data bytes after a 0x00 report number")
        self.info = {"model": self.model, "product_id": f"0x{self.pid:04X}", "path": dev_info["path"],
                     "name": dev_info.get("name") or ""}
        self.mutex = threading.RLock()            # m.mutex: one command sequence at a time
        self.write_lock = threading.Lock()
        self.responses = ResponseBroker()
        self.stop_ev = threading.Event()
        self.last_rx = 0.0
        self._reset_realtime_control_state()
        self._reset_light_state_cache()
        self._reset_gear_rpm_cache()
        self.last_flash_write_at = 0.0
        self.controller_tier = None
        self.connected = True
        self.thread = threading.Thread(target=self._monitor, daemon=True, name="flydigi-hid")
        self.thread.start()

    # -- state resets (device.go) --------------------------------------------------------------------------------
    def _reset_realtime_control_state(self):
        self.realtime_wake_gen = getattr(self, "realtime_wake_gen", 0) + 1
        self.last_commanded_rpm = 0
        self.has_commanded_rpm = False
        self.realtime_mode = False
        self.consecutive_realtime_write_errors = 0
        self.realtime_write_recovery_scheduled = False
        self.last_realtime_write_error_at = 0.0

    def _reset_light_state_cache(self):
        self.gear_light = None

    def _reset_gear_rpm_cache(self):
        self.device_gear_rpm = [None] * GEAR_RPM_SLOT_COUNT

    # -- I/O ----------------------------------------------------------------------------------------------------
    def _write_frame(self, cmd, payload=b""):
        frame = P.build_frame(cmd, *payload)
        P.validate_outbound_frame(frame)
        report = hidio.build_hid_report(frame, self.unnumbered)
        with self.write_lock:
            if self.dev is None:
                raise DeviceError("device is not connected")
            self.dev.write(report)

    def _command_and_wait(self, cmd, payload=b"", timeout=DEVICE_RESPONSE_TIMEOUT):
        """sendHIDCommandAndWaitLocked"""
        w = self.responses.register(cmd)
        try:
            self._write_frame(cmd, payload)
        except Exception:
            self.responses.cancel(w)
            raise
        return self.responses.wait(w, timeout)

    def _ack(self, cmd, payload=b"", *accepted):
        """sendHIDAckLocked"""
        validate_ack(self._command_and_wait(cmd, payload), *(accepted or (1,)))

    def _monitor(self):
        """monitorDeviceData: the read loop owns the handle and closes it when it ends."""
        errors = 0
        try:
            while not self.stop_ev.is_set():
                try:
                    raw = self.dev.read(HID_READ_POLL_INTERVAL)
                except (OSError, ValueError) as e:
                    errors += 1
                    if errors == 1 or errors % 5 == 0:
                        log.warning("Flydigi: read failed (%d/%d): %s", errors, MAX_CONSECUTIVE_READ_ERRORS, e)
                    if errors >= MAX_CONSECUTIVE_READ_ERRORS:
                        log.warning("Flydigi: too many read errors, the device seems gone")
                        return
                    self.stop_ev.wait(HID_READ_ERROR_RETRY_DELAY)
                    continue
                errors = 0
                if not raw:
                    continue
                self.last_rx = time.monotonic()
                f = P.parse_frame(raw)
                if f is not None and f.checksum_ok:
                    self.responses.deliver(f)
                    if f.command == P.CMD_STATUS_NOTIFY:
                        st = P.decode_status(f.payload)
                        if st is None:
                            continue
                        if not st["realtime"] and self.mutex.acquire(blocking=False):
                            # a physical gear change / reconnect puts the device back in gear mode: the next target
                            # must enter realtime mode again
                            try:
                                self.realtime_mode = False
                                self.has_commanded_rpm = False
                            finally:
                                self.mutex.release()
                        self._publish(st)
        except Exception:  # noqa: BLE001
            log.exception("Flydigi: read loop")
        finally:
            explicit = self.stop_ev.is_set()
            with self.write_lock:
                dev, self.dev = self.dev, None
            if dev is not None:
                dev.close()
            self.connected = False
            self.status = None
            if not explicit:
                log.info("Flydigi: %s disconnected", self.model)
                self.on_lost()

    def close(self):
        self.stop_ev.set()
        if self.thread is not threading.current_thread():
            self.thread.join(3)

    def link_alive(self):
        return self.last_rx and time.monotonic() - self.last_rx <= HID_LINK_ALIVE_WINDOW

    # -- flash spacing --------------------------------------------------------------------------------------------
    def _await_flash_write_window(self):
        if self.last_flash_write_at:
            wait = FLASH_WRITE_SPACING - (time.monotonic() - self.last_flash_write_at)
            if wait > 0:
                time.sleep(wait)

    def _note_flash_write(self):
        self.last_flash_write_at = time.monotonic()

    # -- realtime RPM (device.go setRealtimeFanSpeedLocked and the wake path) -----------------------------------
    def set_fan_speed(self, rpm):
        rpm = int(rpm)
        if not 0 <= rpm <= P.REALTIME_RPM_MAX:
            raise ValueError(f"RPM 0..{P.REALTIME_RPM_MAX}")
        with self.mutex:
            if not self.connected:
                return False
            return self._set_realtime_fan_speed(rpm)

    def _set_realtime_fan_speed(self, rpm):
        if self.has_commanded_rpm and self.last_commanded_rpm == rpm and self.realtime_mode:
            return True
        waking_from_zero = self.has_commanded_rpm and self.last_commanded_rpm == 0 and rpm > 0
        fresh_start = not self.has_commanded_rpm
        if waking_from_zero:
            try:
                self._recover_realtime_wake(rpm)
            except Exception as e:  # noqa: BLE001
                self.realtime_mode = False
                self._note_realtime_write_result(False)
                log.warning("Flydigi: waking the fan failed: %s", e)
                return False
            self.last_commanded_rpm, self.has_commanded_rpm = rpm, True
            self.realtime_wake_gen += 1
            self._note_realtime_write_result(True)
            log.info("Flydigi: fan woken through the gear start path, target %d RPM", rpm)
            self._schedule_realtime_wake_verification(rpm, self.realtime_wake_gen)
            return True
        if not self.realtime_mode:
            try:
                self._ack(P.CMD_ENTER_REALTIME_RPM, b"", 1, 3)
            except Exception as e:  # noqa: BLE001
                self._note_realtime_write_result(False)
                log.warning("Flydigi: entering realtime mode failed: %s", e)
                return False
            self.realtime_mode = True
        try:
            self._send_realtime_target(rpm)
        except Exception as e:  # noqa: BLE001
            self.realtime_mode = False            # state unknown: a full handshake next time
            self._note_realtime_write_result(False)
            log.warning("Flydigi: setting %d RPM failed: %s", rpm, e)
            return False
        self.last_commanded_rpm, self.has_commanded_rpm = rpm, True
        self.realtime_wake_gen += 1
        self._note_realtime_write_result(True)
        if rpm == 0:
            log.debug("Flydigi: 0 RPM, realtime session kept for the next wake")   # never 0x24 after 0
        elif fresh_start:
            self._schedule_realtime_wake_verification(rpm, self.realtime_wake_gen)
        return True

    def _send_realtime_target(self, rpm):
        self._ack(P.CMD_SET_REALTIME_RPM, bytes((rpm & 0xFF, rpm >> 8)), 1)

    def _schedule_realtime_wake_verification(self, target, generation):
        def check():
            time.sleep(REALTIME_WAKE_VERIFY_DELAY)
            with self.mutex:
                if not self.connected or not self.realtime_mode or self.realtime_wake_gen != generation \
                        or self.last_commanded_rpm != target:
                    return
                st = self.status
                if st is None or st["current_rpm"] > 0:
                    return
                log.warning("Flydigi: target %d RPM but the fan is at 0 RPM — soft wake", target)
                try:
                    self._recover_realtime_wake(target)
                except Exception as e:  # noqa: BLE001
                    self._note_realtime_write_result(False)
                    log.warning("Flydigi: soft wake failed: %s", e)
                    return
                self._note_realtime_write_result(True)
        threading.Thread(target=check, daemon=True, name="flydigi-wake").start()

    def _recover_realtime_wake(self, target):
        """recoverRealtimeWakeLocked: the firmware's motor start path, then back to the exact target."""
        self._ack(P.CMD_EXIT_REALTIME_RPM, b"", 1, 2)
        self.realtime_mode = False
        self._ack(P.CMD_SET_FIXED_GEAR, bytes((P.fixed_gear_for_wake(self.status),)), 1)
        time.sleep(REALTIME_WAKE_KICK_DURATION)
        self._ack(P.CMD_ENTER_REALTIME_RPM, b"", 1, 3)
        self.realtime_mode = True
        kick = max(target, REALTIME_WAKE_KICK_RPM)
        self._send_realtime_target(kick)
        if kick != target:
            time.sleep(REALTIME_WAKE_KICK_DURATION)
            self._send_realtime_target(target)

    def _note_realtime_write_result(self, success):
        """noteRealtimeWriteResultLocked: three failures in a row -> probe with 0x25, drop the link only if dead."""
        if success:
            self.consecutive_realtime_write_errors = 0
            self.realtime_write_recovery_scheduled = False
            self.last_realtime_write_error_at = 0.0
            return
        now = time.monotonic()
        if self.last_realtime_write_error_at and now - self.last_realtime_write_error_at > REALTIME_WRITE_ERROR_DECAY:
            self.consecutive_realtime_write_errors = 0
            self.realtime_write_recovery_scheduled = False
        self.last_realtime_write_error_at = now
        self.consecutive_realtime_write_errors += 1
        if self.consecutive_realtime_write_errors < MAX_CONSECUTIVE_REALTIME_WRITE_ERRORS \
                or self.realtime_write_recovery_scheduled:
            return
        self.realtime_write_recovery_scheduled = True
        log.warning("Flydigi: %d realtime writes failed in a row — checking the link",
                    self.consecutive_realtime_write_errors)

        def recover():
            with self.mutex:
                if not (self.realtime_write_recovery_scheduled and self.connected and
                        self.consecutive_realtime_write_errors >= MAX_CONSECUTIVE_REALTIME_WRITE_ERRORS):
                    return
                try:
                    f = self._command_and_wait(P.CMD_QUERY_WORK_MODE)
                    probe_ok = bool(f.payload)
                except Exception:  # noqa: BLE001
                    probe_ok = False
                if not realtime_recovery_needs_disconnect(probe_ok, self.link_alive()):
                    self._note_realtime_write_result(True)
                    self.realtime_mode = False
                    self.has_commanded_rpm = False
                    log.warning("Flydigi: control failed but the device still answers — keeping the link "
                                "(probe ok: %s)", probe_ok)
                    return
            log.warning("Flydigi: no answer and no recent report — reconnecting")
            self.stop_ev.set()
            self.on_lost()
        threading.Thread(target=recover, daemon=True, name="flydigi-recover").start()

    def enter_auto_mode(self):
        """EnterAutoMode: 0x23 only."""
        with self.mutex:
            self._ack(P.CMD_ENTER_REALTIME_RPM, b"", 1, 3)
            self.realtime_mode = True

    # -- gears --------------------------------------------------------------------------------------------------
    def set_fixed_gear(self, gear):
        """SetManualGear with a bare 0x08 (the gear's RPM stays what the device has stored)."""
        gear = int(gear)
        if not 1 <= gear <= 4:
            raise ValueError("gear 1..4")
        with self.mutex:
            if self.controller_tier is not None and gear > P.max_gear_for_fixed_gear_command(self.controller_tier):
                raise DeviceError(f"capability tier {self.controller_tier} selects at most gear "
                                  f"{P.max_gear_for_fixed_gear_command(self.controller_tier)}")
            self._ack(P.CMD_SET_FIXED_GEAR, bytes((gear,)), 1)
            self._reset_realtime_control_state()
        return True

    def set_manual_gear_rpm(self, gear, rpm):
        """SetManualGearRPM: write the gear slot's RPM by 0x26 (or only select it by 0x08 when the slot already holds
        that RPM — no flash write), then wait for the 0xEF status to confirm the gear."""
        gear, rpm = int(gear), int(rpm)
        idx = gear - 1
        if not 0 <= idx < GEAR_RPM_SLOT_COUNT:
            raise ValueError("gear 1..4")
        if not P.MANUAL_GEAR_MIN_RPM <= rpm <= P.MANUAL_GEAR_MAX_RPM:
            raise ValueError(f"gear RPM {P.MANUAL_GEAR_MIN_RPM}..{P.MANUAL_GEAR_MAX_RPM}")
        with self.mutex:
            if self.controller_tier is not None and idx + 1 > P.max_gear_for_gear_rpm_command(self.controller_tier):
                raise DeviceError(f"capability tier {self.controller_tier} selects at most gear "
                                  f"{P.max_gear_for_gear_rpm_command(self.controller_tier)}")
            if self.device_gear_rpm[idx] == rpm:
                cmd, payload, flash = P.CMD_SET_FIXED_GEAR, bytes((idx + 1,)), False
            else:
                cmd, payload, flash = P.CMD_SET_GEAR_RPM, bytes((idx, rpm & 0xFF, rpm >> 8)), True
                self._await_flash_write_window()
            status_w = self.responses.register(P.CMD_STATUS_NOTIFY)      # status comes before the ACK
            try:
                ack = self._command_and_wait(cmd, payload)
                validate_ack(ack, 1)
            except Exception:
                self.responses.cancel(status_w)
                if flash:
                    self.device_gear_rpm[idx] = None
                    self._note_flash_write()
                raise
            if flash:
                self._note_flash_write()
                self.device_gear_rpm[idx] = rpm
            actual = self._wait_for_selected_gear(status_w, gear, GEAR_SELECTION_VERIFY_TIMEOUT)
            if actual != gear:
                raise DeviceError(f"the gear RPM was written but the device is still in gear {actual or '?'}")
            self._reset_realtime_control_state()
        return True

    def _wait_for_selected_gear(self, first, expected, timeout):
        deadline = time.monotonic() + timeout
        w, last = first, 0
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return last
            try:
                f = self.responses.wait(w, left)
            except TimeoutError:
                return last
            st = P.decode_status(f.payload)
            if st:
                last = st["selected_gear"]
                if not st["realtime"] and last == expected:
                    return last
            w = self.responses.register(P.CMD_STATUS_NOTIFY)

    # -- flash settings -------------------------------------------------------------------------------------------
    def set_gear_light(self, on):
        with self.mutex:
            if self.gear_light is not None and self.gear_light == bool(on):
                return True                           # 0x48 rewrites a flash page and does not compare: skip
            self._await_flash_write_window()
            try:
                self._ack(P.CMD_GEAR_LIGHT, bytes((1 if on else 0,)), 1)
            except Exception:
                self.gear_light = None
                raise
            finally:
                self._note_flash_write()
            self.gear_light = bool(on)
        return True

    def set_power_on_start(self, on):
        with self.mutex:
            self._await_flash_write_window()
            try:
                self._ack(P.CMD_SET_POWER_ON_START, bytes((1 if on else 2,)), 1)
            finally:
                self._note_flash_write()
        return True

    def set_smart_start_stop(self, mode):
        code = {"off": 0, "immediate": 1, "delayed": 2}.get(mode)
        if code is None:
            raise ValueError("smart start/stop: off | immediate | delayed")
        with self.mutex:
            self._await_flash_write_window()
            try:
                self._ack(P.CMD_SET_SMART_START_STOP, bytes((code,)), 1)
            finally:
                self._note_flash_write()
        return True

    # -- queries (query.go QueryDeviceSettings) ---------------------------------------------------------------------
    def query_settings(self):
        out, errors = {"model": self.model}, []
        detailed = self.pid in (hidio.PID_BS2, hidio.PID_BS2PRO, hidio.PID_BS3, hidio.PID_BS3PRO)
        for cmd in HID_DETAILED_QUERY_COMMANDS if detailed else BASIC_DEVICE_SETTINGS_QUERY_COMMANDS:
            attempts = FIRMWARE_VERSION_QUERY_ATTEMPTS if cmd == P.CMD_QUERY_FIRMWARE_VERSION else 1
            for a in range(attempts):
                try:
                    with self.mutex:
                        f = self._command_and_wait(cmd)
                    d = P.decode_frame(f)
                    if cmd == P.CMD_QUERY_FIRMWARE_VERSION and not d.get("firmware"):
                        raise DeviceError("incomplete firmware version")
                    out.update(d)
                    break
                except Exception as e:  # noqa: BLE001
                    if a == attempts - 1:
                        errors.append(f"0x{cmd:02X}: {e}")
                    else:
                        time.sleep(FIRMWARE_VERSION_RETRY_DELAY)
        table = out.get("gear_table")
        if table:                                        # seeds the cache: 0x08 instead of a flash write later
            with self.mutex:
                for i, v in enumerate(table[:GEAR_RPM_SLOT_COUNT]):
                    if v > 0:
                        self.device_gear_rpm[i] = v
        if out.get("capability_tier") is not None:
            self.controller_tier = out["capability_tier"]
            out["max_selectable_gear"] = P.max_gear_for_gear_rpm_command(self.controller_tier)
        if errors:
            out["errors"] = errors
        return out


# =================================================================================================================
class BS1Cooler(BaseCooler):
    """BS1: the reduced command set, written without waiting for ACKs (ble.go). Transport: USB HID or Bluetooth LE."""
    model = "BS1"

    def __init__(self, on_update=None, on_lost=None):
        super().__init__(on_update, on_lost)
        self.control = threading.Lock()                 # controlMutex
        self.realtime_mode = False
        self.realtime_stopped = False
        self.stop_ev = threading.Event()

    # transport hooks
    def _write(self, frame):
        raise NotImplementedError

    def _on_frame(self, raw, ascii_gear):
        f = P.parse_frame(raw)
        if f is None or not f.checksum_ok or f.command != P.CMD_STATUS_NOTIFY:
            return
        st = P.decode_status(f.payload)
        if st is None:
            return
        if ascii_gear:          # USB HID: 0x30 + 2 * (gear - 1) (bs1HIDGearName), no max gear
            g = st["gear_byte"]
            st["selected_gear"] = (g - 0x30) // 2 + 1 if 0x30 <= g <= 0x36 and g % 2 == 0 else 0
            st["selected"] = P.gear_code_name(st["selected_gear"])
            st["max_gear"] = ""
        self._publish(st)

    # ble.go SetFanSpeed
    def set_fan_speed(self, rpm):
        rpm = int(rpm)
        if not 0 <= rpm <= P.REALTIME_RPM_MAX:
            raise ValueError(f"RPM 0..{P.REALTIME_RPM_MAX}")
        with self.control:
            waking = self.realtime_stopped and rpm > 0
            if not self.realtime_mode or waking:
                self._write(P.build_frame(P.CMD_ENTER_REALTIME_RPM))
                time.sleep(BS1_MODE_SWITCH_DELAY)
                self.realtime_mode = True
            if waking:
                try:
                    self._write(P.build_frame(P.CMD_SET_REALTIME_RPM, *_le16(max(rpm, REALTIME_WAKE_KICK_RPM))))
                except Exception:
                    self.realtime_mode = False
                    raise
                time.sleep(REALTIME_WAKE_KICK_DURATION)
            try:
                self._write(P.build_frame(P.CMD_SET_REALTIME_RPM, *_le16(rpm)))
            except Exception:
                self.realtime_mode = False
                raise
            self.realtime_stopped = rpm == 0
        return True

    def enter_auto_mode(self):
        with self.control:
            self._write(P.build_frame(P.CMD_ENTER_REALTIME_RPM))
            self.realtime_mode = True

    def set_fixed_gear(self, gear):
        gear = int(gear)
        if not 1 <= gear <= 4:
            raise ValueError("gear 1..4")
        with self.control:
            self._write(P.build_frame(P.CMD_SET_FIXED_GEAR, gear))
            self.realtime_mode = False                     # the keep-alive must stop sending 0x23
            self.realtime_stopped = False
        return True

    def set_manual_gear_rpm(self, gear, rpm):              # BS1 has no gear RPM slots: the fixed gear (THRM too)
        return self.set_fixed_gear(gear)

    def set_power_on_start(self, on):
        self._write(P.build_frame(P.CMD_SET_POWER_ON_START, 1 if on else 2))
        return True

    def set_gear_light(self, on):
        raise DeviceError("BS1 has no gear light setting")

    def set_smart_start_stop(self, mode):
        raise DeviceError("BS1 has no smart start/stop setting")

    def query_settings(self):
        return {"model": "BS1", "firmware_read": "unsupported"}

    def keepalive_command(self, index):
        """bs1KeepAliveCommand: 0x23 / 0x45 alternately in realtime mode, only 0x45 in gear mode."""
        if self.realtime_mode and index % 2 == 0:
            return P.build_frame(P.CMD_ENTER_REALTIME_RPM)
        return P.build_frame(P.CMD_RGB_STATUS)


def _le16(v):
    return v & 0xFF, (v >> 8) & 0xFF


class BS1Hid(BS1Cooler):
    """bs1_hid.go: 32-byte reports, Report ID 0x01, checksum moved to the last byte; no keep-alive."""
    kind = "bs1-usb"

    def __init__(self, dev_info, on_update=None, on_lost=None):
        super().__init__(on_update, on_lost)
        self.transport = "usb"
        self.dev = hidio.open_device(dev_info)
        self.io = threading.Lock()
        self.first = threading.Event()
        self.info = {"model": "BS1", "product_id": f"0x{hidio.BS1_PID:04X}", "path": dev_info["path"],
                     "name": dev_info.get("name") or BS1_DEVICE_NAME}
        self.thread = threading.Thread(target=self._run, daemon=True, name="flydigi-bs1-hid")
        self.thread.start()
        if not self.first.wait(BS1_HID_PROBE_TIMEOUT):
            self.close()
            raise DeviceError("BS1 is in the system but does not answer — unplug the USB cable and plug it in again")
        self.connected = True

    def _write(self, frame):
        report = hidio.build_bs1_hid_report(frame)
        if report is None:
            raise DeviceError(f"frame of {len(frame)} bytes does not fit the BS1 report")
        with self.io:
            if self.dev is None:
                raise DeviceError("BS1 HID handle is closed")
            self.dev.write(report)

    def _run(self):
        last = time.monotonic()
        err = None
        try:
            while not self.stop_ev.is_set():
                raw = self.dev.read(HID_READ_POLL_INTERVAL)
                if not raw:
                    if time.monotonic() - last >= BS1_HID_IDLE_TIMEOUT:
                        err = "no data for 20 s"
                        break
                    continue
                last = time.monotonic()
                self.first.set()
                self._on_frame(raw, ascii_gear=True)
        except (OSError, ValueError) as e:
            err = str(e)
        finally:
            with self.io:
                dev, self.dev = self.dev, None
            if dev is not None:
                dev.close()
            was = self.connected
            self.connected = False
            self.status = None
            if err and was:
                log.info("Flydigi BS1 (USB): %s", err)
                self.on_lost()

    def close(self):
        self.stop_ev.set()
        if self.thread is not threading.current_thread():
            self.thread.join(3)


class BS1Ble(BS1Cooler):
    """ble.go: service 0xFFF0, write 0xFFF2 (write without response, then with), notify 0xFFF1, keep-alive 3 s."""
    kind = "bs1-ble"

    def __init__(self, on_update=None, on_lost=None):
        super().__init__(on_update, on_lost)
        import bleak  # noqa: F401  (ImportError: no Bluetooth LE here)
        self.bleak = bleak
        self.transport = "ble"
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.address = None
        threading.Thread(target=self.loop.run_forever, daemon=True, name="flydigi-ble").start()

    def _call(self, coro, timeout=30):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    @staticmethod
    def match(found, known_address, elapsed):
        """bs1ScanMatcher: a name with "BS1" at once; a nameless 0xFFF0 advert when it is the known address or after
        3 s without a named one; any other name is not a BS1."""
        cand = None
        for address, name, has_service in found:
            if "BS1" in (name or ""):
                return address, name
            if name or not has_service:
                continue
            cand = cand or address
            if address == known_address:
                return address, BS1_DEVICE_NAME
        if cand and elapsed >= BS1_SERVICE_FALLBACK_DELAY:
            return cand, BS1_DEVICE_NAME
        return None

    async def _scan(self, known):
        seen = {}
        start = time.monotonic()

        def cb(dev, adv):
            name = dev.name or getattr(adv, "local_name", None) or ""
            has = BS1_SERVICE in [u.lower() for u in (getattr(adv, "service_uuids", None) or [])]
            if "BS1" in name or "Flydigi" in name or (not name and has):
                seen[dev.address] = (dev.address, name, has)
        sc = self.bleak.BleakScanner(detection_callback=cb)
        await sc.start()
        try:
            while time.monotonic() - start < DEFAULT_BLE_SCAN_TIMEOUT:
                hit = self.match(seen.values(), known, time.monotonic() - start)
                if hit:
                    return hit
                await asyncio.sleep(0.25)
        finally:
            await sc.stop()
        return self.match(seen.values(), known, BS1_SERVICE_FALLBACK_DELAY)     # acceptFallback

    async def _connect(self, known):
        hit = await self._scan(known)
        if not hit:
            raise LookupError("no BS1 found by Bluetooth LE")
        address, name = hit
        client = self.bleak.BleakClient(address, disconnected_callback=lambda _c: self._lost(), timeout=15.0)
        await asyncio.wait_for(client.connect(), 20)
        try:
            await client.start_notify(BS1_NOTIFY_CHAR, lambda _s, data: self._on_frame(bytes(data), ascii_gear=False))
        except BaseException:
            await client.disconnect()
            raise
        self.client, self.address = client, address
        self.info = {"model": "BS1", "name": name, "address": address}
        return address

    def connect(self, known=None):
        self._call(self._connect(known), 40)
        self.connected = True
        self.realtime_mode = False                     # a new connection starts in gear mode
        threading.Thread(target=self._heartbeat, daemon=True, name="flydigi-bs1-keepalive").start()
        return self.address

    def _lost(self):
        if self.connected and not self.stop_ev.is_set():
            self.connected = False
            self.status = None
            log.info("Flydigi BS1 (Bluetooth LE) disconnected")
            self.on_lost()

    def _write(self, frame):
        if not self.connected or self.client is None:
            raise DeviceError("BS1 is not connected")

        async def w():
            try:
                await asyncio.wait_for(self.client.write_gatt_char(BS1_WRITE_CHAR, bytes(frame), response=False), 5)
            except Exception:  # noqa: BLE001
                await asyncio.wait_for(self.client.write_gatt_char(BS1_WRITE_CHAR, bytes(frame), response=True), 5)
        self._call(w(), 12)

    def _heartbeat(self):
        i = 0
        while not self.stop_ev.wait(BS1_KEEPALIVE_INTERVAL):
            if not self.connected:
                return
            with self.control:
                cmd = self.keepalive_command(i)
                i += 1
                try:
                    self._write(cmd)
                except Exception as e:  # noqa: BLE001
                    log.warning("Flydigi BS1: keep-alive failed: %s", e)
                    self._lost()
                    return

    def close(self):
        self.stop_ev.set()
        self.connected = False
        c, self.client = self.client, None
        if c is not None:
            try:
                self._call(c.disconnect(), 10)
            except Exception:  # noqa: BLE001
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)


# -- connection (device.go connect) -----------------------------------------------------------------------------------
def pick_hid_candidates(found, priority=hidio.SUPPORTED_PIDS):
    """pickHIDCandidates: for each product ID in priority order, its first interface in enumeration order.
    On Windows an interface without an output report cannot take commands and is passed over."""
    out = []
    for pid in priority:
        for c in found:
            if c["pid"] == pid and c.get("output_len") != 0:
                out.append(c)
                break
    return out


def find_bs1_hid():
    """enumerateBS1HID: vendor collections only (usage page >= 0xFF00), the one named "Flydigi BS1" first."""
    named = fallback = None
    for d in hidio.enumerate_hid(hidio.BS1_VID, (hidio.BS1_PID,)):
        up = d.get("usage_page")
        if up is not None and up < hidio.BS1_VENDOR_USAGE_PAGE_MIN:
            continue
        if BS1_DEVICE_NAME in (d.get("name") or ""):
            named = named or d
        else:
            fallback = fallback or d
    return named or fallback


IDLE_BLE_SCAN_COOLDOWN = 15 * 60.0


def should_skip_ble_fallback(prefer_last, last_type, since_last_scan):
    """shouldSkipBLEFallback: after an HID cooler wait for the system to list it again; never connected this
    session -> at most one BLE scan per 15 min; BS1 in use -> scan every time."""
    if not prefer_last:
        return False
    if last_type == "hid":
        return True
    if last_type == "ble":
        return False
    return since_last_scan is not None and 0 <= since_last_scan < IDLE_BLE_SCAN_COOLDOWN
