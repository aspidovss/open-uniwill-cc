"""A constant active picture must not leave a USB keyboard idle long enough to suspend."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from uwccd.lighting import fx


class Keyboard:
    pictures_ok = True

    def __init__(self):
        self.writes = []

    def four_zone(self):
        return False

    def write_picture(self, colors, light, announce=True):
        self.writes.append((list(colors), light, announce))


class FrameKeepalive(unittest.TestCase):
    def engine(self):
        kb = Keyboard()
        engine = fx.FxEngine(kb, 116, 4, {}, lambda: {"config": fx.clean_config(None), "ac": True, "metrics": {}})
        return kb, engine

    def test_constant_picture_is_refreshed_without_restarting_effect(self):
        kb, engine = self.engine()
        frame = [(0.0, 1.0, 0.0)] * fx.N
        with patch.object(fx.time, "monotonic", return_value=10.0) as clock:
            engine.send(frame, True)
            clock.return_value = 10.5
            engine.send(frame, False)
            self.assertEqual(len(kb.writes), 1)
            for second in range(11, 17):
                clock.return_value = float(second)
                engine.send(frame, False)
                self.assertEqual(len(kb.writes), second - 9)
        self.assertTrue(kb.writes[0][2])
        self.assertTrue(all(not item[2] for item in kb.writes[1:]))
        self.assertTrue(all(item[:2] == kb.writes[0][:2] for item in kb.writes))

    def test_missing_temperatures_keep_refreshing_the_held_color(self):
        kb, engine = self.engine()
        engine.effect.update_metrics({"cpu_temp": 60, "gpu_temp": 50})
        with patch.object(fx.time, "monotonic", return_value=10.0) as clock:
            engine.send(engine.effect.frame(0, 1), True)
            expected = kb.writes[-1][0]
            engine.effect.update_metrics({})
            for second in range(1, 7):
                clock.return_value = 10.0 + second
                engine.send(engine.effect.frame(second, 1), False)
        self.assertEqual(len(kb.writes), 7)
        self.assertTrue(all(item[0] == expected for item in kb.writes))
        self.assertEqual(engine.effect.status()["temperatures"], {"cpu": None, "gpu": None})

    def test_sleeping_engine_sends_no_keepalive(self):
        kb, engine = self.engine()
        now = [10.0]
        engine.idle = "asleep"
        engine.last_out = [(0, 0, 0)] * fx.N
        engine.last_sent = 10.0
        def wait(seconds):
            now[0] += max(.01, seconds)
        engine._halt = SimpleNamespace(is_set=lambda: now[0] >= 12.0, wait=wait)
        with patch.object(fx.time, "monotonic", side_effect=lambda: now[0]):
            engine.run()
        self.assertEqual(kb.writes, [])


if __name__ == "__main__":
    unittest.main()
