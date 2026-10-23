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
        self.lc.configure({"delay_up": 0, "delay_down": 0, "smooth": False})   # immediate, as the policy tests expect

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

    def _step(self, t=None, advance=0):
        if t is not None:
            self.temp[0] = t
        self.clock[0] += advance
        self.lc._wake_up()
        time.sleep(0.25)
        st = self.lc.status()
        return st["fan"], st["pump"]

    def _fake_clock(self):
        self.clock = [time.monotonic() + 1]
        self.lc._now = lambda: self.clock[0]

    def test_tier_delays(self):
        self._fake_clock()
        self.lc.configure({"delay_up": 10, "delay_down": 30})
        self.assertEqual(self._step(50), (25, 8))
        self.assertEqual(self._step(60), (25, 8))                 # a short peak does not switch
        self.assertEqual(self.lc.status()["pending"]["dir"], "up")
        self.assertEqual(self._step(50, 3), (25, 8))              # back down before the delay -> nothing
        self.assertIsNone(self.lc.status()["pending"])
        self._step(60)
        self.assertEqual(self._step(60, 10), (50, 8))             # held 10 s -> next tier
        self.assertEqual(self._step(50), (50, 8))                 # going down waits 30 s
        self.assertEqual(self._step(50, 29), (50, 8))
        self.assertEqual(self._step(50, 2), (25, 8))
        self.assertEqual(self._step(64), (50, 8))                 # 8 °C over the tier threshold: at once
        self.assertEqual(self._step(97), (90, 11))                # 95 °C: at once

    def test_smoothing_and_ramp(self):
        self._fake_clock()
        self.lc.configure({"smooth": True})
        self._step(50)
        self.assertEqual(self._step(60, 11)[0], 35)               # old samples left the 10 s window; 25 -> 50 % in steps
        self.assertEqual([self._step(60, 1)[0] for _ in range(2)], [45, 50])
        self.lc.configure({"tiers": [{"below": 55, "fan": 25, "pump": 7}, {"below": 999, "fan": 50, "pump": 12}]})
        pumps = [self._step(60, 1)[1] for _ in range(3)]
        self.assertEqual(pumps, [11, 12, 12])                     # one voltage step at a time (8 -> 11 -> 12)

    def test_pump_idle_and_tier_pump_off(self):
        self._fake_clock()
        self.lc.configure({"pump_idle": {"enabled": True, "off_below": 50, "off_after": 60, "on_above": 55,
                                         "on_after": 10, "min_run": 0}})
        self.assertEqual(self._step(40)[1], 8)
        self.assertEqual(self._step(40, 61)[1], 0)
        self.assertTrue(self.lc.status()["pump_idle"])
        self.assertEqual(self._step(53, 30)[1], 0)                # between the thresholds: stays off
        self._step(60)
        self.assertEqual(self._step(60, 10)[1], 8)
        with self.assertRaises(ValueError):
            self.lc.configure({"pump_idle": {"off_below": 60, "on_above": 61}})
        with self.assertRaises(ValueError):
            self.lc.configure({"temp_source": "ram"})
        self.lc.configure({"pump_idle": {"enabled": False}, "temp_source": "gpu",
                           "tiers": [{"below": 50, "fan": 0, "pump": 0}, {"below": 999, "fan": 60, "pump": 8}]})
        self.assertEqual(self._step(45), (0, 0))

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

    def test_lightbar(self):
        lb = self.get("state")["keyboard"]["lightbar"]
        self.assertEqual(sorted(lb["zones"]), ["base", "hinge", "logo"])
        self.assertEqual(self.post("lightbar", {"zone": "hinge", "effect": "static", "colors": [[255, 0, 0]], "light": 3})[0], 200)
        self.assertEqual(self.get("state")["keyboard"]["lightbar"]["zones"]["hinge"]["colors"], [[255, 0, 0]])
        self.assertEqual(self.post("lightbar", {"zone": "hinge", "power": False})[0], 200)
        self.assertFalse(self.get("state")["keyboard"]["lightbar"]["zones"]["hinge"]["power"])
        self.assertEqual(self.post("lightbar", {"zone": "hinge", "power": True})[0], 200)
        self.assertEqual(self.post("lightbar", {"zone": "nope", "power": True})[0], 400)
        self.assertEqual(self.post("lightbar", {"zone": "base", "effect": "disco"})[0], 400)

    def test_temperature_limits(self):
        lim = self.get("state")["power"]["limits"]
        self.assertEqual(lim["tcc_max"], max(lim["tcc_fw_max"], 15))
        self.assertIn("tjmax", lim)
        body = lambda v: {"CPU": {"TccOffsetSwitch": 1, "TccOffset": v}}            # noqa: E731
        self.assertEqual(self.post("profiles/Mode4_Profile4", body(15), "PUT")[0], 200)
        self.assertEqual(self.post("profiles/Mode4_Profile4", body(30), "PUT")[0], 400)
        self.assertEqual(self.post("setting", {"key": "tcc_extended", "value": True})[0], 200)
        self.assertEqual(self.get("state")["power"]["limits"]["tcc_max"], 40)
        self.assertEqual(self.post("profiles/Mode4_Profile4", body(30), "PUT")[0], 200)
        self.assertEqual(self.post("profiles/Mode4_Profile4", body(41), "PUT")[0], 400)
        self.post("setting", {"key": "tcc_extended", "value": False})
        self.assertEqual(self.post("profile-reset/Mode4_Profile4", {})[0], 200)
        gt = self.get("state")["power"]["limits"].get("gpu_temp")
        if gt:                                                                        # mock dGPU: 65..87 °C
            g = lambda v: {"GPU": {"TargetTemperatureSwitch": 1, "TargetTemperature": v}}  # noqa: E731
            self.assertEqual(self.post("profiles/Mode4_Profile4", g(75), "PUT")[0], 200)
            self.assertEqual(self.post("profiles/Mode4_Profile4", g(120), "PUT")[0], 400)
            self.post("profile-reset/Mode4_Profile4", {})

    def test_export_import(self):
        def raw(path):
            r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/{path}", headers={"X-UWCC-Token": TOKEN})
            return json.load(urllib.request.urlopen(r, timeout=10))
        one = raw("export?what=fans&table=M4T3")
        self.assertEqual((one["format"], one["kind"], list(one["tables"])), ("open-uniwill-cc", "fans", ["M4T3"]))
        full = raw("export?what=all")
        self.assertIn("Mode4_Profile3", full["profiles"])
        self.assertIn("settings", full)
        # change a curve point, import it back
        t = one["tables"]["M4T3"]
        t["CPU"][0]["Duty"] = 33
        code, r = self.post("import", {"data": one, "sections": ["fans"]})
        self.assertEqual((code, r["tables"]), (200, ["M4T3"]))
        self.assertEqual(self.get("state")["tables"]["M4T3"]["CPU"][0]["Duty"], 33)
        # another laptop: refused unless forced
        other = dict(one, project_id="0x99", project="other")
        self.assertEqual(self.post("import", {"data": other, "sections": ["fans"]})[0], 400)
        self.assertEqual(self.post("import", {"data": other, "sections": ["fans"], "force": True})[0], 200)
        # a profile file of the original Control Center
        prof = {"Name": "Mode4_Profile3", "CPU": {"PL1": 70, "PL2": 100, "PL4": 150, "TccOffsetSwitch": 1, "TccOffset": 10},
                "GPU": {}, "FAN": {}, "CustomizeName": "From OEM"}
        code, r = self.post("import", {"data": {"files": [prof]}, "sections": ["profiles"]})
        self.assertEqual((code, r["profiles"]), (200, ["Mode4_Profile3"]))
        p3 = self.get("state")["profiles"]["Mode4_Profile3"]
        self.assertEqual((p3["CPU"]["PL1"], p3["CPU"]["TccOffset"], p3["CustomizeName"]), (70, 10, "From OEM"))
        self.assertEqual(self.post("import", {"data": {"hello": 1}})[0], 400)
        self.post("profile-reset/Mode4_Profile3", {})
        self.post("table/M4T3/restore", {})

    def test_update_and_dynamic_boost_offline(self):
        u = self.get("update")
        self.assertEqual(u["repo"], "https://github.com/aspidovss/open-uniwill-cc")
        self.assertTrue(u["enabled"])
        self.assertIsNone(u["checked"])                    # nothing is requested in mock mode
        self.assertIn("present", self.get("dynamic-boost"))
        self.assertEqual(self.post("setting", {"key": "update_check", "value": False})[0], 200)
        self.assertFalse(self.get("update")["enabled"])
        self.post("setting", {"key": "update_check", "value": True})

    def test_history_ranges(self):
        from uwccd.automation import average
        avg = average([{"t": 60, "ct": 50, "pl1": 45}, {"t": 62, "ct": 70, "pl1": 55}])
        self.assertEqual((avg["ct"], avg["ct_mx"], avg["pl1"], avg["t"]), (60.0, 70, 55, 62))
        time.sleep(2.5)
        self.assertIsInstance(self.get("history?range=60"), list)
        self.assertTrue(self.get("history?range=1m"))                  # fine 2 s buffer is filled at once
        self.assertIsInstance(self.get("history?range=24h"), list)
        self.assertEqual(self.post("setting", {"key": "history_record", "value": False})[0], 200)
        self.assertFalse(self.get("state")["settings"]["history_record"])
        self.post("setting", {"key": "history_record", "value": True})

    def test_report_and_update_request(self):
        import io as _io
        import zipfile
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/report?private=mac&name=uwcc-report-test-1.zip",
                                   headers={"X-UWCC-Token": TOKEN})
        resp = urllib.request.urlopen(r, timeout=60)
        self.assertEqual(resp.headers["X-UWCC-Filename"], "uwcc-report-test-1.zip")
        z = zipfile.ZipFile(_io.BytesIO(resp.read()))
        self.assertTrue({"report.json", "report.txt", "uwccd.log"} <= set(z.namelist()))
        self.assertTrue(all(n.startswith(("report.", "uwccd.log", "acpi/", "oem/")) for n in z.namelist()))
        rep = json.loads(z.read("report.json"))
        self.assertEqual(rep["private_included"], ["mac"])
        self.assertIn("0700-07FF", rep["ec"]["dump"])
        self.assertEqual(rep["ec"]["named"]["PROJECT_ID"]["addr"], "0x740")
        self.assertNotIn("hostname", rep["system"])
        self.assertIn("project_id", self.get("report/summary"))
        self.assertEqual(self.post("reveal", {"name": "uwcc-report-test-1.zip"})[1], {"tray": False})
        self.assertIn("build", self.get("update"))
        self.assertIn("acpi", rep)
        self.assertIn("timings_s", rep)
        st = self.post("report/start", {"sections": ["system", "ec"], "name": "uwcc-report-job-1.zip"})[1]
        for _ in range(100):
            if st["state"] != "running":
                break
            time.sleep(0.1)
            st = self.get("report/status")
        self.assertEqual((st["state"], st["name"]), ("done", "uwcc-report-job-1.zip"))
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/report/file?id={st['id']}", headers={"X-UWCC-Token": TOKEN})
        self.assertTrue(zipfile.ZipFile(_io.BytesIO(urllib.request.urlopen(r, timeout=30).read())).namelist())
        self.assertNotIn("oem_files_full", rep["sections"])
        from uwccd import report_oem
        red = report_oem._redact_bytes("C:\\Users\\Иван\\x".encode("utf-16"), lambda t: t.replace("Иван", "<user>"))
        self.assertEqual(red.decode("utf-16"), "C:\\Users\\<user>\\x")

    def test_history_export(self):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/history/export?format=csv", headers={"X-UWCC-Token": TOKEN})
        resp = urllib.request.urlopen(r, timeout=10)
        self.assertIn("attachment", resp.headers["Content-Disposition"])
        self.assertTrue(resp.read().decode("utf-8-sig").startswith("time,cpu_temp_c,"))
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/history/export?format=xml", headers={"X-UWCC-Token": TOKEN})
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(r, timeout=10)


