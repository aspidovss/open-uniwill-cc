"""Temperature lighting tests without hardware (Windows and Linux)."""
import math
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from uwccd.lighting import fx
from uwccd.service import Service


class TemperatureEffect(unittest.TestCase):
    def make(self, **params):
        self.assertTrue(fx.is_fx(116), "temperature effect must be registered")
        return fx.make(116, {"smoothing_ms": 0, **params})

    def test_split_and_swap(self):
        for left in ("cpu", "gpu"):
            e = self.make(left=left)
            e.update_metrics({"cpu_temp": 40, "gpu_temp": 85})
            frame = e.frame(0, 1)
            self.assertEqual(len(frame), 126)
            for row in range(6):
                for col in range(21):
                    cpu = (col < 10) == (left == "cpu")
                    rgb = tuple(fx.l2s(v) for v in frame[row * 21 + col])
                    self.assertEqual(rgb, (0, 180, 255) if cpu else (255, 0, 0))

    def test_independent_thresholds_and_clamping(self):
        e = self.make(cpu_points=[{"temp": 20, "color": [0, 180, 255]}, {"temp": 30, "color": [0, 255, 80]}])
        e.update_metrics({"cpu_temp": 30, "gpu_temp": 30})
        f = e.frame(0, 1)
        self.assertEqual(tuple(fx.l2s(v) for v in f[0]), (0, 255, 80))
        self.assertEqual(tuple(fx.l2s(v) for v in f[20]), (0, 180, 255))
        e.update_metrics({"cpu_temp": 110, "gpu_temp": 120})
        f = e.frame(1, 1)
        self.assertEqual(tuple(fx.l2s(v) for v in f[0]), (0, 255, 80))
        self.assertEqual(f[20], (1.0, 0.0, 0.0))

    def test_interpolation_in_linear_light(self):
        e = self.make(cpu_points=[{"temp": 85, "color": [255, 100, 0]}, {"temp": 95, "color": [255, 0, 0]}])
        e.update_metrics({"cpu_temp": 90})  # halfway between orange at 85 and red at 95
        f = e.frame(0, 1)
        self.assertEqual(f[0][0], 1.0)
        self.assertAlmostEqual(f[0][1], 0.06371884021782372)
        self.assertEqual(f[0][2], 0.0)
        self.assertEqual(f[20], (0.0, 0.0, 0.0))

    def test_missing_invalid_and_returning_sensor(self):
        e = self.make(smoothing_ms=1000)
        for invalid in (None, float("nan"), float("inf"), -1, 151, 10 ** 400, True, "55"):
            e.update_metrics({"cpu_temp": invalid, "gpu_temp": 85})
            f = e.frame(0, 1)
            self.assertEqual(f[0], (0.0, 0.0, 0.0))
            self.assertEqual(f[20], (1.0, 0.0, 0.0))
        e.update_metrics({"cpu_temp": 95})
        self.assertEqual(e.frame(1, 1)[0], (1.0, 0.0, 0.0))
        e.update_metrics({})
        self.assertEqual(e.frame(2, 1), [(0.0, 0.0, 0.0)] * 126)

    def test_smoothing_uses_elapsed_seconds(self):
        results = []
        for fps in (10, 30, 60):
            e = self.make(smoothing_ms=1000)
            e.update_metrics({"cpu_temp": 40})
            e.frame(0, 1)
            e.update_metrics({"cpu_temp": 95})
            for i in range(1, fps + 1):
                frame = e.frame(i / fps, 30 / fps)
            results.append(frame[0])
        for c in results:
            self.assertAlmostEqual(c[0], 1 - math.exp(-1))
            self.assertAlmostEqual(c[2], math.exp(-1))

    def test_parameter_validation(self):
        self.make()
        bad_points = [[], [{"temp": 40, "color": [0, 0, 0]}],
                      [{"temp": 40, "color": [0, 0, 0]}, {"temp": 40, "color": [255, 255, 255]}],
                      [{"temp": 60, "color": [0, 0, 0]}, {"temp": 40, "color": [255, 255, 255]}],
                      [{"temp": i, "color": [0, 0, 0]} for i in range(16)],
                      [{"temp": float("nan"), "color": [0, 0, 0]}, {"temp": 90, "color": [255, 255, 255]}],
                      [{"temp": 10 ** 400, "color": [0, 0, 0]}, {"temp": 90, "color": [255, 255, 255]}],
                      [{"temp": 30, "color": [256, 0, 0]}, {"temp": 90, "color": [255, 255, 255]}],
                      [{"temp": True, "color": [0, 0, 0]}, {"temp": 90, "color": [255, 255, 255]}]]
        for points in bad_points:
            params = {"cpu_points": points}
            with self.subTest(params=params), self.assertRaises(ValueError):
                fx.clean_params(116, params)
        for invalid in ("bad", None, float("inf"), float("nan")):
            p = fx.clean_params(116, {"smoothing_ms": invalid})
            self.assertEqual(p["smoothing_ms"], 1000)
        p = fx.clean_params(116, {"left": "bad", "smoothing_ms": -1, "unknown": 9})
        self.assertEqual((p["left"], p["smoothing_ms"]), ("cpu", 0))
        self.assertNotIn("unknown", p)

    def test_custom_palette_and_fifteen_points(self):
        points = [{"temp": i * 8, "color": [i * 17, 0, 255 - i * 17]} for i in range(15)]
        e = self.make(cpu_points=points)
        e.update_metrics({"cpu_temp": 56})
        self.assertEqual(tuple(fx.l2s(v) for v in e.frame(0, 1)[0]), (119, 0, 136))
        e.update_metrics({"cpu_temp": 120})
        self.assertEqual(tuple(fx.l2s(v) for v in e.frame(1, 1)[0]), (238, 0, 17))

    def test_defaults_have_fifteen_colours_over_40_to_85_for_both_sensors(self):
        p = fx.clean_params(116, {})
        self.assertEqual(p["cpu_points"], p["gpu_points"])
        self.assertEqual([point["temp"] for point in p["cpu_points"]],
                         [40, 43, 46, 50, 53, 56, 59, 62, 66, 69, 72, 75, 79, 82, 85])
        self.assertEqual(len({tuple(point["color"]) for point in p["cpu_points"]}), 15)
        e = self.make()
        e.update_metrics({"cpu_temp": 40, "gpu_temp": 85})
        f = e.frame(0, 1)
        self.assertEqual(tuple(fx.l2s(v) for v in f[0]), (0, 180, 255))
        self.assertEqual(f[20], (1.0, 0.0, 0.0))

    def test_cli_parses_and_displays_temperature_points(self):
        import runpy
        cli = runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "uwccctl"))
        spec = fx.catalog()[116]
        got = cli["fx_params"](spec, ["cpu_points=40:00B4FF,95:FF0000", "left=gpu"])
        self.assertEqual(got, {"cpu_points": [{"temp": 40, "color": [0, 180, 255]},
                                               {"temp": 95, "color": [255, 0, 0]}], "left": "gpu"})
        text = cli["fx_text"]({"fx_effects": {"116": spec}})[0]
        self.assertIn("cpu_points=TEMP:RRGGBB,...", text)

    def test_engine_receives_service_metrics(self):
        self.make()
        wrote = threading.Event()
        pictures = []

        def capture(picture, light, announce):
            pictures.append(picture)
            wrote.set()

        kb = SimpleNamespace(four_zone=lambda: False, write_picture=capture)
        env = {"config": fx.clean_config({"transition": "off"}), "ac": True,
               "metrics": {"cpu_temp": 95, "gpu_temp": 35}}
        engine = fx.FxEngine(kb, 116, 4, {"smoothing_ms": 0}, lambda: env)
        engine.start()
        try:
            self.assertTrue(wrote.wait(2), "engine must send a frame")
            self.assertEqual(pictures[0][0], (255, 0, 0))
            self.assertEqual(pictures[0][20], (0, 180, 255))
            self.assertEqual(engine.info()["temperatures"], {"cpu": 95, "gpu": 35})
        finally:
            engine.stop()
            engine.join(2)

    def test_saved_parameters_survive_power_cycle(self):
        from uwccd.ec import MockEC
        from uwccd.lighting.ite import MockITE
        with tempfile.TemporaryDirectory() as tmp:
            kb = MockITE(MockEC(os.path.join(tmp, "ec.json")))
            try:
                points = [{"temp": 20, "color": [0, 255, 255]}, {"temp": 100, "color": [255, 0, 0]}]
                kb.set_effect(116, light=2, fx={"left": "gpu", "cpu_points": points, "smoothing_ms": 500})
                saved = dict(kb.saved)
                kb.set_power(False)
                self.assertIsNone(kb.fx())
                kb.set_power(True)
                self.assertEqual(kb.saved, saved)
                self.assertEqual(kb.fx().params["cpu_points"], points)
                with self.assertRaises(ValueError):
                    kb.set_effect(116, fx={"cpu_points": points[::-1]})
                self.assertEqual(kb.saved, saved)
            finally:
                kb.stop_ap()

    def test_four_zone_output_blends_the_boundary_zone(self):
        self.make()
        wrote = threading.Event()
        zones = []

        def capture(colors, light, announce):
            zones.extend(colors)
            wrote.set()

        kb = SimpleNamespace(four_zone=lambda: True, write_zones=capture)
        env = {"config": fx.clean_config({"transition": "off"}), "ac": True,
               "metrics": {"cpu_temp": 95, "gpu_temp": 35}}
        engine = fx.FxEngine(kb, 116, 4, {}, lambda: env)
        engine.start()
        try:
            self.assertTrue(wrote.wait(2))
            self.assertEqual(zones[0], (255, 0, 0))
            self.assertEqual(zones[3], (0, 180, 255))
            self.assertTrue(0 < zones[1][0] < 255 and 0 < zones[1][2] < 255)
        finally:
            engine.stop()
            engine.join(2)


