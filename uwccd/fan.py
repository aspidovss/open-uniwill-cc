"""Operating modes, profiles and fan tables.

Port of MyFanManager_RamFan1p5_CML + FanTable_Manager1p5_CML + MyFanTableCtrl + GpuFeatures
(the code path GCUService takes for PH4/PH6 "commercial" projects with RamFan 1.5 EC).
"""
import copy
import logging
import os
import shutil
import threading
import time

from . import regs as R
from . import store

log = logging.getLogger("uwccd.fan")

TABLE_NAMES = ["M1T1", "M1T2", "M1T3", "M2T1", "M2T2", "M2T3"]
MODE_NAMES = {R.MODE_OFFICE: "office", R.MODE_GAMING: "gaming", R.MODE_TURBO: "turbo"}

DEFAULT_OPTION = {
    "GamingProfileIndex": 0, "OfficeProfileIndex": 0, "TurboProfileIndex": 0, "CustomProfileIndex": 0,
    "FanBoostEnable": 0, "FanSafetyProtectNotify": 0, "DefaultNotify": 0, "WhisperModeSwitch": 0,
    "WhisperModeSetting": 0, "WhisperModeMinFps_QUIETER": 30, "WhisperModeMinFps_QUIET": 40,
    "WhisperModeMinFps_BALANCED": 60, "OperatingMode": 1,
}

DEFAULT_PROFILE = {
    "Activated": False, "Name": "", "CustomizeName": "1", "OverClockingEnabled": 0,
    "CPU": {"PL1": 0, "PL1_Enabled": False, "PL2": 0, "PL2_Enabled": False, "PL1_dc": 0,
            "PL1_dc_Enabled": False, "PL2_dc": 0, "PL2_dc_Enabled": False, "PL4": 215, "PL1_S2": 0,
            "PL1_S2_Enabled": False, "PL2_S2": 0, "PL2_S2_Enabled": False, "OffsetCoreVoltage": 0,
            "OffsetCoreVoltageOC": 0, "TccOffsetSwitch": 0, "TccOffset": 5, "AmdSPL": 0, "AmdSPPT": 0,
            "AmdFPPT": 215, "AmdTccTarget": 95, "AmdCoreFreq": 0, "AmdCoreFreqOC": 0,
            "AmdCoreVoltage": 0, "AmdCoreVoltageOC": 0},
    "GPU": {"CoreClockOffset": 0, "CoreClockOffsetOC": 0, "MemoryClockOffset": 0, "MemoryClockOffsetOC": 0,
            "TargetTemperature": 87, "ConfigurableTGPSwitch": 0, "ConfigurableTGPTarget": 0,
            "DynamicBoostSwitch": 0, "DynamicBoost": 0, "ConfigurableTGPSwitch_S2": 0,
            "ConfigurableTGPTarget_S2": 0, "DynamicBoostSwitch_S2": 0, "DynamicBoost_S2": 0,
            "DynamicBoostTotalProcessingPowerTarget": 255, "WhisperModeSwitch": 0, "WhisperModeSetting": 0,
            "WhisperModeMinFps_QUIETER": 30, "WhisperModeMinFps_QUIET": 40, "WhisperModeMinFps_BALANCED": 60},
    "FAN": {"TableName": "M1T1", "FanSwitchSpeedEnabled": 0, "FanSwitchSpeed": 300, "SkipSafetyAbnormalProtection": 0},
    "MEM": {"MemoryOverClockSwitch": 0},
}


def empty_table(name):
    pts = [{"ID": i, "UpT": 255, "DownT": 255, "Duty": 255} for i in range(16)]
    return {"Activated": False, "Name": name, "FanControlRespective": False,
            "CpuTemp_DefaultMaxLevel": 10, "GpuTemp_DefaultMaxLevel": 10,
            "CPU": copy.deepcopy(pts), "GPU": copy.deepcopy(pts)}


def copy_table(src, name):
    """CopyFanTable — copies the curve only (PL / GPU feature strings are NOT copied)."""
    t = empty_table(name)
    t["CpuTemp_DefaultMaxLevel"] = src.get("CpuTemp_DefaultMaxLevel", 10)
    t["GpuTemp_DefaultMaxLevel"] = src.get("GpuTemp_DefaultMaxLevel", 10)
    for k in ("CPU", "GPU"):
        for i in range(16):
            for f in ("UpT", "DownT", "Duty"):
                t[k][i][f] = src[k][i][f]
    return t


