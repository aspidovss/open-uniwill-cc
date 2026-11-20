"""1.9.2.1: /api/state with a hanging part, the watchdog (stack dump, restart), nvidia-smi error lines."""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uwccd import stateguard as G  # noqa: E402


class Guard(unittest.TestCase):
    def test_hanging_part_is_sent_stale(self):
        g = G.PartGuard(timeout=0.2)
        release = threading.Event()
        calls = []

        def slow():
            calls.append(1)
            if len(calls) > 1:
                release.wait(5)
            return {"v": len(calls)}

        out, stale = g.build({"fast": lambda: 1, "slow": slow})
        self.assertEqual((out, stale), ({"fast": 1, "slow": {"v": 1}}, []))
        t0 = time.time()
        out, stale = g.build({"fast": lambda: 2, "slow": slow})          # hangs: the last value, after the limit
        self.assertEqual((out["fast"], out["slow"], stale), (2, {"v": 1}, ["slow"]))
        self.assertLess(time.time() - t0, 2)
        t0 = time.time()
        out, stale = g.build({"fast": lambda: 3, "slow": slow})          # still stuck: not waited for again
        self.assertEqual(stale, ["slow"])
        self.assertLess(time.time() - t0, 0.15)
        self.assertGreater(g.oldest()[0], 0)
        self.assertEqual(g.oldest()[1], "state part slow")
        release.set()
        time.sleep(0.1)
        out, stale = g.build({"fast": lambda: 4, "slow": lambda: "back"})
        self.assertEqual((out["slow"], stale), ("back", []))

    def test_errors_still_raise(self):
        g = G.PartGuard(timeout=1)
        with self.assertRaises(ZeroDivisionError):
            g.build({"bad": lambda: 1 / 0})

    def test_watchdog_dumps_then_restarts(self):
        g = G.PartGuard()
        restarted = []
        w = G.Watchdog(g, restarted.append, dump_after=30, restart_after=180)
        self.assertIsNone(w.check())
        key = g.enter()
        g.inflight[id(key)] = time.time() - 40
        with self.assertLogs("uwccd.watchdog", "ERROR") as cm:
            self.assertEqual(w.check(), "dump")
        self.assertIn("stacks of all threads", cm.output[0])
        self.assertIn("--- thread", cm.output[0])
        self.assertIsNone(w.check())                                     # dumped once per hang
        g.inflight[id(key)] = time.time() - 200
        with self.assertLogs("uwccd.watchdog", "ERROR"):
            self.assertEqual(w.check(), "restart")
        self.assertEqual(restarted, ["hung: /api/state request"])
        self.assertIsNone(w.check())                                     # restarted once
        g.leave(key)
        self.assertEqual(g.oldest(), (0.0, None))

    def test_watchdog_without_restart(self):                         # --mock: dump only
        g = G.PartGuard()
        key = g.enter()
        g.inflight[id(key)] = time.time() - 500
        w = G.Watchdog(g, None)
        with self.assertLogs("uwccd.watchdog", "ERROR"):
            self.assertEqual(w.check(), "dump")
        self.assertIsNone(w.check())


class NvidiaSmi(unittest.TestCase):
    def test_error_line(self):
        """nvidia-smi printing an error instead of the CSV line (seen on 2026-11-20) gives no GPU data, no crash."""
        from unittest import mock
        from uwccd import monitor
        mon = monitor.Monitor.__new__(monitor.Monitor)
        mon._nv_cache = (0, None)
        res = mock.Mock(stdout="Unable to determine the device handle for GPU0000:01:00.0: Unknown Error\n")
        with mock.patch.object(monitor.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
                mock.patch.object(monitor.subprocess, "run", return_value=res), \
                mock.patch.object(monitor.os.path, "exists", return_value=False), \
                mock.patch.object(monitor, "dgpu_state", return_value=None):
            self.assertIsNone(mon.nvidia())


if __name__ == "__main__":
    unittest.main()