class TemperatureMetrics(unittest.TestCase):
    def service(self, level="full", age=0, sample_level=None):
        s = Service.__new__(Service)
        s.sampler = SimpleNamespace(latest={"t": time.time() - age, "monitoring": sample_level or level,
                                           "cpu": {"temp": 55, "usage": 10}, "gpu": {"temp": 45}},
                                    current_interval=lambda: 2.0, LIGHT_S=20.0)
        s.monitor_level = lambda: level
        s.monitor = SimpleNamespace(battery=lambda: None)
        return s

    def test_fresh_full_and_light_samples(self):
        for level, age in (("full", 3), ("light", 25)):
            with self.subTest(level=level):
                m = self.service(level, age)._fx_metrics()
                self.assertEqual((m.get("cpu_temp"), m.get("gpu_temp")), (55, 45))

    def test_off_stale_and_previous_mode_do_not_report_temperatures(self):
        for level, age, sample_level in (("off", 0, "full"), ("full", 7, "full"),
                                          ("light", 61, "light"), ("light", 0, "full")):
            with self.subTest(level=level, age=age, sample_level=sample_level):
                m = self.service(level, age, sample_level)._fx_metrics()
                self.assertIsNone(m.get("cpu_temp"))
                self.assertIsNone(m.get("gpu_temp"))

    def test_expiry_without_new_sample_and_sleeping_gpu(self):
        s = self.service()
        s.sampler.latest["gpu"] = {"asleep": True}
        now = time.time()
        with patch("uwccd.service.time.time", return_value=now):
            self.assertEqual(s._fx_metrics().get("cpu_temp"), 55)
            self.assertIsNone(s._fx_metrics().get("gpu_temp"))
        with patch("uwccd.service.time.time", return_value=now + 7):
            self.assertIsNone(s._fx_metrics().get("cpu_temp"))


if __name__ == "__main__":
    unittest.main()
