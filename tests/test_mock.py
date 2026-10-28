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
if sys.platform == "win32":     # the simulated service needs Linux paths (/run, /proc, /sys); run the tests in WSL or Linux
    raise unittest.SkipTest("tests/test_mock.py runs on Linux only")
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
    def test_betterrgb_fx_api(self):
        st = self.get("state")["keyboard"]
        self.assertIn("100", {str(k) for k in st["fx_effects"]})
        self.assertEqual(self.post("keyboard/effect", {"effect": 107, "light": 3, "fx": {"density": 5}})[0], 200)
        k = self.get("state")["keyboard"]
        self.assertEqual((k["effect"]["idx"], k["effect"]["fx"]["density"]), (107, 5))
        self.assertEqual(k["fx"]["name"], "Rain")
        code, r = self.post("keyboard/fx/config", {"fps_ac": 20, "bar": {"mode": "battery"}})
        self.assertEqual((code, r["fps_ac"], r["bar"]["mode"]), (200, 20, "battery"))
        self.assertIn("volume", self.post("keyboard/fx/input", {"metrics": {"volume": 0.5}})[1]["needs"])
        self.assertEqual(self.post("keyboard/fx/calibrate", {"action": "start"})[1]["calibrating"], True)
        r = self.post("keyboard/fx/calibrate", {"action": "apply", "observed": [255, 230, 200]})[1]
        self.assertEqual((r["calibrating"], r["gains"][2]), (False, 1000))
        self.assertEqual(self.post("keyboard/fx/calibrate", {"action": "reset"})[1]["gains"], [1000, 1000, 1000])
        self.assertEqual(self.post("keyboard/fx/input", {"screen": {"w": 2, "h": 2, "rgb": ""}})[0], 400)
        self.post("keyboard/fx/config", {"bar": {"mode": "off"}})
        self.assertEqual(self.post("keyboard/effect", {"effect": 1, "colors": [[0, 255, 0]]})[0], 200)
        self.assertIsNone(self.get("state")["keyboard"]["fx"])

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

    def test_user_agreement(self):
        from uwccd import EULA_VERSION
        st = self.get("state")["settings"]
        self.assertEqual(st["eula_version"], EULA_VERSION)
        self.assertEqual(self.post("setting", {"key": "eula_accepted", "value": EULA_VERSION + 1})[0], 400)
        self.assertEqual(self.post("setting", {"key": "eula_accepted", "value": EULA_VERSION})[0], 200)
        self.assertEqual(self.get("state")["settings"]["eula_accepted"], EULA_VERSION)
        web = os.path.join(os.path.dirname(__file__), "..", "uwccd", "web")
        for lang in ("en", "ru"):
            with open(os.path.join(web, f"eula.{lang}.txt"), "rb") as f:
                data = f.read()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), lang)            # BOM: Inno Setup reads it as UTF-8
            self.assertIn(b"MIT", data)

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