def generate_duty(src, factor, name):
    t = copy_table(src, name)
    for k in ("CPU", "GPU"):
        for i in range(16):
            t[k][i]["Duty"] = int(src[k][i]["Duty"] * factor) & 0xFF
    return t


def level_unused(points, i):
    """A level is unused when its duty is the 0xFF marker or (above level 0) its entry temperature is 0 or 255."""
    p = points[i]
    return p["Duty"] > 100 or (i > 0 and p["UpT"] in (0, 255))


def normalize_points(points):
    """Everything after the first unused level is unused too (the EC stops there). Some ECs fill the
    tail with zeros instead of 0xFF; such levels used to look like 'active, 0 °C' and broke validation."""
    end = next((i for i in range(1, 16) if level_unused(points, i)), 16)
    for p in points[end:]:
        p["UpT"] = p["DownT"] = p["Duty"] = 255
    return points


def max_level(points):
    lvl = 10
    for i in range(1, 16):
        if points[i]["Duty"] > points[i - 1]["Duty"]:
            lvl = i
    return lvl + 1


class FanTables:
    """FanTable_Manager1p5_CML."""

    def __init__(self, ec, platform):
        self.ec = ec
        self.platform = platform
        self.nv = platform.nv_gpu
        self.dir = store.path("UserFanTables", platform.project_name)
        self.tables = {}
        self.defaults = {}
        self.lock = threading.Lock()

    # -- persistence ---------------------------------------------------------
    def _file(self, name):
        return os.path.join(self.dir, name + ".json")

    def save(self, t):
        store.save_json(self._file(t["Name"]), t)

    def load(self, name):
        t = store.load_json(self._file(name))
        if not t:
            return None
        t.setdefault("Name", name)
        for k in ("CPU", "GPU"):
            if len(t.get(k) or []) == 16:
                normalize_points(t[k])
        return t

    def seed_from_share(self):
        """Copy the factory per-project tables (UserFanTables/<Project>) shipped with Control Center."""
        src = os.path.join(store.SHARE_DIR, "UserFanTables", self.platform.project_name)
        if os.path.isdir(src) and not os.path.isdir(self.dir):
            shutil.copytree(src, self.dir)
            log.info("seeded fan tables from %s", src)

    def init(self):
        self.seed_from_share()
        for n in ("DefaultFanTable_Gaming", "DefaultFanTable_Office", "DefaultFanTable_Turbo"):
            t = self.load(n)
            if t:
                self.defaults[n] = t
        if all(os.path.exists(self._file(n)) for n in TABLE_NAMES):
            for n in TABLE_NAMES:
                self.tables[n] = self.load(n)
            if len(self.defaults) < 3:
                self.refresh_default_all()
        else:
            self.refresh()

    def refresh(self):
        """FanTable_Refresh — read EC default tables and derive the user tables."""
        self.refresh_default_all()
        g = self.defaults.get("DefaultFanTable_Gaming")
        o = self.defaults.get("DefaultFanTable_Office")
        if not g or not o:
            log.error("default fan tables unavailable")
            return
        for n in ("M1T1", "M1T2", "M1T3"):
            self.tables[n] = copy_table(g, n)
            self.save(self.tables[n])
        for n in ("M2T1", "M2T2", "M2T3"):
            self.tables[n] = copy_table(o, n)
            self.save(self.tables[n])

    def refresh_default_all(self):
        self.ec.set_bit(R.AP_EXIST, 0, False)
        ok = True
        for name, code in (("DefaultFanTable_Office", 3), ("DefaultFanTable_Turbo", 1), ("DefaultFanTable_Gaming", 2)):
            t = empty_table(name)
            if self.refresh_default(t, code):
                t["CpuTemp_DefaultMaxLevel"] = max_level(t["CPU"])
                t["GpuTemp_DefaultMaxLevel"] = max_level(t["GPU"])
                self.defaults[name] = t
            else:
                ok = False
        if ok:
            for t in self.defaults.values():
                self.save(t)
        self.ec.set_bit(R.AP_EXIST, 0, True)
        return ok

    def refresh_default(self, t, mode_code):
        self.ec.write(R.FT_HS_MODE, mode_code)
        self.ec.write(R.FT_HS_A, 0xFD)
        self.ec.write(R.FT_HS_B, 0xC9)
        for _ in range(10):
            time.sleep(0.5)
            if self.ec.read(R.FT_HS_A) != 0xFD and self.ec.read(R.FT_HS_B) != 0xC9:
                self.read_ec_table(t)
                return True
        log.warning("EC did not provide default fan table %s", t["Name"])
        return False

    # -- EC encoding -----------------------------------------------------------
    def read_ec_table(self, t):
        for kind, up, down, duty, enabled in (("CPU", R.FT_CPU_UP, R.FT_CPU_DOWN, R.FT_CPU_DUTY, True),
                                               ("GPU", R.FT_GPU_UP, R.FT_GPU_DOWN, R.FT_GPU_DUTY, self.nv)):
            if not enabled:
                continue
            for i in range(16):
                p = t[kind][i]
                p["UpT"] = 0 if i == 0 else self.ec.read(up + i - 1)
                p["DownT"] = self.ec.read(down + i + 1) if i < 15 else self.ec.read(down + i)
                p["Duty"] = self.ec.read(duty + i) // 2
            normalize_points(t[kind])

    def write_ec_table(self, t):
        for kind, up, down, duty, enabled in (("CPU", R.FT_CPU_UP, R.FT_CPU_DOWN, R.FT_CPU_DUTY, True),
                                               ("GPU", R.FT_GPU_UP, R.FT_GPU_DOWN, R.FT_GPU_DUTY, self.nv)):
            pts = t.get(kind)
            if not enabled or not pts:
                continue
            for i in range(16):
                self.ec.write(up + i, pts[i + 1]["UpT"] if i < 15 else 0xFF)
                if i < 15:
                    self.ec.write(down + i + 1, pts[i]["DownT"])
                d = pts[i]["Duty"]
                self.ec.write(duty + i, d * 2 if d <= 100 else 0xFF)

    def set_respective(self, on):
        self.ec.set_bit(R.FAN_CTRL_7C5, 7, bool(on))

    def set_control_by_ramfan(self, on):
        """MyFanTableCtrl.SetFanControlByRamFan1p5 — bit2 of 0x7C6 enables the RAM fan table."""
        if on:
            enable = self.ec.read(R.FT_CPU_UP) != 0 or self.ec.read(R.FT_CPU_UP + 1) != 0
        else:
            enable = False
        self.ec.set_bit(R.FAN_CTRL_7C6, 2, enable)

    def apply(self, name):
        """MyFanTableCtrl.SetFanTable -> SetFanControlByRamFan1p5(0); SetFanTable; (1)."""
        t = self.tables.get(name)
        if t:
            self.apply_table(t)

    def apply_table(self, t):
        name = t.get("Name")
        with self.lock:
            self.set_control_by_ramfan(False)
            self.set_respective(t.get("FanControlRespective", False))
            self.write_ec_table(t)
            self.set_control_by_ramfan(True)
        log.info("fan table %s applied", name)

    def disable(self):
        self.set_control_by_ramfan(False)

    # -- edit ------------------------------------------------------------------
    def update(self, name, data):
        """SetFanTableSetting from the UI."""
        if name not in self.tables:
            raise KeyError(name)
        t = copy.deepcopy(self.tables[name])
        for kind in ("CPU", "GPU"):
            if kind in data:
                pts = data[kind]
                if len(pts) != 16:
                    raise ValueError("16 points expected")
                for i, p in enumerate(pts):
                    for f in ("UpT", "DownT", "Duty"):
                        v = int(p[f])
                        if not 0 <= v <= 255:
                            raise ValueError(f"{kind}[{i}].{f} out of range")
                        t[kind][i][f] = v
        for kind in ("CPU", "GPU"):
            pts = t[kind]
            normalize_points(pts)
            active = [p for i, p in enumerate(pts) if not level_unused(pts, i)]
            for a, b in zip(active, active[1:]):
                if b["UpT"] <= a["UpT"]:
                    raise ValueError(f"{kind}: level temperatures must increase")
            if len(active) > 1 and active[-1]["Duty"] < 40:
                raise ValueError(f"{kind}: the highest level must run the fan at 40 % or more")
        if "FanControlRespective" in data:
            t["FanControlRespective"] = bool(data["FanControlRespective"])
        t["Activated"] = True
        self.tables[name] = t
        self.save(t)
        return t

    def restore_default(self, name):
        g = self.defaults.get("DefaultFanTable_Gaming")
        o = self.defaults.get("DefaultFanTable_Office")
        if name.startswith("M1") and g:
            t = copy_table(g, name)
        elif name == "M2T1" and o:
            t = generate_duty(o, 0.8, name)
        elif name == "M2T2" and o:
            t = generate_duty(o, 0.9, name)
        elif name == "M2T3" and o:
            t = copy_table(o, name)
        else:
            return None
        self.tables[name] = t
        self.save(t)
        return t

    def pl_defaults(self, name):
        """GetPLDefaultValue -> strings ("NA", "DEFAULT" or number) — None if absent."""
        t = self.tables.get(name) or {}
        return {k: t.get(k) for k in ("PL1", "PL2", "PL1_dc", "PL2_dc", "CTGP", "DB", "WM",
                                      "CTGP2", "DB2", "PL1_S2", "PL2_S2")}