class UpdateAndBuildUnit(unittest.TestCase):
    def test_download_verified(self):
        import hashlib
        import http.server
        import threading as th
        sys.path.insert(0, ROOT)
        from uwccd import updates
        d = tempfile.mkdtemp(prefix="uwcc-upd-")
        payload = b"MZ fake installer" * 1000
        os.makedirs(os.path.join(d, "srv"))
        with open(os.path.join(d, "srv", "open-uniwill-cc-windows-9.9.9-setup.exe"), "wb") as f:
            f.write(payload)
        with open(os.path.join(d, "srv", "SHA256SUMS.txt"), "w") as f:
            f.write(f"{hashlib.sha256(payload).hexdigest()}  open-uniwill-cc-windows-9.9.9-setup.exe\n")
        with open(os.path.join(d, "srv", "BAD.txt"), "w") as f:
            f.write("0" * 64 + "  open-uniwill-cc-windows-9.9.9-setup.exe\n")
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=os.path.join(d, "srv"), **k)  # noqa: E731
        handler.log_message = lambda *a: None
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        th.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            pct = []
            path = updates.download_verified(base + "/open-uniwill-cc-windows-9.9.9-setup.exe", base + "/SHA256SUMS.txt",
                                             os.path.join(d, "Downloads"), pct.append)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), payload)
            self.assertEqual(pct[-1], 100)
            with self.assertRaises(ValueError):
                updates.download_verified(base + "/open-uniwill-cc-windows-9.9.9-setup.exe", base + "/BAD.txt",
                                          os.path.join(d, "Bad"))
            self.assertEqual(os.listdir(os.path.join(d, "Bad")), [])           # the damaged file is deleted
        finally:
            srv.shutdown()

    def test_version_string(self):
        sys.path.insert(0, ROOT)
        import uwccd
        uwccd._build = {"date": "2026-10-23", "commit": "abc1234", "source": "build"}
        try:
            self.assertEqual(uwccd.version_string(), f"{uwccd.__version__} · build 2026-10-23 · abc1234")
        finally:
            uwccd._build = None