class CliService(MockService):
    """bin/uwccctl against the simulated service (MAIBENBEN Tsunami, project 0x10)."""

    @classmethod
    def setUpClass(cls):
        os.environ["UWCC_MOCK_PROJECT"] = "0x10"
        try:
            super().setUpClass()
        finally:
            del os.environ["UWCC_MOCK_PROJECT"]

    def cli(self, *args, code=0):
        env = dict(os.environ, UWCC_PORT=str(self.port), UWCC_TOKEN=TOKEN, PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "uwccctl"), *args], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, code, f"uwccctl {' '.join(args)}: {r.stdout}{r.stderr}")
        return r.stdout

    def j(self, *args, code=0):
        return json.loads(self.cli("--json", *args, code=code))

    def test_cli_status_monitor_help(self):
        self.assertIn("MAIBENBEN Tsunami", self.cli("status"))
        d = self.j("status")
        self.assertIn("state", d)
        self.assertIn("fans", d["monitor"])
        self.assertIn("cpu", self.j("monitor"))
        self.assertIn("kb effect", self.cli("help", "kb"))
        self.assertIn("COMMAND", self.cli("help"))
        self.assertIn("error", self.j("nosuchcommand", code=2))

    def test_cli_betterrgb(self):
        self.assertIn("Quicksand", self.cli("kb", "fx"))
        self.cli("kb", "fx", "rain", "density=4", "colors=5080FF,FFFFFF", "--light", "3")
        k = self.get("state")["keyboard"]["effect"]
        self.assertEqual((k["idx"], k["light"], k["fx"]["density"], k["fx"]["colors"][1]), (107, 3, 4, [255, 255, 255]))
        self.assertIn("BetterRGB effect Rain", self.cli("kb"))
        self.assertIn("transition=ripple_top", self.cli("kb", "fx-config", "transition=ripple_top", "bar=cpu"))
        self.assertIn("calibrating yes", self.cli("kb", "fx-calibrate", "start"))
        self.assertIn("calibrating no", self.cli("kb", "fx-calibrate", "cancel"))
        self.cli("kb", "fx", "rain", "nope=1", code=2)
        self.cli("kb", "effect", "single")

    def test_cli_modes_profiles(self):
        self.assertEqual(self.j("mode", "turbo")["mode"], "turbo")
        self.assertEqual(self.get("state")["power"]["mode"], 2)
        self.cli("mode", "custom")
        self.assertEqual(self.j("profile", "2")["Name"], "Mode4_Profile3")
        p = self.j("profile", "set", "custom:2", "pl1=60", "pl2=90", "tcc=10", "ctgp=off", "name=Quiet")
        self.assertEqual((p["CPU"]["PL1"], p["CPU"]["PL2"], p["CPU"]["TccOffsetSwitch"], p["CPU"]["TccOffset"]),
                         (60, 90, 1, 10))
        self.assertEqual((p["GPU"]["ConfigurableTGPSwitch"], p["CustomizeName"]), (0, "Quiet"))
        self.assertEqual(self.j("profile", "show")["CustomizeName"], "Quiet")
        self.assertEqual(self.j("profile", "set", "pl1=999", code=1)["error"][:10], "ValueError")
        self.assertEqual(self.j("profile", "reset", "custom:2")["CustomizeName"], "3")
        self.assertEqual(len(self.j("profile", "list")), 11)
        self.cli("profile", "show", "nosuch", code=2)
        self.assertTrue(self.j("boost", "on")["fan_boost"])
        self.assertFalse(self.j("boost", "off")["fan_boost"])
        self.assertTrue(self.j("super", "on")["super_performance"])
        self.assertTrue(self.get("state")["power"]["super_performance"])
        self.cli("super", "off")
        self.assertTrue(self.j("ramoc", "on")["pending_reboot"])
        self.cli("ramoc", "off")
        self.cli("restore", code=2)
        self.cli("restore", "--yes")
        self.cli("mode", "office")

    def test_cli_fan_tables(self):
        names = [r["table"] for r in self.j("fan", "list")]
        self.assertEqual(len(names), 20)
        t = self.j("fan", "set", "M3T2", "cpu", "0/45:0", "55/50:30", "70/65:60", "85/80:100")
        self.assertEqual([(x["UpT"], x["Duty"]) for x in t["CPU"][:5]], [(0, 0), (55, 30), (70, 60), (85, 100), (255, 255)])
        self.assertEqual(self.get("table/M3T2")["CPU"][2]["DownT"], 65)
        self.cli("fan", "set", "M3T2", "cpu", "0/45:0", "55/50:20", code=1)        # last level below 40 %
        self.assertTrue(self.j("fan", "separate", "M3T2", "on")["FanControlRespective"])
        path = os.path.join(self.tmp, "t.json")
        with open(path, "w") as f:
            f.write(self.cli("--json", "fan", "show", "M3T2"))
        self.j("fan", "reset", "M3T2")
        self.assertNotEqual(self.get("table/M3T2")["CPU"][1]["UpT"], 55)
        self.assertEqual(self.j("fan", "set", "M3T2", "--file", path)["CPU"][1]["UpT"], 55)
        self.assertIn("CPU:", self.cli("fan", "show"))
        self.cli("fan", "show", "X9", code=2)

    def test_cli_battery_keyboard(self):
        self.assertEqual(self.j("battery", "mode", "stationary")["health_mode"], 2)
        b = self.j("battery", "limit", "80", "60")
        self.assertEqual((b["limit_up"], b["limit_down"]), (80, 60))
        self.assertTrue(self.j("battery", "typec", "on")["typec_priority"])
        self.cli("battery", "mode", "full")
        names = {e["name"].lower() for e in self.j("kb", "effects")}
        self.assertIn("wave", names)
        k = self.j("kb", "effect", "wave", "--speed", "3", "--multi", "--dir", "left")
        self.assertEqual((k["effect"]["idx"], k["effect"]["speed"], k["effect"]["circular"], k["effect"]["direction"]),
                         (2, 3, True, 1))
        k = self.j("kb", "effect", "single", "--color", "00ff80", "--light", "2", "--no-multi")
        self.assertEqual((k["effect"]["colors"], k["effect"]["light"], k["effect"]["circular"]), ([[0, 255, 128]], 2, False))
        self.assertEqual(self.j("kb", "effect", "breathing")["effect"]["colors"], [[0, 255, 128]])   # options kept
        self.cli("kb", "effect", "nosuch", code=2)
        self.cli("kb", "effect", "single", "--color", "zz", code=2)
        self.assertFalse(self.j("kb", "off")["power"])
        self.assertTrue(self.j("kb", "on")["power"])
        lb = self.j("lb", "logo", "color", "ff0000", "breathing")
        self.assertEqual((lb["zones"]["logo"]["effect"], lb["zones"]["logo"]["colors"]), ("breathing", [[255, 0, 0]]))

    def test_cli_settings_apps_lc(self):
        self.assertEqual(self.j("set", "fn_lock", "on"), {"fn_lock": True})
        self.assertEqual(self.j("get", "fn_lock"), {"fn_lock": True})
        self.cli("set", "fn_lock", "off")
        self.assertEqual(self.j("set", "cpu_alert", "90"), {"cpu_alert": 90})
        self.assertEqual(self.j("set", "mode_on_battery", "office"), {"mode_on_battery": 0})
        self.cli("set", "mode_on_battery", "previous", code=1)
        self.cli("set", "kb_timeout", "abc", code=2)
        self.cli("set", "nosuch", "1", code=2)
        self.assertEqual(self.j("set", "kb_timeout", "30"), {"kb_timeout": 30})
        self.assertIn("ppd_sync", self.j("get"))
        self.assertEqual(self.j("apps", "add", "steam", "gaming"), [{"process": "steam", "mode": 1, "enabled": True}])
        self.assertFalse(self.j("apps", "disable", "steam")[0]["enabled"])
        self.assertEqual(self.j("apps", "remove", "steam"), [])
        self.cli("apps", "remove", "steam", code=1)
        c = self.j("lc", "tiers", "50:20:7", "65:40:8", "999:80:12")["config"]
        self.assertEqual([t["below"] for t in c["tiers"]], [50, 65, 999])
        self.assertEqual(self.j("lc", "set", "temp_source", "gpu")["config"]["temp_source"], "gpu")
        self.assertEqual(self.j("lc", "set", "delay_up", "20")["config"]["delay_up"], 20)
        self.assertFalse(self.j("lc", "set", "smooth", "off")["config"]["smooth"])
        pi = self.j("lc", "idle", "on", "off_below=45")["config"]["pump_idle"]
        self.assertEqual((pi["enabled"], pi["off_below"]), (True, 45))
        self.cli("lc", "set", "temp_source", "disk", code=1)
        self.assertEqual(self.j("debug", "on"), {"debug": True})
        self.cli("debug", "off")

    def test_fan_manager_setting(self):
        self.assertEqual(self.get("state")["settings"]["fan_manager"], "auto")
        self.assertEqual(self.post("setting", {"key": "fan_manager", "value": "xyz"})[0], 400)
        self.assertTrue(self.j("set", "fan_manager", "cml")["restarting"])
        self.assertEqual(self.get("state")["settings"]["fan_manager"], "cml")
        self.assertEqual(self.post("setting", {"key": "fan_manager", "value": "auto"})[0], 200)
        self.assertEqual(self.get("state")["settings"]["fan_manager"], "auto")