class GpuFeatures:
    """GCUService.MyFan.Overclocking.GpuFeatures — NVIDIA cTGP / Dynamic Boost through the EC."""

    def __init__(self, ec):
        self.ec = ec

    def ctgp_fun_ctrl(self, on):
        self.ec.set_bit(R.GPU_FEAT_CTRL, 2, on == 1)

    def ctgp_target(self, value, base=0):
        if value >= base:
            self.ec.write(R.GPU_CTGP_TARGET, (value - base) & 0xFF)

    def db_fun_ctrl(self, _on=1):
        self.ec.set_bit(R.GPU_FEAT_CTRL, 0, True)   # GCUService always writes 1

    def db_enable(self, on):
        self.ec.set_bit(R.GPU_FEAT_CTRL, 1, on == 1)

    def db_tpp_target(self, v):
        self.ec.write(R.GPU_DB_TPP_TARGET, v & 0xFF)

    def db_max_tgp(self, v):
        self.ec.write(R.GPU_DB_MAX_TGP, v & 0xFF)


def _feat(value):
    """RefreshCpu/GpuFeatureValidValues: (enabled, value or 'DEFAULT')."""
    if value is None:
        return None
    s = str(value)
    if "NA" in s:
        return (False, 0)
    if "DEFAULT" in s:
        return (True, "DEFAULT")
    try:
        return (True, int(s))
    except ValueError:
        return None