class HwocUnit(unittest.TestCase):
    def test_super_performance_flow(self):
        sys.path.insert(0, ROOT)
        from uwccd import hwoc
        from uwccd.ec import MockEC
        ec = MockEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        ec.write(0x7C7, 0x12)                                   # level 4 (bits 2..4), cooler flag
        lc_state = {"connected": False, "flow": "idle"}
        calls = []

        class O:
            pass
        svc = O()
        svc.ec, svc.fan_control, svc.emit = ec, True, lambda *a: calls.append(a[0])
        svc.settings_store = {"lc_hwoc": True}
        svc.liquid = O()
        svc.liquid.available, svc.liquid.ec_table, svc.liquid.status = True, True, lambda: lc_state
        svc.power = O()
        svc.power.manager, svc.power.option, svc.power.tables = "std", {"OperatingMode": 2}, O()
        svc.power.set_user_profile = lambda m: calls.append(("profile", m))
        h = hwoc.LiquidHWOC(svc)
        hwoc.FLOW_STABLE = 0
        h.update()
        self.assertEqual((h.active, h.reason), (False, "cooler not connected"))
        lc_state.update(connected=True, flow="ok")
        h.update()
        self.assertTrue(h.active)
        self.assertEqual(ec.read(0xF5F), 5)                     # Turbo -> EC liquid-cooling table 5
        self.assertTrue(h.table_loaded)
        self.assertEqual((ec.pwup_calls, h.level), ([4], 4))
        self.assertTrue(svc.power.tables.blocked)
        svc.power.lc_override(0)                                # mode change while active -> Office table 7
        self.assertEqual(ec.read(0xF5F), 7)
        h.on_wmi(0xC2)
        self.assertEqual(ec.pwup_calls[-1], 4)
        lc_state.update(flow="fault")
        h.update()
        self.assertFalse(h.active)
        self.assertFalse(svc.power.tables.blocked)
        self.assertIsNone(svc.power.lc_override)
        self.assertIn(("profile", 2), calls)
        svc.settings_store["lc_hwoc"] = False
        lc_state.update(flow="ok")
        h.update()
        self.assertEqual((h.active, h.reason), (False, "off"))


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


class PlatformSupportUnit(unittest.TestCase):
    def _pf(self, pid):
        from uwccd import hw
        class E:
            def read(self, a): return pid if a == hw.R.PROJECT_ID else 0
            def bit(self, a, b): return 0
        orig = hw.project2ex_id
        hw.project2ex_id = lambda ec, raw: raw
        try:
            return hw.Platform(E())
        finally:
            hw.project2ex_id = orig

    def test_levels(self):
        p = self._pf(0x10)
        self.assertEqual((p.support, p.project_name, p.display_name), ("tested", "0x10", "MAIBENBEN Tsunami"))
        p = self._pf(0x1A)
        self.assertEqual((p.support, p.project_name), ("experimental", "0x1A"))
        self.assertIn("Kuangshi", p.display_name)
        self.assertEqual(self._pf(0x99).support, "experimental")
        from uwccd import hw
        known = next(k for k in hw.PROJECT_NAMES if k not in hw.TESTED_IDS)
        self.assertEqual(self._pf(known).support, "known")


if __name__ == "__main__":
    unittest.main()