for _n in [n for n in dir(MockService) if n.startswith("test_")]:
    setattr(CliService, _n, None)


class EcAccessService(MockService):
    """Windows EC path (simulated): OEM driver missing -> no EC access -> WMI after the warning; installer choice."""

    @classmethod
    def setUpClass(cls):
        os.environ["UWCC_MOCK_PROJECT"] = "0x10"
        os.environ["UWCC_MOCK_OEM"] = "0"
        store = tempfile.mkdtemp(prefix="uwcc-drvstore-")
        for f in ("UWACPIDriver.inf", "UWACPIDriver.sys", "uwacpidriver.cat"):
            with open(os.path.join(store, f.lower()), "wb") as fh:
                fh.write(b"[Version]\r\nDriverVer = 09/13/2022,17.53.43.609\r\n[Standard.NTamd64]\r\nx=y, ACPI\\INOU0000\r\n"
                         b"AddService = UWACPIDriver\r\n" + b";" * 600 if f.endswith(".inf") else b"\0" * 8192)
        os.environ["UWCC_MOCK_DRIVERSTORE"] = store
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        os.environ.pop("UWCC_MOCK_PROJECT", None)
        os.environ.pop("UWCC_MOCK_OEM", None)
        os.environ.pop("UWCC_MOCK_DRIVERSTORE", None)

    @classmethod
    def restart(cls):
        cls.proc.terminate()
        cls.proc.wait(5)
        env = dict(os.environ, UWCC_DATA=os.path.join(cls.tmp, "data"), UWCC_RUN=os.path.join(cls.tmp, "run"),
                   PYTHONPATH=ROOT)
        code = ("import uwccd.ec as e; e.MockEC.__init__.__defaults__ = (%r,); "
                "import runpy; runpy.run_module('uwccd', run_name='__main__')" % cls.ecfile)
        cls.proc = subprocess.Popen([sys.executable, "-c", code, "--mock", "--port", str(cls.port), "--token", TOKEN],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                cls.get("state")
                return
            except Exception:  # noqa: BLE001
                time.sleep(0.1)

    def admin_key(self):
        with open(os.path.join(self.tmp, "run", "admin-token")) as f:
            return f.read().strip()

    def apost(self, path, body):
        """POST with the administrator key (what `uwccctl` sends when run as administrator / root)."""
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/{path}", data=json.dumps(body).encode(),
                                   method="POST", headers={"X-UWCC-Token": TOKEN, "X-UWCC-Admin": self.admin_key()})
        try:
            return 200, json.load(urllib.request.urlopen(r, timeout=30))
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def wait_selfcheck(self):
        for _ in range(300):
            r = self.get("selfcheck")
            if not r["running"]:
                return r
            time.sleep(0.1)
        self.fail("self-check did not finish")

    def test_ec_paths(self):
        a = self.get("ec-access")
        self.assertEqual((a["active"], a["reason"], a["oem_present"]), ("none", "oem_missing", False))
        self.assertEqual(set(a["features"].values()), {"off"})
        self.assertFalse(a["admin"]["unlocked"])
        # EC Manager changes need administrator rights
        code, r = self.post("ec-access", {"consent": a["consent_version"]})
        self.assertEqual((code, r.get("admin_required")), (403, True))
        self.assertEqual(self.post("admin/unlock", {})[0], 403)                      # the ordinary key is not enough
        self.assertEqual(self.apost("ec-access", {"backend": "bogus"})[0], 400)
        self.assertEqual(self.apost("ec-access", {"consent": 99})[0], 400)
        code, r = self.apost("ec-access", {"consent": a["consent_version"]})
        self.assertEqual(code, 200)
        self.assertTrue(r["consent"] and r["restart_needed"])
        self.restart()
        a = self.get("ec-access")
        self.assertEqual((a["active"], a["setting"]), ("wmi", "auto"))
        self.assertEqual(a["features"]["power_boost_lc"], "off")
        self.assertEqual(a["features"]["fan_tables"], "slow")
        self.assertTrue(a["tested"])
        self.assertEqual((a["platform"]["id"], a["platform"]["status"], a["platform"]["source"]), ("uniwill-0x10", "verified", "builtin"))
        st = self.get("state")
        self.assertEqual(st["power"]["limits"]["source"], "config")
        self.assertEqual((st["power"]["limits"]["pl1_max"], st["power"]["limits"]["db_max"]), (160, 25))
        self.assertFalse(st["hwoc"]["supported"])
        self.assertEqual(self.post("mode", {"mode": 2})[0], 200)                    # control works through WMI
        self.assertEqual(self.ec(0x751) & 0x10, 0x10)
        t = self.post("ec-access/test", {})[1]
        self.assertEqual((t["path"], t["project"]), ("wmi", "0x10"))
        # unlock for the window (what `uwccctl ec unlock` does), then plain requests pass
        code, r = self.apost("admin/unlock", {"seconds": 120})
        self.assertEqual((code, r["unlocked"]), (200, True))
        self.assertTrue(self.get("ec-access")["admin"]["unlocked"])
        # ec_wmi.json: validation, locked feature, hard caps, factory limits of a verified platform, import / reset
        self.assertEqual(self.post("ec-access/config", {"config": {"bogus": 1}})[0], 400)
        self.assertEqual(self.post("ec-access/config", {"config": {"poll": {"cache_ms": -5}}})[0], 400)
        self.assertEqual(self.post("ec-access/config", {"config": {"limits": {"0x10": {"PL4": 400}}}})[0], 400)   # cap 300
        self.assertEqual(self.post("ec-access/config", {"config": {"limits": {"0x10": {"PL4": 260}}}})[0], 400)   # factory 250
        self.assertEqual(self.post("ec-access/config", {"config": {"limits": {"0x10": {"PL1": 150, "PL4": 240}}}})[0], 200)
        code, r = self.post("ec-access/config", {"config": {"features": {"battery": "off", "power_boost_lc": "on"}}})
        self.assertEqual(code, 200)
        self.assertEqual((r["effective"]["features"]["battery"], r["effective"]["features"]["power_boost_lc"]), ("off", "off"))
        self.assertEqual(self.get("ec-access")["features"]["battery"], "off")
        self.post("ec-access/config", {"reset": True})
        self.assertEqual(self.get("ec-access")["features"]["battery"], "on")
        self.post("admin/lock", {})
        self.assertEqual(self.post("ec-access/config", {"reset": True})[0], 403)
        # monitoring switches: WMI off -> temperatures only; all off -> nothing, the cooler would use a preset
        self.post("setting", {"key": "monitor_off_wmi", "value": True})
        self.assertEqual(self.get("ec-access")["monitoring"]["level"], "light")
        self.assertIn(self.get("monitor").get("monitoring"), ("light",))
        self.post("setting", {"key": "monitor_off_all", "value": True})
        self.assertEqual(self.get("state")["monitoring"], "off")
        self.post("setting", {"key": "monitor_off_all", "value": False})
        self.post("setting", {"key": "monitor_off_wmi", "value": False})
        self.assertEqual(self.get("state")["monitoring"], "full")
        # self-check: stage 1 reads; stage 2 needs the administrator key, writes and restores
        self.assertEqual(self.apost("selfcheck", {"stage": 2})[0], 409)          # stage 1 first
        self.assertFalse(self.get("selfcheck")["stage1_done"])
        code, _ = self.post("selfcheck", {"stage": 1})
        self.assertEqual(code, 200)
        r = self.wait_selfcheck()["result"]
        ids = {i["id"]: i["status"] for i in r["items"]}
        self.assertEqual((ids["project"], ids["oem_path"]), ("ok", "skip"))      # OEM driver missing in this test
        self.assertEqual(r["draft"]["match"]["project"], ["0x10"])
        fn_before, pl1_before = self.ec(0x74E), self.ec(0x783)
        self.assertEqual(self.post("selfcheck", {"stage": 2})[0], 403)
        self.assertEqual(self.apost("selfcheck", {"stage": 2})[0], 200)
        r = self.wait_selfcheck()["result"]
        ids = {i["id"]: i["status"] for i in r["items"]}
        for k in ("fn_lock", "touchpad", "modes", "power_limits", "gpu_power", "battery", "fan_tables"):
            self.assertEqual(ids[k], "ok", k)
        self.assertEqual(ids["pwup"], "fail")
        self.assertEqual((ids["backup"], ids["restore"]), ("ok", "ok"))                 # forced backup, verified restore
        self.assertTrue(os.path.isfile(r["backup"]["path"]) and r["backup"]["count"] > 100)
        self.assertEqual(r["backup"]["restored"], r["backup"]["count"])
        self.assertEqual((self.ec(0x74E), self.ec(0x783)), (fn_before, pl1_before))   # restored
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "selfcheck-snapshot.json")))
        self.assertEqual(r["features"]["fan_tables"], "slow")
        exp = self.get("selfcheck/export")
        self.assertEqual(exp["draft_profile"]["status"], "draft")
        # a report runs stage 1 again but keeps the stage 2 result shown in EC Manager
        st = self.post("report/start", {"sections": ["selfcheck"], "name": "uwcc-report-sc-1.zip"})[1]
        for _ in range(100):
            if self.get("report/status")["state"] != "running":
                break
            time.sleep(0.2)
        self.assertEqual(self.get("report/status")["state"], "done")
        self.assertEqual(self.get("selfcheck/export")["result"]["stage"], 2)
        # the draft becomes this laptop's platform profile (administrator), then back to the built-in one
        self.assertEqual(self.post("platform/apply-draft", {})[0], 403)
        code, p = self.apost("platform/apply-draft", {})
        self.assertEqual((code, p["source"], p["status"], p["modified"]), (200, "user", "draft", True))
        bad = dict(exp["draft_profile"], limits={"PL1": 160, "PL2": 160, "PL4": 999})
        self.assertEqual(self.apost("platform/import", {"profile": bad})[0], 400)
        self.assertEqual(self.apost("platform/reset", {})[1]["source"], "builtin")
        # interrupted stage 2: the snapshot is restored on the next start
        with open(os.path.join(self.tmp, "data", "selfcheck-snapshot.json"), "w") as f:
            json.dump({"regs": {"0x74E": 0x10}}, f)
        self.restart()
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "selfcheck-snapshot.json")))
        # installer choice: OEM only -> no EC access again (driver missing), the file is consumed
        with open(os.path.join(self.tmp, "data", "ec_backend.install"), "w") as f:
            f.write("oem")
        self.restart()
        a = self.get("ec-access")
        self.assertEqual((a["setting"], a["active"], a["reason"]), ("oem", "none", "oem_missing"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "ec_backend.install")))
        self.apost("ec-access", {"backend": "wmi"})
        self.restart()
        self.assertEqual(self.get("ec-access")["active"], "wmi")
        # free build: the OEM driver package is looked for in <ProgramData>/UWCC/driver and installed from EC Manager
        a = self.get("ec-access")
        self.assertIsNone(a["driver_package"])
        self.assertEqual(self.apost("ec-access/install-driver", {})[0], 409)
        drv = os.path.join(self.tmp, "UWCC", "driver")
        os.makedirs(drv, exist_ok=True)
        for f in ("UWACPIDriver.inf", "UWACPIDriver.sys", "uwacpidriver.cat"):
            open(os.path.join(drv, f), "w").close()
        self.assertEqual(self.get("ec-access")["driver_package"]["dir"], drv)
        self.assertEqual(self.get("ec-access")["driver_package"]["check"]["level"], "hard")   # empty files
        self.assertEqual(self.apost("ec-access/install-driver", {"accept_risks": True})[0], 400)
        for f in os.listdir(drv):
            os.remove(os.path.join(drv, f))
        store = os.environ["UWCC_MOCK_DRIVERSTORE"]
        for f in os.listdir(store):
            with open(os.path.join(store, f), "rb") as a, open(os.path.join(drv, f), "wb") as b:
                b.write(a.read())
        self.assertEqual(self.get("ec-access")["driver_package"]["check"]["level"], "warn")    # not a known version
        self.assertEqual(self.post("ec-access/install-driver", {})[0], 403)
        code, r = self.apost("ec-access/install-driver", {"accept_risks": True})
        self.assertEqual((code, r["installed"], r["restart_needed"]), (200, True, True))
        self.assertEqual(self.get("ec-access")["setting"], "auto")
        # 1.6.2: the package is checked; an unknown version needs "I understand the risk"
        import shutil as _sh
        for f in os.listdir(drv):
            os.remove(os.path.join(drv, f))
        for f in os.listdir(os.path.join(ROOT, "proprietary", "driver")) if os.path.isdir(os.path.join(ROOT, "proprietary", "driver")) else []:
            _sh.copy(os.path.join(ROOT, "proprietary", "driver", f), drv)
        if os.listdir(drv):
            pkg = self.get("ec-access")["driver_package"]
            self.assertEqual(pkg["check"]["level"], "ok")
            with open(os.path.join(drv, "UWACPIDriver.sys"), "ab") as f:
                f.write(b"x")                                       # another (unknown) version
            pkg = self.get("ec-access")["driver_package"]
            self.assertEqual(pkg["check"]["level"], "warn")
            r = self.apost("ec-access/install-driver", {})[1]
            self.assertTrue(r["risk_required"] and not r["installed"])
            r = self.apost("ec-access/install-driver", {"accept_risks": True})[1]
            self.assertTrue(r["installed"])
        # fetch from the driver store (simulated by UWCC_MOCK_DRIVERSTORE in setUpClass)
        for f in os.listdir(drv):
            os.remove(os.path.join(drv, f))
        self.assertEqual(self.post("ec-access/fetch-driver", {})[0], 403)
        code, r = self.apost("ec-access/fetch-driver", {})
        self.assertEqual((code, sorted(x.lower() for x in r["files"])), (200, ["uwacpidriver.cat", "uwacpidriver.inf", "uwacpidriver.sys"]))
        self.assertEqual(r["package"]["check"]["checks"][0]["id"], "files")
        # monitoring settings, history size / clear / folder
        self.post("setting", {"key": "monitoring", "value": "off_both"})
        m = self.get("ec-access")["monitoring"]
        self.assertEqual((m["off_oem"], m["off_wmi"], m["off_all"]), (True, True, False))
        self.post("setting", {"key": "monitoring", "value": "full"})
        self.assertEqual(self.post("setting", {"key": "monitor_interval", "value": 99})[0], 400)
        self.post("setting", {"key": "monitor_interval", "value": 3})
        self.assertEqual(self.get("ec-access")["history"]["interval"], 3)
        self.post("setting", {"key": "history_max_kb", "value": 64})
        self.assertEqual(self.get("ec-access")["history"]["max_kb"], 64)
        self.assertEqual(self.post("history/clear", {})[1]["points"]["day"], 0)
        newdir = os.path.join(self.tmp, "hist")
        self.assertEqual(self.post("history/config", {"dir": newdir})[0], 403)
        code, r = self.apost("history/config", {"dir": newdir})
        self.assertEqual((code, r["dir"]), (200, newdir))
        self.assertEqual(self.apost("history/config", {"dir": "relative"})[0], 400)
        # built-in help: the documentation is served, nothing outside docs/
        hr = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/help/EC/OEM-driver.md", timeout=10)
        self.assertIn("UWACPIDriver", hr.read().decode())
        for bad in ("/help/../uwccd/api.py", "/help/EC/../../LICENSE", "/help/%2e%2e/README.md"):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}{bad}", timeout=10)