class PowerManager:
    """MyFanManager_RamFan1p5_CML."""

    manager = "cml"
    TABLE_NAMES = TABLE_NAMES
    MODES = (R.MODE_OFFICE, R.MODE_GAMING, R.MODE_TURBO)

    def __init__(self, ec, platform, nvram, notify):
        self.ec = ec
        self.pf = platform
        self.nvram = nvram
        self.notify = notify          # callback(event:str, data:dict)
        self.tables = FanTables(ec, platform)
        self.gpu = GpuFeatures(ec)
        self.dir = store.path("UserPofiles")
        self.option = dict(DEFAULT_OPTION)
        self.profiles = {}
        self.custom = {}
        self.current = None
        self.lock = threading.RLock()
        self.ac_online = True
        self.pl_default = {}

    # -- startup (EnableByService) ------------------------------------------------
    def start(self):
        with self.lock:
            self.tables.init()
            self.load_profile_all()
            self.sync_bios()
            self.init()

    def read_pl_defaults(self):
        def rd(base):
            return {"PL1": self.ec.read(base), "PL2": self.ec.read(base + 1),
                    "PL4": self.ec.read(base + 2), "DState": self.ec.read(base + 3)}
        self.pl_default = {"gaming": rd(R.PL_DEF_GAMING), "office": rd(R.PL_DEF_OFFICE),
                           "turbo": rd(R.PL_DEF_TURBO)}
        tau = self.ec.read(R.TAU_DEF)
        self.pl_default["tau"] = tau or 0x38

    def refresh_customize_values(self):
        self.custom = {}
        for name in TABLE_NAMES:
            d = self.tables.pl_defaults(name)
            base = self.pl_default["gaming" if name.startswith("M1") else "office"]
            c = {"PL1_Enabled": False, "PL2_Enabled": False, "PL1_dc_Enabled": False, "PL2_dc_Enabled": False,
                 "PL1": 0, "PL2": 0, "PL1_dc": 0, "PL2_dc": 0, "PL1_S2": 0, "PL2_S2": 0,
                 "PL1_S2_Enabled": False, "PL2_S2_Enabled": False, "CTGP": 0, "CTGP_Switch": 0,
                 "DB": 0, "DB_Switch": 0, "WM": 0, "WM_Switch": 0, "CTGP2": 0, "CTGP2_Switch": 0,
                 "DB2": 0, "DB2_Switch": 0}
            for key, dflt in (("PL1", base["PL1"]), ("PL2", base["PL2"]), ("PL1_dc", base["PL1"]), ("PL2_dc", base["PL2"])):
                f = _feat(d[key])
                if f is None:      # null -> exception in GCUService -> all PL disabled
                    for k in ("PL1", "PL2", "PL1_dc", "PL2_dc"):
                        c[k + "_Enabled"] = False
                    break
                c[key + "_Enabled"] = f[0]
                c[key] = dflt if f[1] == "DEFAULT" else f[1]
            for key, sw in (("CTGP", "CTGP_Switch"), ("DB", "DB_Switch"), ("WM", "WM_Switch")):
                f = _feat(d[key] if d[key] is not None else "NA")
                c[sw], c[key] = (1, f[1]) if f and f[0] and f[1] != "DEFAULT" else (0, 0)
            if name.startswith("M1"):
                for key, sw in (("CTGP2", "CTGP2_Switch"), ("DB2", "DB2_Switch")):
                    f = _feat(d[key] if d[key] is not None else "NA")
                    c[sw], c[key] = (1, f[1]) if f and f[0] and f[1] != "DEFAULT" else (0, 0)
                for key in ("PL1_S2", "PL2_S2"):
                    f = _feat(d[key] if d[key] is not None else "NA")
                    c[key + "_Enabled"], c[key] = (True, f[1]) if f and f[0] and f[1] != "DEFAULT" else (False, 0)
            self.custom[name] = c

    def _pfile(self, name):
        return os.path.join(self.dir, name + ".json")

    def load_profile_all(self):
        self.read_pl_defaults()
        self.refresh_customize_values()
        if os.path.isdir(self.dir) and os.path.exists(self._pfile("MainOption")):
            self.option = {**DEFAULT_OPTION, **(store.load_json(self._pfile("MainOption"), {}) or {})}
            for m in (1, 2):
                for p in (1, 2, 3):
                    n = f"Mode{m}_Profile{p}"
                    prof = store.load_json(self._pfile(n))
                    self.profiles[n] = self._merge_profile(prof, n)
            self.refresh_default_profiles()
            if self.option["OfficeProfileIndex"] > 2 or self.option["GamingProfileIndex"] > 2:
                self.load_default()
        else:
            self.load_default()
        if not self.pf.turbo_support and self.option["OperatingMode"] == R.MODE_TURBO:
            self.option["OperatingMode"] = self.pf.default_mode

    @staticmethod
    def _merge_profile(prof, name):
        p = copy.deepcopy(DEFAULT_PROFILE)
        p["Name"] = name
        if prof:
            for k, v in prof.items():
                if isinstance(v, dict) and isinstance(p.get(k), dict):
                    p[k].update(v)
                else:
                    p[k] = v
        return p

    def _refresh_mode(self, name, cname, pl, table, skip):
        p = copy.deepcopy(DEFAULT_PROFILE)
        p.update({"Activated": False, "Name": name, "CustomizeName": cname})
        p["FAN"].update({"FanSwitchSpeed": 300, "TableName": table, "SkipSafetyAbnormalProtection": skip})
        p["CPU"].update({"PL1": pl["PL1"], "PL2": pl["PL2"], "TccOffset": 5, "AmdSPL": pl["PL1"],
                         "AmdSPPT": pl["PL2"], "AmdTccTarget": 95})
        self.profiles[name] = p
        store.save_json(self._pfile(name), p)

    def refresh_default_profiles(self):
        spec = [("Mode1_Profile1", "1", "gaming", "M1T1", 0), ("Mode1_Profile2", "2", "gaming", "M1T2", 0),
                ("Mode1_Profile3", "3", "gaming", "M1T3", 0), ("Mode2_Profile1", "1", "office", "M2T1", 0),
                ("Mode2_Profile2", "2", "office", "M2T2", 1), ("Mode2_Profile3", "3", "office", "M2T3", 1)]
        for name, cname, mode, table, skip in spec:
            if not (self.profiles.get(name) or {}).get("Activated"):
                self._refresh_mode(name, cname, self.pl_default[mode], table, skip)

    def load_default(self):
        self.option = dict(DEFAULT_OPTION)
        self.option["OperatingMode"] = self.pf.default_mode
        self.option["GamingProfileIndex"] = 1
        self.option["OfficeProfileIndex"] = 0
        self.option["TurboProfileIndex"] = 0
        store.save_json(self._pfile("MainOption"), self.option)
        self.profiles = {}
        self.refresh_default_profiles()

    def save_option(self, **kw):
        self.option.update(kw)
        store.save_json(self._pfile("MainOption"), self.option)

    def sync_bios(self):
        self.nvram.set("ApExistFlag", 1)
        pm = self.nvram.get("PowerMode") if self.nvram.verified else None
        if pm is not None and pm != 0xFF:
            if pm in (0, 1, 2) and self.option["OperatingMode"] != pm:
                self.save_option(OperatingMode=pm)
        elif pm == 0xFF:
            self.save_option(OperatingMode=self.pf.default_mode)
        self.ec.set_bit(R.AP_EXIST, 0, True)

    # -- profile application ---------------------------------------------------------
    def init(self):
        mode = self.option["OperatingMode"]
        self.refresh_current_profile(mode)
        self.set_user_profile(mode)

    def refresh_current_profile(self, mode):
        if mode == R.MODE_GAMING:
            idx, m = self.option["GamingProfileIndex"], 1
        elif mode == R.MODE_OFFICE:
            idx, m = self.option["OfficeProfileIndex"], 2
        else:
            return        # turbo keeps the previous profile (GCUService behaviour)
        idx = min(max(idx, 0), 2)
        name = f"Mode{m}_Profile{idx + 1}"
        table = f"M{m}T{idx + 1}"
        p = self.profiles[name]
        c = self.custom.get(table, {})
        cpu = p["CPU"]
        for k in ("PL1", "PL2", "PL1_dc", "PL2_dc", "PL1_Enabled", "PL2_Enabled", "PL1_dc_Enabled",
                  "PL2_dc_Enabled", "PL1_S2", "PL2_S2", "PL1_S2_Enabled", "PL2_S2_Enabled"):
            if k in c:
                cpu[k] = c[k]
        cpu["AmdSPL"] = c.get("PL1", cpu["AmdSPL"])
        cpu["AmdSPPT"] = c.get("PL2", cpu["AmdSPPT"])
        gpu = p["GPU"]
        if self.pf.project_id == 0x1704 and m == 1:
            gpu.update({"ConfigurableTGPSwitch": 1, "ConfigurableTGPTarget": (0x23, 0x23, 0x32)[idx], "DynamicBoostSwitch": 1,
                        "DynamicBoost": (0, 0xF, 0xF)[idx]})
        else:
            gpu.update({"ConfigurableTGPTarget": c.get("CTGP", 0), "ConfigurableTGPSwitch": c.get("CTGP_Switch", 0),
                        "DynamicBoost": c.get("DB", 0), "DynamicBoostSwitch": c.get("DB_Switch", 0),
                        "ConfigurableTGPTarget_S2": c.get("CTGP2", 0), "ConfigurableTGPSwitch_S2": c.get("CTGP2_Switch", 0),
                        "DynamicBoost_S2": c.get("DB2", 0), "DynamicBoostSwitch_S2": c.get("DB2_Switch", 0)})
        self.option["WhisperModeSetting"] = c.get("WM", 0)
        self.option["WhisperModeSwitch"] = c.get("WM_Switch", 0)
        self.current = p

    def set_fan_mode(self, mode):
        boost = self.option.get("FanBoostEnable") == 1
        base = R.MODE_BYTE.get(mode, 0)
        self.ec.write(R.FAN_MODE, base | (0x40 if boost else 0))

    def set_user_profile(self, mode):
        with self.lock:
            self.set_fan_mode(mode)
            p = self.current
            if not p:
                return
            self.ec.set_bit(R.FAN_CTRL_7C5, 4, p["FAN"].get("SkipSafetyAbnormalProtection") == 1)
            self.tables.apply(p["FAN"]["TableName"])
            thermal = False
            if self.pf.balanced_protect:
                if mode == R.MODE_GAMING:
                    self.balanced_protect_mode({0: 1, 1: 2, 2: 3}.get(self.option["GamingProfileIndex"], 0))
                else:
                    self.balanced_protect_mode(0)
                thermal = bool(self.ec.read(R.BALANCED_PROTECT) & 0x40)
            cpu = p["CPU"]
            if self.pf.amd:
                if self.ac_online:
                    if cpu["PL1_Enabled"]:
                        self.ec.write(R.PL1, cpu["AmdSPL"])
                    if cpu["PL2_Enabled"]:
                        self.ec.write(R.PL2, cpu["AmdSPPT"])
                else:
                    if cpu["PL1_Enabled"]:
                        self.ec.write(R.PL1, 0)
                    if cpu["PL2_Enabled"]:
                        self.ec.write(R.PL2, 0)
            elif self.ac_online:
                if thermal and cpu["PL1_S2_Enabled"]:
                    self.ec.write(R.PL1, cpu["PL1_S2"])
                elif cpu["PL1_Enabled"]:
                    self.ec.write(R.PL1, cpu["PL1"])
                if thermal and cpu["PL2_S2_Enabled"]:
                    self.ec.write(R.PL2, cpu["PL2_S2"])
                elif cpu["PL2_Enabled"]:
                    self.ec.write(R.PL2, cpu["PL2"])
            else:
                if cpu["PL1_dc_Enabled"]:
                    self.ec.write(R.PL1, cpu["PL1_dc"])
                if cpu["PL2_dc_Enabled"]:
                    self.ec.write(R.PL2, cpu["PL2_dc"])
            if self.pf.nv_gpu:
                self.apply_gpu(p, thermal)
            log.info("profile applied: mode=%s table=%s", MODE_NAMES.get(mode), p["FAN"]["TableName"])

    def apply_gpu(self, p, thermal):
        g = p["GPU"]
        if self.ac_online:
            if thermal and (g["DynamicBoost_S2"] == 1 or g["ConfigurableTGPSwitch_S2"] == 1):
                self.set_db_switch(g["DynamicBoostSwitch_S2"], g["DynamicBoost_S2"])
                self.gpu.db_fun_ctrl(1)
                self.gpu.ctgp_target(g["ConfigurableTGPTarget_S2"], 0)
                self.gpu.ctgp_fun_ctrl(g["ConfigurableTGPSwitch_S2"])
            else:
                self.set_db_switch(g["DynamicBoostSwitch"], g["DynamicBoost"])
                self.gpu.db_fun_ctrl(1)
                self.gpu.ctgp_target(g["ConfigurableTGPTarget"], 0)
                self.gpu.ctgp_fun_ctrl(g["ConfigurableTGPSwitch"])
        else:
            self.set_db_switch(0, 0)
            self.ec.set_bit(R.GPU_FEAT_CTRL, 0, False)
            self.gpu.ctgp_target(0, 0)
            self.gpu.ctgp_fun_ctrl(0)

    def set_db_switch(self, on, value):
        v = value if on == 1 else 0
        self.gpu.db_tpp_target(v)
        self.gpu.db_max_tgp(v)
        self.gpu.db_enable(on)

    def balanced_protect_mode(self, n):
        v = self.ec.read(R.BALANCED_PROTECT) & 0xCF
        if n in (1, 2, 3):
            v += n << 4
        self.ec.write(R.BALANCED_PROTECT, v)

    # -- user actions -------------------------------------------------------------------
    def user_set_mode(self, mode, osd=False):
        if mode not in self.MODES:
            raise ValueError("mode 0..2")
        if mode == R.MODE_TURBO and not self.pf.turbo_support:
            raise ValueError("turbo mode not supported")
        with self.lock:
            self.option["OperatingMode"] = mode
            self.refresh_current_profile(mode)
            self.set_user_profile(mode)
            self.save_option(OperatingMode=mode)
            self.nvram.set("PowerMode", mode)
        self.notify("mode", {"mode": mode, "osd": osd})

    def set_profile_index(self, mode, idx):
        if not 0 <= idx <= 2:
            raise ValueError("profile index 0..2")
        key = {R.MODE_GAMING: "GamingProfileIndex", R.MODE_OFFICE: "OfficeProfileIndex",
               R.MODE_TURBO: "TurboProfileIndex"}[mode]
        self.save_option(**{key: idx})
        self.user_set_mode(mode)

    def set_fan_boost(self, on):
        with self.lock:
            self.save_option(FanBoostEnable=1 if on else 0)
            self.set_fan_mode(self.option["OperatingMode"])
        self.notify("fanboost", {"on": bool(on)})

    def restore(self):
        with self.lock:
            self.load_default()
            self.init()
        self.notify("status", {})

    def mode_switch_key(self):
        """SetModeSwitchChange — Fn mode key cycles Office -> Gaming -> Turbo -> Office."""
        m = self.option["OperatingMode"]
        if not self.pf.turbo_support:
            nxt = R.MODE_GAMING if m == R.MODE_OFFICE else R.MODE_OFFICE
        else:
            nxt = {R.MODE_OFFICE: R.MODE_GAMING, R.MODE_GAMING: R.MODE_TURBO, R.MODE_TURBO: R.MODE_OFFICE}[m]
        self.user_set_mode(nxt, osd=True)

    def fan_boost_from_ec(self, off=False):
        if off:
            on = False
        else:
            on = bool(self.ec.read(R.FAN_MODE) & 0x40)
        self.save_option(FanBoostEnable=1 if on else 0)
        self.set_fan_mode(self.option["OperatingMode"])
        self.notify("fanboost", {"on": on, "osd": True})

    def power_status_change(self, online):
        self.ac_online = online
        with self.lock:
            self.init()

    def update_profile(self, name, data):
        """Edit of a profile from the UI (PL values, GPU features, fan switches)."""
        if name not in self.profiles:
            raise KeyError(name)
        p = self.profiles[name]
        for sect in ("CPU", "GPU", "FAN"):
            for k, v in (data.get(sect) or {}).items():
                if k in p[sect]:
                    p[sect][k] = type(p[sect][k])(v) if not isinstance(p[sect][k], bool) else bool(v)
        if "CustomizeName" in data:
            p["CustomizeName"] = str(data["CustomizeName"])[:32]
        p["Activated"] = True
        store.save_json(self._pfile(name), p)
        # customised PL values also become the table customize values (UI edits them per table)
        t = p["FAN"]["TableName"]
        c = self.custom.setdefault(t, {})
        for k in ("PL1", "PL2", "PL1_dc", "PL2_dc"):
            if k in (data.get("CPU") or {}):
                c[k] = p["CPU"][k]
            if k + "_Enabled" in (data.get("CPU") or {}):
                c[k + "_Enabled"] = p["CPU"][k + "_Enabled"]
        tb = self.tables.tables.get(t)
        if tb is not None:
            for k in ("PL1", "PL2", "PL1_dc", "PL2_dc"):
                if c.get(k + "_Enabled"):
                    tb[k] = str(c.get(k, 0))
                elif k + "_Enabled" in c:
                    tb[k] = "NA"
            self.tables.save(tb)
        self.init()
        return p

    def update_table(self, name, data):
        t = self.tables.update(name, data)
        if self.current and self.current["FAN"]["TableName"] == name:
            self.tables.apply(name)
        return t

    def restore_table(self, name):
        t = self.tables.restore_default(name)
        if t and self.current and self.current["FAN"]["TableName"] == name:
            self.tables.apply(name)
        self.refresh_customize_values()
        return t

    def shutdown(self):
        """Disable / Uninstall: give fan control back to the EC."""
        try:
            self.tables.disable()
            self.ec.set_bit(R.AP_EXIST, 0, False)
            self.set_fan_mode(self.pf.default_mode)
        except Exception as e:  # noqa: BLE001
            log.warning("shutdown: %s", e)

    # -- status ----------------------------------------------------------------------------
    def status(self):
        fm = self.ec.read(R.FAN_MODE)
        ec_mode = R.MODE_TURBO if fm & 0x10 else (R.MODE_OFFICE if fm & 0x80 else R.MODE_GAMING)
        cur = self.current or {}
        return {
            "manager": self.manager,
            "custom_support": False,
            "table_names": self.TABLE_NAMES,
            "current_profile": cur.get("Name"),
            "mode": self.option["OperatingMode"],
            "ec_mode": ec_mode,
            "fan_boost": bool(self.option.get("FanBoostEnable")),
            "profile_index": {"gaming": self.option["GamingProfileIndex"], "office": self.option["OfficeProfileIndex"],
                              "turbo": self.option["TurboProfileIndex"]},
            "turbo_support": self.pf.turbo_support,
            "current_table": (cur.get("FAN") or {}).get("TableName"),
            "ac_online": self.ac_online,
            "pl_default": self.pl_default,
        }
