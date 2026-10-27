"""Self-check of the EC access (EC Manager): what works on this laptop, and what is not clear.

Stage 1 — read only, safe:
    identity (project ID, BIOS project, EC / BIOS versions) and the matching platform profile;
    which access paths exist (OEM driver, WMI) and, when both do, a byte-by-byte comparison of the same registers;
    plausibility of known registers (mode byte, factory power limits, fans, battery), time per EC access;
    firmware methods found in the ACPI tables (WMBC / RKBC / WKBC / SMRW / PWUP ...).
Stage 2 — writes with read-back and restore (administrator, on AC power only):
    every function is switched a little and back: Fn Lock, touchpad flag, mode byte, Fan Boost (do the fans react?),
    PL1, cTGP target, charge limit, the fan-table handshake. The registers are saved first
    (<data>/selfcheck-snapshot.json); if the service stops in the middle, it restores them on the next start.
    At the end the current mode profile is applied again.
Result: every check with its status and evidence, the list of what is not clear, and a draft platform profile that
can be exported for GitHub or applied as this laptop's profile (administrator).
"""
import logging
import os
import sys
import threading
import time

from . import platformdb, store
from . import regs as R

log = logging.getLogger("uwccd.selfcheck")

SNAPSHOT = "selfcheck-snapshot.json"
LAST = "selfcheck-last.json"
# stable registers compared between the OEM driver and WMI (no fan speeds / temperatures)
COMPARE = [0x740, 0x74C, 0x741, 0x742, 0x73C, 0x766, 0x771, 0x772, 0x782, 0x78E, 0x7A4, 0x7C8, 0x7CA, 0x7D2, 0x7D3,
           0x730, 0x731, 0x732, 0x734, 0x735, 0x736, 0x7A7, 0x7A8, 0x7A9, 0x751, 0x783, 0x784, 0x785, 0x786,
           0x74E, 0x7A6, 0x7B9, 0x7D0, 0x744]
SNAP_REGS = [0x74E, 0x7A6, 0x7B9, 0x751, 0x783, 0x784, 0x785, 0x743, 0x744, 0x726]
FIRMWARE_NAMES = ("WMBC", "OEMG", "RKBC", "WKBC", "ECRR", "ECRW", "SMRW", "PWUP")
KNOWN_MODE_BYTES = (0x00, 0x10, 0x80, 0xA0, 0x20)


def _item(iid, group, name, status, detail=""):
    return {"id": iid, "group": group, "name": name, "status": status, "detail": detail}


def restore_snapshot(ec):
    """Service start: a stage-2 check did not finish — put the saved registers back."""
    p = store.path(SNAPSHOT)
    snap = store.load_json(p)
    if not snap:
        return False
    try:
        for a, v in (snap.get("regs") or {}).items():
            ec.write(int(a, 16), int(v))
        log.warning("self-check was interrupted — %d registers restored", len(snap.get("regs") or {}))
    except Exception as e:  # noqa: BLE001
        log.error("restore after an interrupted self-check: %s", e)
    try:
        os.remove(p)
    except OSError:
        pass
    return True