for _n in [n for n in dir(MockService) if n.startswith("test_")]:
    setattr(EcAccessService, _n, None)


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

    def test_super_performance_and_ram_oc(self):
        st = self.get("state")
        self.assertTrue(st["settings"]["mem_oc_support"])
        self.assertFalse(st["power"]["super_performance"])
        # super performance works in any mode and survives mode changes
        self.assertEqual(self.post("mode", {"mode": 1})[0], 200)
        self.assertEqual(self.post("setting", {"key": "super_performance", "value": True})[0], 200)
        self.assertEqual(self.ec(0x751) & 0xBF, 0x10)              # Turbo fan mode
        self.assertFalse(self.ec(0x726) & 0x80)
        self.assertEqual(self.post("mode", {"mode": 3})[0], 200)
        self.assertTrue(self.get("state")["power"]["super_performance"])
        self.assertEqual(self.ec(0x751) & 0xBF, 0x10)
        self.assertFalse(self.ec(0x726) & 0x80)                    # SetFanMode(2) clears the Custom flag
        self.assertEqual(self.post("setting", {"key": "super_performance", "value": False})[0], 200)
        self.assertTrue(self.ec(0x726) & 0x80)                     # back to Custom
        self.assertEqual(self.post("mode", {"mode": 0})[0], 200)
        self.assertEqual(self.ec(0x751) & 0xBF, 0xA0)              # Office
        # RAM overclocking: its own switch, independent of modes and super performance
        self.assertEqual(self.post("setting", {"key": "mem_oc", "value": True})[0], 200)
        self.assertEqual(self.get("nvram")["MemoryOverClockSwitch"], 1)
        st = self.get("state")["settings"]
        self.assertEqual((st["mem_oc"], st["mem_oc_pending"]), (True, True))
        self.assertEqual(self.post("mode", {"mode": 1})[0], 200)
        self.assertEqual(self.get("nvram")["MemoryOverClockSwitch"], 1)      # mode change leaves it alone
        self.assertEqual(self.post("setting", {"key": "mem_oc", "value": False})[0], 200)
        self.assertEqual(self.get("nvram")["MemoryOverClockSwitch"], 0)
        self.assertFalse(self.get("state")["settings"]["mem_oc_pending"])

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
        self.assertTrue(all(n.startswith(("report.", "uwccd.log", "acpi/", "oem/", "selfcheck.json")) for n in z.namelist()))
        rep = json.loads(z.read("report.json"))
        self.assertEqual(rep["private_included"], ["mac"])
        # 1.6.4: self-check stage 1 (read only) is part of the report by default
        self.assertEqual(rep["selfcheck"]["stage"], 1, rep["selfcheck"])
        self.assertTrue(rep["selfcheck"]["items"])
        sc = json.loads(z.read("selfcheck.json"))
        self.assertEqual(sc["result"]["stage"], 1)
        self.assertIn("draft_profile", sc)
        self.assertIn("self-check, stage 1 (read only)", z.read("report.txt").decode())
        self.assertTrue(self.get("ec-access")["selfcheck"]["stage1_done"])
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


