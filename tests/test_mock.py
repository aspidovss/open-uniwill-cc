"""End-to-end tests against the simulated EC:  python3 -m unittest discover -s tests"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = "t-" + os.urandom(6).hex()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class MockService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="uwcc-test-")
        cls.port = free_port()
        cls.ecfile = os.path.join(cls.tmp, "ec.json")
        env = dict(os.environ, UWCC_DATA=os.path.join(cls.tmp, "data"), UWCC_RUN=os.path.join(cls.tmp, "run"),
                   PYTHONPATH=ROOT)
        code = ("import uwccd.ec as e; e.MockEC.__init__.__defaults__ = (%r,); "
                "import runpy; runpy.run_module('uwccd', run_name='__main__')" % cls.ecfile)
        cls.proc = subprocess.Popen([sys.executable, "-c", code, "--mock", "--port", str(cls.port), "--token", TOKEN],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                cls.get("state")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)

    @classmethod
    def get(cls, path):
        r = urllib.request.Request(f"http://127.0.0.1:{cls.port}/api/{path}", headers={"X-UWCC-Token": TOKEN})
        return json.load(urllib.request.urlopen(r, timeout=10))

    def post(self, path, body, method="POST", token=TOKEN):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/{path}", data=json.dumps(body).encode(),
                                   method=method, headers={"X-UWCC-Token": token} if token else {})
        try:
            return 200, json.load(urllib.request.urlopen(r, timeout=20))
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def ec(self, addr):
        return self.get(f"ec/{addr:x}")["value"]

    # -- tests ------------------------------------------------------------------
    def test_auth_required(self):
        code, _ = self.post("mode", {"mode": 0}, token=None)
        self.assertEqual(code, 401)

    def test_modes_and_boost(self):
        self.assertEqual(self.post("mode", {"mode": 0})[0], 200)
        self.assertEqual(self.ec(0x751), 0xA0)
        self.post("fanboost", {"on": True})
        self.assertEqual(self.ec(0x751), 0xE0)
        self.post("mode", {"mode": 2})
        self.assertEqual(self.ec(0x751), 0x50)
        self.post("fanboost", {"on": False})
        self.post("mode", {"mode": 1})
        self.assertEqual(self.ec(0x751), 0x00)
        self.assertEqual(self.get("state")["power"]["mode"], 1)

    def test_fan_table_roundtrip(self):
        self.post("profile", {"mode": 1, "index": 0})
        t = self.get("table/M1T1")
        t["CPU"][3]["Duty"] = 44
        code, _ = self.post("table/M1T1", {"CPU": t["CPU"], "GPU": t["GPU"]}, "PUT")
        self.assertEqual(code, 200)
        self.assertEqual(self.ec(0xF23), 88)               # duty * 2
        self.assertEqual(self.ec(0xF02), t["CPU"][3]["UpT"])  # UpT of level 3 at F00+2
        self.assertTrue(self.ec(0x7C6) & 0x04)               # RAM fan table active

    def test_fan_table_validation(self):
        t = self.get("table/M1T2")
        t["CPU"][2]["UpT"] = 10
        code, err = self.post("table/M1T2", {"CPU": t["CPU"]}, "PUT")
        self.assertEqual(code, 400, err)

    def test_pl_profile(self):
        self.post("profile", {"mode": 1, "index": 2})
        code, _ = self.post("profiles/Mode1_Profile3", {"CPU": {"PL1": 55, "PL1_Enabled": True, "PL2": 70, "PL2_Enabled": True}}, "PUT")
        self.assertEqual(code, 200)
        self.assertEqual(self.ec(0x783), 55)
        self.assertEqual(self.ec(0x784), 70)

    def test_switches_and_battery(self):
        self.post("setting", {"key": "usb_charger", "value": True})
        self.assertTrue(self.ec(0x767) & 0x10)
        self.post("setting", {"key": "fn_lock", "value": True})
        self.assertTrue(self.ec(0x74E) & 0x10)
        self.post("setting", {"key": "touchpad_toggle", "value": False})
        self.assertTrue(self.ec(0x7A6) & 0x40)
        self.post("battery", {"health_mode": 2})
        self.assertEqual(self.ec(0x7A6) & 0x30, 0x20)
        self.post("battery", {"limit_up": 80, "limit_down": 60})
        self.assertEqual(self.ec(0x7B9) & 0x7F, 80)
        self.assertEqual(self.ec(0x7D0), 60)

    def test_keyboard(self):
        self.assertEqual(self.post("keyboard/effect", {"effect": 1, "colors": [[0, 255, 0]]})[0], 200)
        has_oem = os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "uwccd", "lighting", "oem"))
        self.assertEqual(self.post("keyboard/effect", {"effect": 7})[0], 200 if has_oem else 400)   # Neon (software)
        self.assertEqual(self.post("keyboard/effect", {"effect": 13})[0], 501)      # Music
        self.assertEqual(self.post("keyboard/power", {"on": False})[0], 200)

    def test_language_setting(self):
        self.assertEqual(self.get("state")["settings"]["lang"], "en")          # English by default
        self.assertEqual(self.post("setting", {"key": "lang", "value": "ru"})[0], 200)
        self.assertEqual(self.get("state")["settings"]["lang"], "ru")
        self.assertEqual(self.post("setting", {"key": "lang", "value": "de"})[0], 400)
        self.post("setting", {"key": "lang", "value": "en"})

    def test_liquid_cooler_api(self):
        lc = self.get("state")["liquid"]
        self.assertTrue(lc["available"])
        self.assertFalse(lc["connected"])
        devs = self.post("lc/scan", {})[1]["devices"]
        self.assertEqual(devs[0]["model"], "LCT22002")
        self.assertEqual(self.post("lc/connect", {"address": "nonsense"})[0], 400)
        self.assertEqual(self.post("lc/connect", {"address": "AA:BB:CC:DD:EE:FF"})[0], 409)
        self.assertEqual(self.post("lc/connect", {"address": devs[0]["address"]})[0], 200)
        lc = self.get("state")["liquid"]
        self.assertEqual((lc["status"], lc["fw"], lc["generation"]), ("connected", "2.0.0.4", "Mk2"))
        self.assertTrue(lc["config"]["enabled"])
        self.assertEqual(self.post("lc/config", {"mode": "high"})[0], 200)
        time.sleep(0.5)
        lc = self.get("state")["liquid"]
        self.assertEqual((lc["fan"], lc["pump"]), (90, 11))
        self.assertEqual(self.post("lc/config", {"mode": "manual", "fan": 40, "pump": 7})[0], 200)
        time.sleep(0.5)
        lc = self.get("state")["liquid"]
        self.assertEqual((lc["fan"], lc["pump"]), (40, 7))
        self.assertEqual(self.post("lc/config", {"mode": "ec"})[0], 400)      # mock EC has no LC table
        self.assertEqual(self.post("lc/config", {"pump": 9})[0], 400)
        self.assertEqual(self.post("lc/config", {"tiers": [{"below": 70, "fan": 30, "pump": 7},
                                                           {"below": 60, "fan": 50, "pump": 8},
                                                           {"below": 0, "fan": 90, "pump": 11}]})[0], 400)
        self.assertEqual(self.post("lc/config", {"rgb": {"on": True, "mode": "spiral", "color": [1, 2, 3]}})[0], 200)
        self.assertEqual(self.get("state")["liquid"]["config"]["rgb"]["mode"], "spiral")
        self.assertEqual(self.post("lc/disconnect", {"forget": True})[0], 200)
        lc = self.get("state")["liquid"]
        self.assertFalse(lc["connected"])
        self.assertIsNone(lc["config"]["address"])


class LiquidCoolerUnit(unittest.TestCase):
    """Protocol frames and policy of uwccd.watercooler against the simulated cooler."""

    def setUp(self):
        os.environ["UWCC_DATA"] = tempfile.mkdtemp(prefix="uwcc-lc-")
        sys.path.insert(0, ROOT)
        import importlib
        from uwccd import store, watercooler
        importlib.reload(store)
        self.W = importlib.reload(watercooler)
        from uwccd.ec import MockEC
        self.ec = MockEC(os.path.join(os.environ["UWCC_DATA"], "ec.json"))
        self.ec.write(0x7A4, 0x80)                 # IsSupportLiquidCooling
        self.ec.write(0x7C8, self.ec.read(0x7C8) | 0x20)   # IsSupportLCFanTable
        self.temp = [50]
        self.events = []
        self.lc = self.W.LiquidCooler(self.ec, lambda: self.temp[0], lambda k, d: self.events.append(d["event"]), mock=True)
        self.lc.start()
        self.lc.connect("C0:FF:EE:22:00:02")

    def tearDown(self):
        self.W.MockLink.flow_ok = True
        self.lc.stop()

    def sent(self):
        return [x.hex() for x in self.W.MockLink.last.sent if len(x) == 8]

    def test_connect_frames_and_ec_flag(self):
        s = self.sent()
        self.assertEqual(self.W.MockLink.last.sent[0], b"sw")
        self.assertIn("fe1e0100800000ef", s)         # RGB static, OEM default green
        self.assertIn("fe1b0119000000ef", s)         # fan 25 % (tier 1 at 50 °C)
        self.assertIn("fe1c013c030000ef", s)         # pump duty 60, 8 V selector 3
        self.assertTrue(self.ec.read(0x7C7) & 0x02)
        self.lc.disconnect()
        self.assertFalse(self.ec.read(0x7C7) & 0x02)

    def test_tiers_with_hysteresis(self):
        lc = self.lc
        for t, want in ((80, (75, 11)), (69, (75, 11)), (66, (50, 8)), (90, (90, 11)), (40, (25, 8))):
            self.temp[0] = t
            lc._wake_up()
            time.sleep(0.3)
            st = lc.status()
            self.assertEqual((st["fan"], st["pump"]), want, f"at {t} °C")

    def test_ec_targets(self):
        self.ec.write(0x7E6, 0x80 | 70)
        self.ec.write(0x7E7, 0x80 | 11)
        self.lc.configure({"mode": "ec"})
        time.sleep(0.4)
        st = self.lc.status()
        self.assertEqual((st["fan"], st["pump"], st["ec_target"]), (70, 11, (70, 11)))
        self.ec.write(0x7E7, 0x00)                  # EC publishes nothing -> temperature tiers
        self.lc._wake_up()
        time.sleep(0.4)
        self.assertEqual(self.lc.status()["pump"], 8)

    def test_flow_fault_notification(self):
        self.W.MockLink.flow_ok = False
        self.W.FLOW_GRACE = 0.2
        self.lc.configure({"mode": "off"})
        time.sleep(0.3)
        self.lc.configure({"mode": "medium"})
        time.sleep(0.5)
        self.lc.loop.call_soon_threadsafe(lambda: self.lc.loop.create_task(self.lc._write(self.W.frame(self.W.METER_QUERY))))
        time.sleep(0.4)
        self.assertEqual(self.lc.status()["flow"], "fault")
        self.assertIn("flow_fault", self.events)

    def test_flow_guard_and_laptop_mode(self):
        mode = [1]
        self.lc.mode_fn = lambda: mode[0]
        self.lc.configure({"mode": "laptop"})
        time.sleep(0.4)
        self.assertEqual((self.lc.status()["fan"], self.lc.status()["pump"]), (60, 11))
        mode[0] = 0
        self.lc._wake_up()
        time.sleep(0.4)
        self.assertEqual(self.lc.status()["fan"], 40)
        self.lc.configure({"mode": "manual", "fan": 30, "pump": 8})
        time.sleep(0.4)
        self.W.MockLink.flow_ok = False
        self.lc.flow_deadline = 0
        self.lc.loop.call_soon_threadsafe(lambda: self.lc.loop.create_task(self.lc._write(self.W.frame(self.W.METER_QUERY))))
        time.sleep(0.6)
        st = self.lc.status()
        self.assertTrue(st["guard"])
        self.assertEqual((st["fan"], st["pump"]), (60, 11))
        mode[0] = 2                                  # laptop mode change ends the guard
        self.lc._wake_up()
        time.sleep(0.4)
        self.assertEqual((self.lc.status()["fan"], self.lc.status()["pump"]), (30, 8))

    def test_mk2_effect_and_off(self):
        self.lc.configure({"rgb": {"mode": "color_wave", "color": [255, 0, 0]}})
        self.assertEqual(self.sent()[-3:], ["fe330000000000ef", "fe1e01ff000000ef", "fe3301ff000006ef"])
        self.lc.configure({"rgb": {"on": False}})
        self.assertEqual(self.sent()[-2:], ["fe330000000000ef", "fe1e0000000000ef"])


class CustomModeService(MockService):
    """Non-commercial project (PH6TQxx) -> RamFan1p5 manager with the Custom mode."""

    @classmethod
    def setUpClass(cls):
        os.environ["UWCC_MOCK_PROJECT"] = "0x16"
        try:
            super().setUpClass()
        finally:
            del os.environ["UWCC_MOCK_PROJECT"]

    test_modes_and_boost = test_fan_table_roundtrip = test_pl_profile = None
    test_liquid_cooler_api = test_language_setting = test_keyboard = test_switches_and_battery = None

    def test_custom_mode(self):
        st = self.get("state")
        self.assertEqual(st["power"]["manager"], "std")
        self.assertEqual(len(st["power"]["table_names"]), 20)
        self.assertEqual(st["power"]["limits"]["pl4_max"], 175)
        self.assertEqual(self.post("mode", {"mode": 3})[0], 200)
        self.assertTrue(self.ec(0x726) & 0x80)
        self.assertEqual(self.post("profile", {"mode": 3, "index": 4})[0], 200)
        self.assertEqual(self.get("state")["power"]["current_profile"], "Mode4_Profile5")
        code, _ = self.post("profiles/Mode4_Profile5", {"CPU": {"PL1": 60, "PL2": 90, "PL4": 150, "TccOffsetSwitch": 1,
                                                                 "TccOffset": 12}, "CustomizeName": "Render"}, "PUT")
        self.assertEqual(code, 200)
        self.assertEqual((self.ec(0x783), self.ec(0x784), self.ec(0x785), self.ec(0x786)), (60, 90, 150, 0x80 | 12))
        self.assertEqual(self.post("profiles/Mode4_Profile5", {"CPU": {"PL1": 400}}, "PUT")[0], 400)
        self.assertEqual(self.post("profile-reset/Mode4_Profile5", {})[0], 200)
        self.assertEqual(self.get("state")["profiles"]["Mode4_Profile5"]["CustomizeName"], "5")
        self.assertEqual(self.post("table/M4T5/restore", {})[0], 200)
        self.assertEqual(self.post("mode", {"mode": 1})[0], 200)
        self.assertFalse(self.ec(0x726) & 0x80)

    def test_automation_settings(self):
        self.assertEqual(self.post("setting", {"key": "mode_on_battery", "value": 0})[0], 200)
        self.assertEqual(self.post("setting", {"key": "mode_on_ac", "value": "previous"})[0], 200)
        self.assertEqual(self.post("setting", {"key": "mode_on_battery", "value": "previous"})[0], 400)
        self.assertEqual(self.post("setting", {"key": "cpu_alert", "value": 150})[0], 400)
        a = self.get("state")["automation"]
        self.assertEqual((a["mode_on_battery"], a["mode_on_ac"]), (0, "previous"))
        self.assertIsInstance(self.get("history"), list)
        self.assertIn("present", self.get("gpu"))


class FanTableUnit(unittest.TestCase):
    def test_zero_filled_tail_is_unused(self):
        from uwccd.fan import normalize_points
        pts = [{"UpT": 0, "DownT": 40, "Duty": 20}, {"UpT": 50, "DownT": 45, "Duty": 40}]
        pts += [{"UpT": 0, "DownT": 0, "Duty": 0} for _ in range(14)]      # EC that pads with zeros
        normalize_points(pts)
        self.assertEqual(pts[1]["UpT"], 50)
        self.assertTrue(all(p["UpT"] == 255 and p["Duty"] == 255 for p in pts[2:]))

    def test_equal_level_temperatures_allowed(self):
        from uwccd.fan import FanTables, empty_table
        t = empty_table("M2T1")
        for i, (u, d, du) in enumerate([(0, 48, 0), (55, 56, 30), (55, 58, 30), (57, 58, 30), (66, 255, 55)]):
            t["GPU"][i].update(UpT=u, DownT=d, Duty=du)
        ft = FanTables.__new__(FanTables)
        ft.tables, ft.save = {"M2T1": t}, lambda _t: None
        self.assertEqual(ft.update("M2T1", {"GPU": t["GPU"]})["GPU"][2]["UpT"], 55)   # factory 55/55 °C
        t["GPU"][2]["UpT"] = 50
        with self.assertRaises(ValueError):
            ft.update("M2T1", {"GPU": t["GPU"]})


if __name__ == "__main__":
    unittest.main()
