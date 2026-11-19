"""Flydigi BS cooler (1.8.2.7): the THRM protocol port, the control sequences, the curve and the automation.

python3 -m unittest tests.test_flydigi
Reference frames are the captures in THRM scripts/hid_data.md (MIT, Copyright (c) 2025 Tianli).
"""
import collections
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uwccd.flydigi import cooler as C  # noqa: E402
from uwccd.flydigi import device as D  # noqa: E402
from uwccd.flydigi import hidio as H  # noqa: E402
from uwccd.flydigi import proto as P  # noqa: E402


def hx(s):
    return bytes.fromhex(s.replace(" ", ""))


class Protocol(unittest.TestCase):
    def test_frames_match_thrm_captures(self):
        self.assertEqual(P.build_frame(0x48, 0), hx("5aa548 03 00 4b"))          # gear light off
        self.assertEqual(P.build_frame(0x48, 1), hx("5aa548 03 01 4c"))          # gear light on
        self.assertEqual(P.build_frame(0x26, 0, 0x14, 0x05), hx("5aa526 05 00 14 05 44"))   # gear 1 low, 1300
        self.assertEqual(P.build_frame(0x26, 3, 0xA0, 0x0F), hx("5aa526 05 03 a0 0f dd"))   # gear 4 high, 4000
        self.assertEqual(P.build_frame(0x0C, 1), hx("5aa50c 03 01 10"))          # power-on start on
        self.assertEqual(P.build_frame(0x0C, 2), hx("5aa50c 03 02 11"))          # … off
        self.assertEqual(P.build_frame(0x0D, 1), hx("5aa50d 03 01 11"))          # smart start/stop immediate
        self.assertEqual(P.build_frame(0x23), hx("5aa523 02 25"))                # enter realtime
        self.assertEqual(P.build_frame(0x21, 0x8D, 0x0F), hx("5aa521 04 8d 0f c1"))   # 3981 RPM
        r = P.build_report(P.build_frame(0x23), H.HID_CONTROL_REPORT_LEN)
        self.assertEqual((len(r), r[:6]), (25, hx("02 5aa523 02 25")))

    def test_status_frame(self):
        raw = hx("01 5A A5 EF 0B 68 04 05 80 0C 14 05 C7 00 D7 00 00 00 00 00 00 00 00 00 00")
        f = P.parse_frame(raw)
        self.assertEqual((f.offset, f.report_id, f.command), (1, 1, 0xEF))
        st = P.decode_status(f.payload)
        self.assertEqual((st["max_gear"], st["selected"], st["selected_gear"]), ("extreme", "quiet", 1))
        self.assertEqual((st["realtime"], st["smart_start_stop"]), (False, "immediate"))
        self.assertEqual((st["current_rpm"], st["target_rpm"]), (3200, 1300))
        self.assertEqual(f.checksum_ok, (sum(raw[3:14]) & 0xFF) == raw[14])
        bad = bytearray(P.build_frame(0x25, 5)); bad[-1] ^= 1
        self.assertFalse(P.parse_frame(bad).checksum_ok)
        self.assertIsNone(P.parse_frame(b"\x00\x01\x02"))

    def test_outbound_guards(self):
        for frame in (P.build_frame(0x47, 25, *[0] * 10), P.build_frame(0x26, 4, 0, 0), P.build_frame(0x08, 5),
                      P.build_frame(0x08, 0), P.build_frame(0x08)):
            with self.assertRaises(ValueError):
                P.validate_outbound_frame(frame)
        P.validate_outbound_frame(P.build_frame(0x47, 24, *[0] * 10))
        P.validate_outbound_frame(P.build_frame(0x08, 4))

    def test_report_layouts(self):
        f = P.build_frame(0x08, 2)                                   # 5A A5 08 03 02 0D
        r = H.build_bs1_hid_report(f)
        self.assertEqual(len(r), 32)
        self.assertEqual(r[:7], hx("01 5aa5 08 03 02 00"))           # checksum slot cleared…
        self.assertEqual(r[31], 0x0D)                                # …and moved to the last byte
        u = H.build_hid_report(f, unnumbered_usb=True)
        self.assertEqual((len(u), u[:7]), (32, hx("00 5aa5 08 03 02 0d")))
        self.assertFalse(H.unnumbered_usb({"bus": H.BUS_BLUETOOTH, "descriptor": H.FLYDIGI_USB_REPORT_DESCRIPTOR}))
        self.assertEqual(H.unnumbered_usb({"bus": H.BUS_USB, "descriptor": H.FLYDIGI_USB_REPORT_DESCRIPTOR}),
                         not H.IS_WIN)
        self.assertEqual(H._usage_page(H.FLYDIGI_USB_REPORT_DESCRIPTOR), 0xFFA0)

    def test_tiers_and_candidates(self):
        self.assertEqual([P.max_gear_for_fixed_gear_command(t) for t in (1, 2, 3)], [3, 4, 4])
        self.assertEqual([P.max_gear_for_gear_rpm_command(t) for t in (1, 2, 3)], [2, 3, 4])
        found = [{"pid": 0x1001, "path": "a"}, {"pid": 0x1004, "path": "b"}, {"pid": 0x1001, "path": "c"},
                 {"pid": 0x1002, "path": "d", "output_len": 0}, {"pid": 0x1002, "path": "e"}]
        self.assertEqual([c["path"] for c in D.pick_hid_candidates(found)], ["e", "b", "a"])
        self.assertTrue(D.should_skip_ble_fallback(True, "hid", None))
        self.assertFalse(D.should_skip_ble_fallback(True, "ble", 1))
        self.assertTrue(D.should_skip_ble_fallback(True, None, 60))
        self.assertFalse(D.should_skip_ble_fallback(True, None, None))
        self.assertFalse(D.should_skip_ble_fallback(True, None, 16 * 60))

    def test_ble_matcher(self):
        m = D.BS1Ble.match
        self.assertEqual(m([("A", "Flydigi BS1", False)], None, 0), ("A", "Flydigi BS1"))
        self.assertIsNone(m([("B", "", True)], None, 1))                       # nameless: wait for a named one
        self.assertEqual(m([("B", "", True)], "B", 0), ("B", D.BS1_DEVICE_NAME))  # … unless it is the known one
        self.assertEqual(m([("B", "", True)], None, 3.1), ("B", D.BS1_DEVICE_NAME))
        self.assertIsNone(m([("C", "Mouse", True)], None, 5))                   # another name: not a BS1