class FanTableBackgroundUnit(unittest.TestCase):
    """WMI path: the fan curve is written in the background with progress; an identical curve is not written again."""

    def test_deferred_progress_and_skip(self):
        from uwccd.busy import Busy
        from uwccd.ec import MockEC
        from uwccd.fan import FanTables, empty_table

        class Pf:
            nv_gpu, project_name = True, "test"

        class CountEC(MockEC):
            writes = 0

            def _write(self, a, v):
                CountEC.writes += 1
                time.sleep(0.002)
                super()._write(a, v)

        events = []
        busy = Busy(lambda kind, data: events.append((kind, [dict(o) for o in data["ops"]])))
        ec = CountEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        ft = FanTables(ec, Pf())
        ft.busy, ft.deferred = busy, True
        t = empty_table("M1T1")
        for i, (u, d, du) in enumerate([(0, 48, 20), (55, 50, 40), (70, 65, 70), (85, 80, 100)]):
            for k in ("CPU", "GPU"):
                t[k][i].update(UpT=u, DownT=d, Duty=du)
        t0 = time.monotonic()
        ft.apply_table(t)
        self.assertLess(time.monotonic() - t0, 0.05)              # returns at once
        self.assertTrue(ft.wait_idle(10))
        first = CountEC.writes
        self.assertGreater(first, 90)
        ops = [o for kind, lst in events for o in lst if o["op"] == "fan_table"]
        self.assertTrue(ops and not ops[0]["blocking"])
        self.assertEqual(max(o["progress"] or 0 for o in ops), 100)
        self.assertEqual(events[-1][1], [])                         # finished
        ft.apply_table(t)                                           # same curve, still active -> skipped
        ft.wait_idle(10)
        self.assertLess(CountEC.writes - first, 3)
        ft.invalidate()                                             # e.g. after resume -> written again
        ft.apply_table(t)
        ft.wait_idle(10)
        self.assertGreater(CountEC.writes - first, 90)