class SelfCheck:
    def __init__(self, svc):
        self.svc = svc
        self.lock = threading.Lock()
        self.running = None
        self.last = store.load_json(store.path(LAST))

    # -- helpers ---------------------------------------------------------------------------------
    @staticmethod
    def rd(ec, a):
        f = getattr(ec, "_read", None)
        return (f(a) if f else ec.read(a)) & 0xFF

    def wr(self, a, v):
        ec = self.svc.ec
        ec.write(a, v & 0xFF)
        inv = getattr(ec, "invalidate", None)
        if inv:
            inv()

    def _progress(self, pct, label=None):
        self.svc.busy.progress("selfcheck", pct, label)

    def summary(self):
        r = self.last or {}
        counts = {}
        for it in r.get("items", []):
            counts[it["status"]] = counts.get(it["status"], 0) + 1
        return {"running": self.running,
                "last": {"time": r.get("time"), "stage": r.get("stage"), "path": r.get("path"), "counts": counts,
                         "unknowns": len(r.get("unknowns", []))} if r else None}

    # -- run -------------------------------------------------------------------------------------
    def start(self, stage):
        with self.lock:
            if self.running:
                raise LookupError("the self-check is already running")
            if self.svc.ec_info.get("active") == "none":
                raise LookupError("no EC access")
            if stage == 2 and not self.svc.monitor.ac_online():
                raise ValueError("connect the charger: the check with writes runs on AC power only")
            self.running = stage
        threading.Thread(target=self._run, args=(stage,), daemon=True, name="selfcheck").start()

    def _run(self, stage):
        try:
            with self.svc.busy.task("selfcheck", label=f"stage {stage}", blocking=True):
                r = self.run(stage)
            self.last = r
            store.save_json(store.path(LAST), r)
            log.info("self-check stage %d: %s", stage, self.summary()["last"]["counts"])
        except Exception as e:  # noqa: BLE001
            log.exception("self-check")
            self.last = {"time": time.time(), "stage": stage, "error": str(e), "items": [], "unknowns": [str(e)]}
        finally:
            with self.lock:
                self.running = None
            self.svc.emit("selfcheck", self.summary())

    def run(self, stage):
        svc = self.svc
        r = {"time": time.time(), "stage": stage, "path": svc.ec_info.get("active"), "items": [], "unknowns": []}
        self.stage1(r)
        if stage >= 2:
            self.stage2(r)
        r["features"] = self.features(r)
        r["draft"] = self.draft(r)
        return r

    # -- stage 1 -------------------------------------------------------------------------------------
    def stage1(self, r):
        svc, ec, add = self.svc, self.svc.ec, r["items"].append
        unk = r["unknowns"]
        self._progress(2, "identity")
        project = self.rd(ec, R.PROJECT_ID)
        bios_proj = self.rd(ec, R.BIOS_PROJECT_ID)
        info = {}
        try:
            info = svc.monitor.info()
        except Exception:  # noqa: BLE001
            pass
        r["identity"] = {"project": f"0x{project:02X}", "bios_project": f"0x{bios_proj:02X}",
                         "vendor": info.get("vendor"), "product": info.get("product"), "board": info.get("board"),
                         "bios": info.get("bios"), "ec": info.get("ec")}
        plat = platformdb.summary(project)
        r["platform"] = plat
        if plat["fallback"]:
            add(_item("project", "identity", "Platform profile", "warn",
                      f"project 0x{project:02X} has no platform profile — the generic one is used"))
            unk.append(f"project 0x{project:02X} is not in the platform database")
        else:
            add(_item("project", "identity", "Platform profile", "ok" if plat["status"] == "verified" else "warn",
                      f"{plat['name']} · {plat['status']} · {plat['source']}"))
        tested = plat.get("tested") or {}
        for k, mine in (("ec", info.get("ec")), ("bios", info.get("bios"))):
            vers = tested.get(k) or []
            if vers and mine and str(mine) not in vers:
                add(_item(f"tested_{k}", "identity", f"Tested {k.upper()} version", "warn",
                          f"profile tested with {', '.join(vers)}, this laptop has {mine}"))
                unk.append(f"{k.upper()} {mine} differs from the tested {', '.join(vers)}")
            elif vers and mine:
                add(_item(f"tested_{k}", "identity", f"Tested {k.upper()} version", "ok", str(mine)))

        # access paths
        self._progress(10, "paths")
        active = svc.ec_info.get("active")
        add(_item("active", "paths", "Active path", "ok", active))
        other_name, other, why = self._other_path(active)
        if active == "oem":
            add(_item("oem_path", "paths", "OEM driver", "ok", "UWACPIDriver answers"))
        if active == "wmi":
            add(_item("wmi_path", "paths", "WMI interface", "ok", getattr(ec, "instance_name", None) or "answers"))
        if other_name:
            add(_item(f"{other_name}_path", "paths", "OEM driver" if other_name == "oem" else "WMI interface",
                      "ok" if other else "skip", why))
        if other:
            self._progress(20, "compare")
            diff = []
            for a in COMPARE:
                v1, v2 = self.rd(ec, a), self.rd(other, a)
                if v1 != v2:
                    diff.append(f"0x{a:03X}: {active} 0x{v1:02X} / {other_name} 0x{v2:02X}")
            add(_item("compare", "paths", f"Same registers through {active} and {other_name}", "ok" if not diff else "fail",
                      f"{len(COMPARE)} registers equal" if not diff else "; ".join(diff[:8])))
            if diff:
                unk.append("the two access paths read different values: " + "; ".join(diff[:8]))
            try:
                other.close()
            except Exception:  # noqa: BLE001
                pass

        # plausibility
        self._progress(35, "registers")
        caps = self.rd(ec, R.EC_CAPS_78E)
        add(_item("ramfan", "registers", "RAM fan tables (RamFan 1.5)", "ok" if caps & 0x40 else "warn",
                  "0x78E bit6 set" if caps & 0x40 else "0x78E bit6 clear — modes and fan curves are not available"))
        fm = self.rd(ec, R.FAN_MODE)
        ok = (fm & ~0x40 & 0xFF) in KNOWN_MODE_BYTES
        add(_item("mode_byte", "registers", "Mode byte (0x751)", "ok" if ok else "warn", f"0x{fm:02X}"))
        if not ok:
            unk.append(f"unknown mode byte 0x{fm:02X} in 0x751")
        bad = []
        for name, base in (("gaming", R.PL_DEF_GAMING), ("office", R.PL_DEF_OFFICE), ("turbo", R.PL_DEF_TURBO)):
            pl = [self.rd(ec, base + i) for i in range(3)]
            if not all(3 <= v <= 255 for v in pl) or pl[0] > pl[1]:
                bad.append(f"{name} {pl}")
        add(_item("pl_defaults", "registers", "Factory power limits", "ok" if not bad else "warn",
                  "PL1 ≤ PL2, all set" if not bad else "; ".join(bad)))
        if bad:
            unk.append("factory power limits look unusual: " + "; ".join(bad))
        try:
            f = svc.monitor.fans()
            fan_ok = all(0 <= f.get(k, 0) <= 9000 for k in ("cpu_rpm", "gpu_rpm")) and \
                all(0 <= f.get(k, 0) <= 100 for k in ("cpu_duty", "gpu_duty"))
            add(_item("fans", "registers", "Fan readings", "ok" if fan_ok else "warn",
                      f"CPU {f.get('cpu_rpm')} rpm / {f.get('cpu_duty')} %" +
                      (f", GPU {f.get('gpu_rpm')} rpm / {f.get('gpu_duty')} %" if "gpu_rpm" in f else "")))
            r["fans"] = f
        except Exception as e:  # noqa: BLE001
            add(_item("fans", "registers", "Fan readings", "fail", str(e)))
        dv = self.rd(ec, R.BAT_DESIGN_VOLT_L) | (self.rd(ec, R.BAT_DESIGN_VOLT_L + 1) << 8)
        add(_item("battery", "registers", "Battery design voltage", "ok" if 7000 <= dv <= 20000 else "warn", f"{dv} mV"))
        add(_item("ap_exist", "registers", "Control program flag (0x741 bit0)",
                  "ok" if self.rd(ec, R.AP_EXIST) & 1 else "warn", "set" if self.rd(ec, R.AP_EXIST) & 1 else "clear"))
        lc = self.rd(ec, R.LC_SUPPORT) & 0x80
        add(_item("lc_support", "registers", "Liquid cooler support (0x7A4 bit7)", "ok", "yes" if lc else "no"))
        r["lc_support"] = bool(lc)
        try:
            sm = ec.smart_apc_table()
            src = getattr(ec, "smapc_source", "firmware")
            add(_item("smrw", "registers", "Power limit table", "ok",
                      ("SMRW (firmware): " if src == "firmware" else "from the platform profile: ") +
                      ", ".join(f"{k} {v}" for k, v in sm.items() if k in ("PL1", "PL2", "PL4", "DefaultTGP", "DynamicBoost"))))
            r["smapc"] = {"source": src, "values": sm}
        except Exception as e:  # noqa: BLE001
            add(_item("smrw", "registers", "Power limit table", "warn", str(e)))
            unk.append("no power limit table: " + str(e))

        # timing
        self._progress(50, "timing")
        t0 = time.perf_counter()
        for _ in range(8):
            self.rd(ec, R.PROJECT_ID)
        ms = (time.perf_counter() - t0) / 8 * 1000
        r["ms_per_read"] = round(ms, 1)
        add(_item("timing", "paths", "Time per EC access", "ok" if ms < 50 else "warn", f"{ms:.1f} ms"))

        # firmware
        self._progress(60, "firmware")
        self._firmware(r)

    def _other_path(self, active):
        svc = self.svc
        from .ecaccess import _wmi_cfg
        if active == "oem":
            try:
                if svc.mock:
                    if os.environ.get("UWCC_MOCK_WMI", "1") == "0":
                        raise RuntimeError("no WMI interface")
                    from .ec import MockWmiEC
                    return "wmi", MockWmiEC(_wmi_cfg(svc.pf.project_raw)), "answers"
                if sys.platform != "win32":
                    return None, None, ""
                from .win.wmiec import WinWmiEC
                return "wmi", WinWmiEC(_wmi_cfg(svc.pf.project_raw)), "answers"
            except Exception as e:  # noqa: BLE001
                return "wmi", None, f"not available: {e}"
        if active == "wmi":
            try:
                if svc.mock:
                    if os.environ.get("UWCC_MOCK_OEM", "1") == "0":
                        raise RuntimeError("OEM driver missing")
                    from .ec import MockEC
                    return "oem", MockEC(), "answers"
                from .win.acpidrv import WinAcpiDriverEC
                return "oem", WinAcpiDriverEC(), "answers"
            except Exception as e:  # noqa: BLE001
                return "oem", None, f"not available: {e}"
        return None, None, ""

    def _firmware(self, r):
        add, unk = r["items"].append, r["unknowns"]
        found = {}
        try:
            from .report_oem import acpi_tables
            _, files = acpi_tables()
            blob = b"".join(v for k, v in files.items() if k.endswith(".aml"))
            if blob:
                found = {n: n.encode() in blob for n in FIRMWARE_NAMES}
        except Exception as e:  # noqa: BLE001
            log.debug("ACPI tables: %s", e)
        if not found:
            add(_item("acpi", "firmware", "ACPI tables", "skip", "not readable here"))
        else:
            r["firmware"] = found
            missing = [n for n, v in found.items() if not v]
            add(_item("acpi", "firmware", "Firmware methods", "ok" if not missing else "warn",
                      "found: " + ", ".join(n for n, v in found.items() if v) +
                      ("; missing: " + ", ".join(missing) if missing else "")))
            if missing:
                unk.append("firmware methods not found: " + ", ".join(missing))
        if sys.platform == "win32" and not self.svc.mock:
            from .win.winplat import wmi_query
            rows = wmi_query("SELECT InstanceName FROM AcpiTest_MULong", r"root\WMI")
            add(_item("wmi_class", "firmware", "WMI class AcpiTest_MULong", "ok" if rows else "warn",
                      ", ".join(str(x.InstanceName) for x in rows) if rows else "not found"))

    # -- stage 2 -------------------------------------------------------------------------------------
    def stage2(self, r):
        svc, ec, add = self.svc, self.svc.ec, r["items"].append
        unk = r["unknowns"]
        snap = {f"0x{a:03X}": self.rd(ec, a) for a in SNAP_REGS}
        store.save_json(store.path(SNAPSHOT), {"time": time.time(), "regs": snap})
        orig = {int(k, 16): v for k, v in snap.items()}
        tests = [self._t_fnlock, self._t_touchpad, self._t_mode, self._t_fanboost, self._t_pl1, self._t_ctgp,
                 self._t_charge, self._t_table]
        try:
            for i, t in enumerate(tests):
                self._progress(65 + i * 30 // len(tests), t.__name__[3:])
                try:
                    it = t(orig)
                except Exception as e:  # noqa: BLE001
                    it = _item(t.__name__[3:], "write", t.__name__[3:], "fail", str(e))
                add(it)
                if it["status"] in ("warn", "fail"):
                    unk.append(f"{it['name']}: {it['detail']}")
        finally:
            for a, v in orig.items():
                try:
                    self.wr(a, v)
                except Exception as e:  # noqa: BLE001
                    log.error("restore 0x%03X: %s", a, e)
            try:
                os.remove(store.path(SNAPSHOT))
            except OSError:
                pass
            self._progress(97, "restore")
            if svc.fan_control:
                try:
                    svc.power.tables.invalidate()
                    svc.power.set_user_profile(svc.power.option["OperatingMode"])
                except Exception as e:  # noqa: BLE001
                    log.error("re-apply after the self-check: %s", e)
        add(_item("lightbar", "write", "Light bar trigger", "skip", "needs your eyes — not checked automatically"))
        if svc.ec_info.get("active") == "wmi":
            add(_item("pwup", "write", "Liquid-cooling power level (PWUP)", "fail", "not reachable through WMI (OEM driver only)"))

    def _bit(self, iid, name, a, bit, orig):
        v = orig[a]
        test = v ^ (1 << bit)
        self.wr(a, test)
        time.sleep(0.2)
        rb = self.rd(self.svc.ec, a)
        self.wr(a, v)
        ok = bool(rb & (1 << bit)) == bool(test & (1 << bit))
        return _item(iid, "write", name, "ok" if ok else "fail",
                     f"0x{a:03X} bit{bit}: wrote 0x{test:02X}, read 0x{rb:02X}, restored 0x{v:02X}")

    def _t_fnlock(self, orig):
        return self._bit("fn_lock", "Fn Lock", R.FN_LOCK, 4, orig)

    def _t_touchpad(self, orig):
        return self._bit("touchpad", "Touchpad toggle flag", R.TOUCHPAD, 6, orig)

    def _t_mode(self, orig):
        v = orig[R.FAN_MODE]
        base = v & ~0x40 & 0xFF
        test = (0xA0 if base != 0xA0 else 0x00) | (v & 0x40)
        self.wr(R.FAN_MODE, test)
        time.sleep(0.3)
        rb = self.rd(self.svc.ec, R.FAN_MODE)
        self.wr(R.FAN_MODE, v)
        ok = (rb & 0x90) == (test & 0x90)
        return _item("modes", "write", "Mode byte", "ok" if ok else "fail",
                     f"wrote 0x{test:02X}, read 0x{rb:02X}, restored 0x{v:02X}")

    def _t_fanboost(self, orig):
        ec = self.svc.ec
        v = orig[R.FAN_MODE]
        if v & 0x40:
            return _item("fan_boost", "write", "Fan Boost", "skip", "Fan Boost is on already")
        before = self.svc.monitor.fans()
        self.wr(R.FAN_MODE, v | 0x40)
        held, after = False, before
        for _ in range(16):
            time.sleep(0.5)
            held = bool(self.rd(ec, R.FAN_MODE) & 0x40)
            inv = getattr(ec, "invalidate", None)
            if inv:
                inv()
            after = self.svc.monitor.fans()
            if after.get("cpu_rpm", 0) - before.get("cpu_rpm", 0) >= 300 or after.get("cpu_duty", 0) >= 90:
                break
        self.wr(R.FAN_MODE, v)
        rose = after.get("cpu_rpm", 0) - before.get("cpu_rpm", 0) >= 300 or after.get("cpu_duty", 0) >= 90
        st = "ok" if held and rose else ("warn" if held else "fail")
        return _item("fan_boost", "write", "Fan Boost", st,
                     f"bit6 {'held' if held else 'not held'}; CPU fan {before.get('cpu_rpm')} → {after.get('cpu_rpm')} rpm"
                     + ("" if rose or not held else " (no reaction within 8 s)"))

    def _t_reg(self, iid, name, a, test, orig, mask=0xFF):
        v = orig[a]
        self.wr(a, test)
        time.sleep(0.2)
        rb = self.rd(self.svc.ec, a)
        self.wr(a, v)
        ok = (rb & mask) == (test & mask)
        return _item(iid, "write", name, "ok" if ok else "fail",
                     f"0x{a:03X}: wrote {test & mask}, read {rb & mask}, restored {v & mask}")

    def _t_pl1(self, orig):
        v = orig[R.PL1]
        test = 25 if (v == 0 or v > 30) else max(10, v - 5)       # always lower: safe
        return self._t_reg("power_limits", "PL1 (0x783)", R.PL1, test, orig)

    def _t_ctgp(self, orig):
        v = orig[R.GPU_CTGP_TARGET]
        test = v - 5 if v >= 5 else 5
        return self._t_reg("gpu_power", "cTGP target (0x744)", R.GPU_CTGP_TARGET, test, orig)

    def _t_charge(self, orig):
        v = orig[R.CHARGE_LIMIT_UP]
        test = (v & 0x80) | (95 if (v & 0x7F) != 95 else 0)
        return self._t_reg("battery", "Charge limit (0x7B9)", R.CHARGE_LIMIT_UP, test, orig, 0x7F)

    def _t_table(self, orig):
        """Fan-table handshake: the EC copies its factory table into RAM and clears 0xF5D / 0xF5E."""
        ec = self.svc.ec
        if not self.rd(ec, R.EC_CAPS_78E) & 0x40:
            return _item("fan_tables", "write", "Fan-table handshake", "skip", "no RamFan 1.5")
        self.wr(R.FT_HS_MODE, 2)
        self.wr(R.FT_HS_A, 0xFD)
        self.wr(R.FT_HS_B, 0xC9)
        for i in range(12):
            time.sleep(0.5)
            if self.rd(ec, R.FT_HS_A) != 0xFD and self.rd(ec, R.FT_HS_B) != 0xC9:
                return _item("fan_tables", "write", "Fan-table handshake", "ok", f"EC answered in {(i + 1) * 0.5:.1f} s")
        return _item("fan_tables", "write", "Fan-table handshake", "fail", "EC did not answer in 6 s")

    # -- conclusions ---------------------------------------------------------------------------------
    def features(self, r):
        st = {it["id"]: it["status"] for it in r["items"]}
        wmi = r["path"] == "wmi"
        on = lambda *ids: all(st.get(i) in ("ok", "warn") for i in ids)       # noqa: E731
        f = {
            "modes": "on" if on("modes") else "off",
            "fan_boost": "on" if on("fan_boost") else "off",
            "power_limits": "on" if on("power_limits") else "off",
            "gpu_power": "on" if on("gpu_power") else "off",
            "super_performance": "on" if on("modes", "gpu_power") else "off",
            "fan_tables": ("slow" if wmi else "on") if on("fan_tables") else "off",
            "fan_monitor": ("slow" if wmi else "on") if st.get("fans") == "ok" else "off",
            "battery": "on" if on("battery") else "off",
            "switches": "on" if on("fn_lock", "touchpad") else "off",
            "lightbar_ec": "off",
            "lc_ec": "on" if r.get("lc_support") else "off",
            "power_boost_lc": "off",
        }
        if r["stage"] < 2:                      # nothing was written: only what reading shows
            for k in ("modes", "fan_boost", "power_limits", "gpu_power", "super_performance", "fan_tables", "battery",
                      "switches"):
                f[k] = "off"
        return f

    def draft(self, r):
        ident = r.get("identity") or {}
        try:
            project = int(ident.get("project", "0x0"), 16)
        except ValueError:
            project = 0
        cur = platformdb.match(project)["profile"]
        name = " ".join(x for x in (ident.get("vendor"), ident.get("product")) if x) or "Laptop"
        lim = None
        sm = (r.get("smapc") or {})
        if sm.get("values"):
            lim = {k: v for k, v in sm["values"].items() if k in platformdb.CAPS}
            try:
                lim = platformdb.check_limits(lim)
            except ValueError as e:
                r["unknowns"].append(f"power limits not used for the draft: {e}")
                lim = None
        from .ecaccess import config
        cfg = config(project)
        return {
            "schema": platformdb.SCHEMA, "id": f"draft-0x{project:02x}",
            "name": f"{name} (project 0x{project:02X})", "vendor": "Uniwill", "status": "draft",
            "match": {"project": [f"0x{project:02X}"]},
            "tested": {"ec": [str(ident.get("ec"))] if ident.get("ec") else [],
                       "bios": [str(ident.get("bios"))] if ident.get("bios") else [],
                       "date": time.strftime("%Y-%m-%d"), "by": "self-check"},
            "access": cur.get("access") or {},
            "wmi": {"poll": cfg["poll"], "always_write": cfg["always_write"], "no_cache": cfg["no_cache"],
                    "features": r.get("features") or {}},
            "limits": lim or cur.get("limits"),
            "evidence": {it["id"]: f"{it['status']}: {it['detail']}"[:300] for it in r["items"]},
            "notes": {"en": [f"Made by the self-check (stage {r['stage']}, path {r['path']})."],
                      "ru": [f"Создан самопроверкой (ступень {r['stage']}, путь {r['path']})."]},
        }

    def export(self):
        """Result for a GitHub issue: no serial numbers or user data."""
        from . import version_string
        r = dict(self.last or {})
        return {"program": version_string(), "result": r, "draft_profile": r.get("draft")}