class FakeFirmware:
    """Answers every command like the BS2 Pro firmware does: an ACK (status 1, or what `acks` says) and, for gear
    commands, a 0xEF status before the ACK."""

    def __init__(self, tier=3):
        self.sent = []
        self.q = collections.deque()
        self.cv = threading.Condition()
        self.acks = {}
        self.gear, self.realtime, self.rpm = 2, False, 0
        self.tier = tier
        self.answer = True

    def status(self):
        g = 0x60 | {1: 0x8, 2: 0xA, 3: 0xC, 4: 0xE}[self.gear]
        p = bytes((g, 0x02 | (1 if self.realtime else 0), 0)) + self.rpm.to_bytes(2, "little") + bytes(2)
        return P.build_report(P.build_frame(0xEF, *p), 25)

    def push(self, rep):
        with self.cv:
            self.q.append(rep)
            self.cv.notify()

    # device interface
    def write(self, report):
        f = P.parse_frame(report)
        self.sent.append((f.command, bytes(f.payload)))
        if not self.answer:
            return
        c = f.command
        if c == 0x23:
            self.realtime = True
        elif c == 0x24:
            self.realtime = False
        elif c == 0x08:
            self.gear, self.realtime = f.payload[0], False
        elif c == 0x26:
            if f.payload[0] + 1 <= P.max_gear_for_gear_rpm_command(self.tier):
                self.gear = f.payload[0] + 1
            self.realtime = False
        if c in (0x08, 0x26):
            self.push(self.status())
        if c == 0x25:
            body = (5 if self.realtime else self.gear,)
        elif c == 0x07:
            body = (self.tier,)
        elif c == 0x27:
            body = b"".join(v.to_bytes(2, "little") for v in (1700, 2400, 3000, 4000))
        elif c == 0x01:
            body = (0, 0, 3, 5)
        else:
            body = (self.acks.get(c, 1),)
        self.push(P.build_report(P.build_frame(c, *body), 25))

    def read(self, timeout):
        with self.cv:
            if not self.q:
                self.cv.wait(timeout)
            return self.q.popleft() if self.q else None

    def close(self):
        pass