class EditionUnit(unittest.TestCase):
    def test_update_asset_matches_edition(self):
        from uwccd import updates
        assets = {"open-uniwill-cc-windows-1.6.1-setup.exe": "full", "open-uniwill-cc-windows-1.6.1-free-setup.exe": "free"}
        for ed in ("full", "free"):
            os.environ["UWCC_EDITION"] = ed
            try:
                self.assertEqual(updates._setup_asset(assets), ed)
            finally:
                os.environ.pop("UWCC_EDITION", None)
        from uwccd import edition
        self.assertEqual(edition(), "source")


class DriverCheckUnit(unittest.TestCase):
    def _pkg(self):
        d = tempfile.mkdtemp()
        src = os.path.join(ROOT, "proprietary", "driver")
        if not os.path.isdir(src):
            self.skipTest("proprietary/driver is not in this checkout")
        import shutil
        for f in os.listdir(src):
            shutil.copy(os.path.join(src, f), d)
        return d

    def test_levels(self):
        from uwccd import drivercheck as dc
        d = self._pkg()
        r = dc.verify(d)
        self.assertEqual((r["level"], r["version"]), ("ok", "17.53.43.609"))
        self.assertTrue(dc.allowed(r))
        with open(os.path.join(d, "UWACPIDriver.sys"), "ab") as f:
            f.write(b"x")
        r = dc.verify(d)
        self.assertEqual(r["level"], "warn")
        self.assertFalse(dc.allowed(r))
        self.assertTrue(dc.allowed(r, accept_risks=True))
        inf = os.path.join(d, "UWACPIDriver.inf")
        with open(inf, "rb") as f:
            data = f.read()
        with open(inf, "wb") as f:
            f.write(data.replace(b"INOU0000", b"ABCD0000"))
        r = dc.verify(d)
        self.assertEqual(r["level"], "hard")
        self.assertFalse(dc.allowed(r, accept_risks=True))           # another device: never
        os.remove(os.path.join(d, "uwacpidriver.cat"))
        self.assertEqual(dc.verify(d)["level"], "hard")
        self.assertEqual(dc.main([d]), 12)