class Control(unittest.TestCase):
    def setUp(self):
        self.saved = (D.REALTIME_WAKE_KICK_DURATION, D.REALTIME_WAKE_VERIFY_DELAY, D.FLASH_WRITE_SPACING,
                      D.DEVICE_RESPONSE_TIMEOUT)
        D.REALTIME_WAKE_KICK_DURATION, D.REALTIME_WAKE_VERIFY_DELAY = 0.01, 0.2
        self.fw = FakeFirmware()
        orig = H.open_device
        H.open_device = lambda info: self.fw
        try:
            self.dev = D.HidCooler({"pid": 0x1002, "path": "fake", "bus": H.BUS_BLUETOOTH})
        finally:
            H.open_device = orig

    def tearDown(self):
        self.dev.close()
        (D.REALTIME_WAKE_KICK_DURATION, D.REALTIME_WAKE_VERIFY_DELAY, D.FLASH_WRITE_SPACING,
         D.DEVICE_RESPONSE_TIMEOUT) = self.saved

    def cmds(self):
        out = [c for c, _ in self.fw.sent]
        self.fw.sent.clear()
        return out

    def test_realtime_sequence(self):
        d = self.dev
        self.fw.push(self.fw.status())                         # the cooler reports gear 2
        time.sleep(0.1)
        self.assertTrue(d.set_fan_speed(2000))
        self.assertEqual(self.fw.sent, [(0x23, b""), (0x21, bytes((0xD0, 0x07)))])
        self.fw.sent.clear()
        d.set_fan_speed(2000)                                  # the same target: nothing is sent
        self.assertEqual(self.cmds(), [])
        d.set_fan_speed(2500)                                  # realtime already on: only the target
        self.assertEqual(self.cmds(), [0x21])
        d.set_fan_speed(0)                                     # 0 RPM: no 0x24 afterwards
        self.assertEqual(self.cmds(), [0x21])
        d.set_fan_speed(1200)                                  # waking from 0: the firmware's start path
        self.assertEqual(self.fw.sent, [(0x24, b""), (0x08, bytes((2,))), (0x23, b""),
                                        (0x21, (1700).to_bytes(2, "little")), (0x21, (1200).to_bytes(2, "little"))])
        self.fw.sent.clear()
        time.sleep(0.4)                                        # 3 s check (shortened): fan still at 0 -> soft wake
        self.assertEqual(self.cmds()[:3], [0x24, 0x08, 0x23])

    def test_enter_realtime_already_on_is_accepted(self):
        self.fw.acks[0x23] = 3                                 # "already in realtime mode"
        self.assertTrue(self.dev.set_fan_speed(1500))
        self.fw.acks[0x21] = 0                                 # refused: the mode handshake is redone next time
        self.assertFalse(self.dev.set_fan_speed(1600))
        self.assertFalse(self.dev.realtime_mode)

    def test_gear_status_resets_realtime(self):
        d = self.dev
        d.set_fan_speed(2000)
        self.fw.realtime = False
        self.fw.push(self.fw.status())                          # physical gear button: back in gear mode
        time.sleep(0.2)
        self.assertFalse(d.realtime_mode)
        self.cmds()
        d.set_fan_speed(2000)                                  # the same RPM is sent again, with 0x23 first
        self.assertEqual(self.cmds(), [0x23, 0x21])

    def test_gear_rpm_flash_cache_and_tier(self):
        d = self.dev
        d.set_manual_gear_rpm(3, 3300)
        self.assertEqual(self.fw.sent, [(0x26, bytes((2,)) + (3300).to_bytes(2, "little"))])
        self.fw.sent.clear()
        d.set_manual_gear_rpm(3, 3300)                         # the slot holds it: 0x08, no flash write
        self.assertEqual(self.fw.sent, [(0x08, bytes((3,)))])
        d.controller_tier = 1
        with self.assertRaises(D.DeviceError):
            d.set_manual_gear_rpm(3, 2800)                     # tier 1: 0x26 selects only gears 1..2
        with self.assertRaises(D.DeviceError):
            d.set_fixed_gear(4)                                # tier 1: 0x08 up to gear 3
        with self.assertRaises(ValueError):
            d.set_manual_gear_rpm(2, 700)

    def test_gear_not_confirmed(self):
        self.fw.tier = 2                                       # the firmware ACKs but stays in its gear
        with self.assertRaises(D.DeviceError):
            self.dev.set_manual_gear_rpm(4, 3700)

    def test_flash_settings(self):
        d = self.dev
        D.FLASH_WRITE_SPACING = 0.15
        t0 = time.monotonic()
        d.set_gear_light(True)
        d.set_gear_light(True)                                 # known value: skipped
        d.set_power_on_start(False)
        d.set_smart_start_stop("delayed")
        self.assertGreaterEqual(time.monotonic() - t0, 0.29)   # 150 ms between flash writes
        self.assertEqual(self.fw.sent, [(0x48, b"\x01"), (0x0C, b"\x02"), (0x0D, b"\x02")])

    def test_query_settings(self):
        s = self.dev.query_settings()
        self.assertEqual((s["firmware"], s["capability_tier"], s["gear_table"]), ("0.0.3.5", 3, [1700, 2400, 3000, 4000]))
        self.assertEqual(self.dev.device_gear_rpm, [1700, 2400, 3000, 4000])
        self.cmds()
        self.dev.set_manual_gear_rpm(2, 2400)                  # seeded by 0x27: no flash write
        self.assertEqual(self.cmds(), [0x08])

    def test_write_errors_probe_before_reconnect(self):
        d = self.dev
        lost = []
        d.on_lost = lambda: lost.append(1)
        d.set_fan_speed(2000)
        self.fw.acks[0x21] = 0
        for r in (2100, 2200, 2300):
            d.set_fan_speed(r)
        time.sleep(0.3)
        self.assertIn(0x25, [c for c, _ in self.fw.sent])        # probed with the read-only 0x25
        self.assertEqual(lost, [])                               # it answered: the link stays
        self.assertFalse(d.has_commanded_rpm)


class Curve(unittest.TestCase):
    def test_interpolate_ramp_hysteresis(self):
        curve = [(40, 1000), (60, 2000), (80, 4000)]
        self.assertEqual([C.interpolate(curve, t) for t in (20, 40, 50, 70, 90)], [1000, 1000, 1500, 3000, 4000])
        self.assertEqual(C.apply_ramp_limit(3000, 1000, 220, 160), 1220)
        self.assertEqual(C.apply_ramp_limit(1000, 3000, 220, 160), 2840)
        fc = C.FlydigiCooler.__new__(C.FlydigiCooler)
        fc.cfg = {**C.DEFAULTS, "curve": [list(p) for p in curve]}
        fc.ctl_temp = None
        self.assertEqual(fc.curve_target(60), 2000)
        self.assertEqual(fc.curve_target(59), 2000)             # fell by 1 °C < hysteresis 2: held
        self.assertEqual(fc.curve_target(58), 1900)
        self.assertEqual(fc.curve_target(70), 3000)             # rising: at once
        with self.assertRaises(ValueError):
            C.check_curve([[40, 1000]])
        self.assertEqual(C.check_curve([[60, 1500], [40, 2000]]), [[40.0, 2000], [60.0, 2000]])


class Automation(unittest.TestCase):
    def test_rule_switches_flydigi_mode_and_back(self):
        from uwccd import automation as A
        rules = A.check_load_rules([{"name": "hot", "conditions": [{"metric": "cpu_temp", "op": ">", "value": 80}],
                                     "hold": 0, "fd_mode": "rpm", "fd_rpm": 4200, "back": "while"},
                                    {"name": "cooler", "conditions": [{"metric": "fd_connected", "value": 1},
                                                                      {"metric": "fd_rpm", "op": ">", "value": 3000}],
                                     "hold": 0, "mode": 1}])
        self.assertEqual((rules[0]["fd_mode"], rules[0]["fd_rpm"]), ("rpm", 4200))
        self.assertEqual(rules[1]["conditions"][0]["op"], "=")
        with self.assertRaises(ValueError):
            A.check_load_rules([{"conditions": [{"metric": "cpu_temp", "op": ">", "value": 1}], "fd_mode": "turbo"}])

        class Fd:
            def __init__(fd):
                fd.cfg = {"mode": "curve", "rpm": 2000, "gear": 2, "level": "mid"}

            def configure(fd, b):
                fd.cfg.update(b)

            def snapshot(fd):
                return dict(fd.cfg)

            def restore(fd, s):
                fd.cfg.update(s)

            def status(fd):
                return {"connected": True, "current_rpm": 4100 if fd.cfg["mode"] == "rpm" else 1500}

        class Store(dict):
            def set(s, k, v):
                s[k] = v

        class Power:
            option = {"OperatingMode": 0, "FanBoostEnable": 0}
            MODES = (0, 1, 2, 3)

            def status(p):
                return {}

        class Svc:
            fan_control, alt, liquid = True, None, None

            def __init__(sv):
                sv.settings_store, sv.power, sv.flydigi = Store(load_rules=[rules[0]]), Power(), Fd()

            def emit(sv, *a):
                pass

        svc = Svc()
        lr = A.LoadRules(svc)
        m = {"monitoring": "full", "cpu": {"temp": 90, "power_w": 10, "usage": 5}, "gpu": {}}
        lr.tick(m, now=1)
        self.assertEqual(svc.flydigi.cfg["mode"], "rpm")
        self.assertEqual(svc.flydigi.cfg["rpm"], 4200)
        self.assertEqual(lr.log[-1]["fd_mode"], "rpm")
        self.assertEqual(lr._state(m)["fd_rpm"], 4100)
        lr.tick({**m, "cpu": {"temp": 50, "power_w": 10, "usage": 5}}, now=3)
        self.assertEqual((svc.flydigi.cfg["mode"], svc.flydigi.cfg["rpm"]), ("curve", 2000))
        self.assertEqual(lr.log[-1]["what"], "back")


if __name__ == "__main__":
    unittest.main()