class MarkdownHelpUnit(unittest.TestCase):
    def test_docs_exist(self):
        for f in ("EC/Platforms.md", "EC/Platforms.ru.md", "EC/OEM-driver.md", "EC/OEM-driver.ru.md", "EC/WMI-config.md",
                  "EC/WMI-vs-Driver.md", "EC/Registers.md", "EC/README.md", "FEATURES.md", "CLI.md", "CLI.ru.md",
                  "LIGHTING.md", "LIGHTING.ru.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "docs", f)), f)


class SnapshotUnit(unittest.TestCase):
    def test_restore_snapshot(self):
        from uwccd import selfcheck, store
        from uwccd.ec import MockEC
        d = tempfile.mkdtemp()
        old = store.DATA_DIR
        store.DATA_DIR = d
        try:
            ec = MockEC(os.path.join(d, "ec.json"))
            ec.write(0x783, 99)
            store.save_json(store.path(selfcheck.SNAPSHOT), {"regs": {"0x783": 40, "0x74E": 0x10}})
            self.assertTrue(selfcheck.restore_snapshot(ec))
            self.assertEqual((ec.read(0x783), ec.read(0x74E)), (40, 0x10))
            self.assertFalse(os.path.exists(store.path(selfcheck.SNAPSHOT)))
            self.assertFalse(selfcheck.restore_snapshot(ec))
        finally:
            store.DATA_DIR = old


class PlatformDbUnit(unittest.TestCase):
    def test_profiles_and_caps(self):
        from uwccd import platformdb
        p = platformdb.match(0x10)
        self.assertEqual((p["profile"]["id"], p["source"]), ("uniwill-0x10", "builtin"))
        self.assertTrue(platformdb.match(0x77).get("fallback"))
        with self.assertRaises(ValueError):
            platformdb.check_limits({"PL4": 301})
        with self.assertRaises(ValueError):
            platformdb.check_limits({"PL1": 170, "PL4": 250}, 0x10)          # above the factory 160
        self.assertEqual(platformdb.check_limits({"PL1": 120, "PL4": 250}, 0x10)["PL1"], 120)
        v = platformdb.validate({"id": "x-1", "status": "verified", "match": {"project": ["0x22"]}, "limits": {"PL4": 200}})
        self.assertEqual(v["status"], "community")                             # only built-in profiles are verified
        with self.assertRaises(ValueError):
            platformdb.validate({"id": "Bad Id", "match": {"project": ["0x22"]}})


class SingleColorKeyboardUnit(unittest.TestCase):
    def test_project_0x1a_uses_ec_single_colour(self):
        """MECHREVO Kuangshi / Jiguang B2 (Aurora X): no ITE device, EC 0x78C single-colour backlight"""
        from uwccd.ec import MockEC
        from uwccd.lighting import ite, keyboard
        ec = MockEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        ec.write(0x78C, 0x80)

        class Pf:
            project_id = 0x1A

        class St(dict):
            def set(self, k, v):
                self[k] = v
        orig = ite.open_keyboard
        ite.open_keyboard = lambda ec, mock=False: None
        try:
            kb = keyboard.KeyboardManager(ec, Pf(), St(), mock=False)
            kb.lb = None
            orig_lb = ite.open_lightbar
            ite.open_lightbar = lambda ec, mock=False: None
            try:
                kb.start()
            finally:
                ite.open_lightbar = orig_lb
        finally:
            ite.open_keyboard = orig
        self.assertEqual(kb.kind, "single")
        self.assertEqual(kb.status()["level"], 4)
        kb.set_level(2)
        self.assertEqual(ec.read(0x78C), 0x50)
        kb.set_power(False)
        self.assertTrue(ec.read(0x78C) & 0x02)


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


class KeyboardTimingUnit(unittest.TestCase):
    def _kb(self, kb_type, ver=(0x11, 5, 0, 0)):
        from uwccd.ec import MockEC
        from uwccd.lighting import ite
        ec = MockEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        k = ite.MockITE(ec)
        k.ver, k.kb_type = ver, kb_type
        return k, ec, ite

    def test_per_key_keyboard(self):
        k, ec, _ = self._kb(5)
        k.set_effect(0, light=1, colors=[(0, 255, 0)])
        self.assertEqual(k.log[0], ("F", "000805000000000000"))   # reset first, as ILM_RGBKB_SetEffectALL
        self.assertEqual(k.log[1], ("F", "000802330008000000"))   # single colour as a 12h picture
        n = len(k.log)
        k.set_effect(0, light=1, colors=[(0, 255, 0)])            # double click: dropped
        self.assertEqual(len(k.log), n)
        k.set_effect(12, light=1, colors=[(0, 255, 0)])           # Aurora: EC passes key presses
        self.assertTrue(ec.read(0x741) & 0x08)

    def test_four_zone_keyboard(self):
        k, ec, ite = self._kb(2)                                  # MAIBENBEN Tsunami: ITE CE00, usage page FF12
        k.set_effect(0, light=1, colors=[(0, 255, 0)])
        pal = [v for f, v in k.log if v.startswith("0014")]
        self.assertEqual(len(pal), 7)                             # the colour in every palette slot ...
        self.assertTrue(k.log[-1][1].startswith("0008020105080801"))   # ... and colour argument 8
        with self.assertRaises(ValueError):
            k.set_effect(14)                                      # User mode: per-key picture, not on FF12
        with self.assertRaises(ValueError):
            k.set_effect(12)                                      # Aurora: not offered for FourZone by the original
        for idx in (7, 16):                                       # Neon (blended frames), Flash (fading)
            k.log.clear()
            k.set_effect(idx, light=1, speed=4)
            time.sleep(0.3)
            k.stop_ap()
            self.assertGreater(sum(1 for f, v in k.log if v.startswith("0014")), 8, idx)
            self.assertFalse(any(v.startswith("00080212") for f, v in k.log))   # no firmware Flash
        k.set_effect(26, light=1, speed=2)                        # Colour wave: drawn zone by zone by the service
        time.sleep(0.3)
        k.stop_ap()
        zones = [v for f, v in k.log if v.startswith("0014")][-4:]
        self.assertEqual([v[6:8] for v in zones], ["01", "02", "03", "04"])
        self.assertTrue(k.log[-1][1].startswith("000802010008"))   # static effect, colour argument 8


class FxUnit(unittest.TestCase):
    """BetterRGB effects (uwccd/lighting/fx.py)"""

    def test_every_effect_draws_valid_frames(self):
        from uwccd.lighting import fx
        for idx in fx.EFFECTS:
            e = fx.make(idx, {})
            for i in range(40):
                if "keys" in e.needs:
                    e.press(fx.cell_of("J"), time.monotonic())
                if "screen" in e.needs:
                    e.feed((8, 4, bytes([200, 30, 10]) * 32))
                f = e.frame(i / 30.0, 1.0)
                self.assertEqual(len(f), 126, idx)
                for c in f:
                    self.assertEqual(len(c), 3)
                    self.assertTrue(all(0.0 <= v <= 4.0 for v in c), (idx, c))      # > 1 is clipped on output

    def test_params_are_cleaned(self):
        from uwccd.lighting import fx
        p = fx.clean_params(107, {"speed": 99, "density": "x", "colors": [[300, -1, 5], "bad"], "nope": 1})
        self.assertEqual((p["speed"], p["density"], p["colors"]), (10, 3, [[255, 0, 5]]))
        self.assertNotIn("nope", p)
        self.assertEqual(fx.clean_params(108, {"style": "lasers"})["style_i"], 2)
        self.assertEqual(fx.clean_params(108, {"style": "bogus"})["style"], "streaks")

    def test_key_map_anchors(self):
        from uwccd.lighting import fx
        # GCUService gaming zones: W/A/S/D = 0x2D/0x41/0x42/0x43, arrows = 0x62/0x76/0x77/0x78
        for name, cell in (("W", 0x2D), ("A", 0x41), ("S", 0x42), ("D", 0x43), ("Up", 0x62), ("Left", 0x76),
                           ("Down", 0x77), ("Right", 0x78)):
            self.assertEqual(fx.cell_of(name), cell, name)
        self.assertEqual(fx.EVDEV[17], "W")
        self.assertEqual(fx.VK[0x57], "W")
        self.assertTrue(all(fx.cell_of(n) is not None for n in fx.EVDEV.values()))
        self.assertTrue(all(fx.cell_of(n) is not None for n in fx.VK.values()))

    def test_transitions_bar_gains_zones(self):
        from uwccd.lighting import fx
        for mode in fx.TRANSITIONS:
            self.assertEqual(fx.coverage(mode, 1.0), [1.0] * 126, mode)
            if mode != "off":
                self.assertEqual(max(fx.coverage(mode, 0.0)), 0.0, mode)
        full = [(1.0, 1.0, 1.0)] * 126
        half = fx.bar_overlay(full, 0.5, "cpu", fx.BAR_DEFAULT, 0.0)
        lit = [max(half[c]) > 0.01 for c in fx.BAR_KEYS]
        self.assertEqual(lit[:9], [True] * 9)
        self.assertEqual(lit[11:], [False] * 9)
        self.assertEqual(half[30], (1.0, 1.0, 1.0))                     # other rows keep the effect

        g = fx.white_gains([255, 255, 200])
        self.assertTrue(g[2] == 1000 and g[0] < 1000 and g[0] == g[1])
        self.assertIsNone(fx.white_gains([0, 0, 0]))
        z = fx.zones_linear([(0.5, 0.0, 0.0)] * 126)
        self.assertEqual(len(z), 4)
        self.assertAlmostEqual(z[0][0], 0.5)
        c = fx.clean_config({"fps_ac": 500, "transition": "x", "gains": [10, 2000], "bar": {"mode": "cpu", "start": "bad"}})
        self.assertEqual((c["fps_ac"], c["transition"], c["gains"], c["bar"]["mode"], c["bar"]["start"]),
                         (60, "fade", [50, 1000, 1000], "cpu", [0, 255, 80]))
        img = fx.decode_screen({"w": 8, "h": 4, "rgb": __import__("base64").b64encode(bytes(96)).decode()})
        self.assertEqual(img[:2], (8, 4))
        with self.assertRaises(ValueError):
            fx.decode_screen({"w": 8, "h": 4, "rgb": ""})

    def test_engine_on_mock_keyboard(self):
        from uwccd.ec import MockEC
        from uwccd.lighting import fx, ite
        ec = MockEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        kb = ite.MockITE(ec)
        kb.fx_env = lambda: {"config": fx.clean_config({"transition_ms": 200}), "ac": True, "metrics": {}}
        kb.set_effect(110, light=2, fx={"speed": 8})
        e = kb.fx()
        self.assertIsNotNone(e)
        self.assertEqual(e.needs(), ["keys"])
        e.press(["J", "nosuchkey"])
        time.sleep(0.5)
        self.assertGreater(e.frames, 3)
        pkts = [v for f, v in kb.log if f == "F"]
        self.assertIn("000802330016000000", pkts)                       # 08h user mode, light 2 = 0x16
        self.assertIn("001200000800000000", pkts)                       # 12h picture
        e.set_idle(True)
        time.sleep(0.5)
        self.assertEqual(e.idle, "asleep")
        e.set_idle(False)
        time.sleep(0.5)
        self.assertEqual(e.idle, "active")
        kb.set_power(False)
        self.assertIsNone(kb.ap)
        kb.set_power(True)
        self.assertIsNotNone(kb.fx())
        self.assertEqual(kb.saved["fx"]["speed"], 8)
        kb.set_effect(4)                                                  # firmware effect stops the engine
        self.assertIsNone(kb.ap)
        kb.kb_type = 2                                                    # four-zone keyboard: zone colours
        kb.set_effect(111, light=4)
        time.sleep(0.3)
        self.assertTrue(any(f == "F" and v.startswith("0014") for f, v in kb.log))
        kb.stop_ap()


class DetectUnit(unittest.TestCase):
    def test_usage_page_types(self):
        from uwccd.ec import MockEC
        from uwccd.lighting import ite
        ec = MockEC(os.path.join(tempfile.mkdtemp(), "ec.json"))
        for up, project, want in ((0xFF12, 0x10, 2), (0xFF12, 0x11, 3), (0xFF02, 0x10, 4)):
            k = ite.MockITE(ec)
            k.usage_page, k.project = up, project
            k.firmware_version = lambda: (0x11, 5, 0, 0)
            k._detect()
            self.assertEqual(k.kb_type, want, hex(up))


if __name__ == "__main__":
    unittest.main()
