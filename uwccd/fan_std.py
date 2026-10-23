"""Operating modes for non-commercial projects: Office / Gaming / Turbo / Custom.

Port of MyFanManager_RamFan1p5 + FanTable_Manager1p5 — the manager GCUService picks when the EC
reports RamFan 1.5 but the project is NOT in ProjectIdExtensions.CommercialProjectIDs
(e.g. PH6TQxx, PH6AGxx, and boards this Control Center build does not know by ID).

Compared with the commercial (_CML) manager it has:
  * a fourth mode, Custom (OperatingMode 3), with five user slots Mode4_Profile1..5 / tables M4T1..M4T5;
    in the EC it is the Gaming fan mode plus bit 7 of 0x726;
  * PL4 (0x785) and the CPU TCC offset (0x786, bit 7 = enable) in every profile;
  * limits from the firmware "Smart APC" table (ACPI method SMRW): PL1/PL2/PL4 maxima, TCC offset maximum,
    cTGP range above the default TGP, Dynamic Boost maximum;
  * an optional fan "switch speed" (0x787).
"Super performance" (LoadOverClockingValue of the original, there a switch of the Custom slots) is a separate
switch here that works on top of any mode: the EC runs the Turbo fan mode with the factory Turbo fan table and the
graphics card gets cTGP maximum + Dynamic Boost; the power limits of the mode's profile stay. RAM overclocking
(BIOS variable) is a separate switch as well — see settings.py.
Not ported: GPU core/memory clock offsets (NVAPI), CPU core voltage offset (Intel OC SDK), WhisperMode.
"""
import copy
import threading
import logging
import os

from . import regs as R
from . import store
from .monitor import tjmax
from .fan import (DEFAULT_PROFILE, MODE_NAMES, FanTables, PowerManager, copy_table)
from .hw import dmi

log = logging.getLogger("uwccd.fan")

MODE_CUSTOM = 3
STD_TABLE_NAMES = [f"M{m}T{t}" for m in (1, 2, 3, 4) for t in range(1, 6)]
TABLE_SOURCE = {"1": "DefaultFanTable_Gaming", "2": "DefaultFanTable_Office", "3": "DefaultFanTable_Turbo",
                "4": "DefaultFanTable_Gaming"}
MODE_DEFAULT_TABLE = {R.MODE_OFFICE: "DefaultFanTable_Office", R.MODE_GAMING: "DefaultFanTable_Gaming",
                      R.MODE_TURBO: "DefaultFanTable_Turbo", MODE_CUSTOM: "DefaultFanTable_Gaming"}
# (profile, CustomizeName, PL default set, fan table)
PROFILE_SPEC = ([(f"Mode1_Profile{i}", str(i), "gaming", f"M1T{i}") for i in (1, 2)] +
                [(f"Mode2_Profile{i}", str(i), "office", f"M2T{i}") for i in (1, 2)] +
                [(f"Mode3_Profile{i}", str(i), "turbo", f"M3T{i}") for i in (1, 2)] +
                [(f"Mode4_Profile{i}", str(i), "gaming", f"M4T{i}") for i in range(1, 6)])
INDEX_KEY = {R.MODE_GAMING: "GamingProfileIndex", R.MODE_OFFICE: "OfficeProfileIndex",
             R.MODE_TURBO: "TurboProfileIndex", MODE_CUSTOM: "CustomProfileIndex"}
MODE_PREFIX = {R.MODE_GAMING: 1, R.MODE_OFFICE: 2, R.MODE_TURBO: 3, MODE_CUSTOM: 4}
SLOTS = {R.MODE_GAMING: 2, R.MODE_OFFICE: 2, R.MODE_TURBO: 2, MODE_CUSTOM: 5}
STD_MODE_NAMES = {**MODE_NAMES, MODE_CUSTOM: "custom"}

REG_TCC_OFFSET = 0x786          # bit7 enable, bits0-6 offset below TjMax
REG_FAN_SWITCH_SPEED = 0x787    # bit7 enable, bits0-6 speed / 100 rpm
REG_CUSTOM_FLAG = 0x726         # bit7: Custom mode
REG_FAN_SAFETY = 0x7A5          # bit3: fan safety protection active
REG_TCC_DEFAULT = (0x7D8, 0x7D9, 0x7DA)   # gaming, office, turbo
REG_VRM_LIMIT = (0x753, 0x754)


class FanTablesStd(FanTables):
    """FanTable_Manager1p5: 20 user tables, each a plain copy of the EC default of its mode."""

    NAMES = STD_TABLE_NAMES

    def _ec_version_changed(self):
        """RegistryCtrl.IsNewEcVersion — regenerate the tables after an EC update."""
        ver = dmi("ec_firmware_release") or dmi("bios_version")
        p = os.path.join(self.dir, ".ec_version")
        try:
            with open(p) as f:
                old = f.read().strip()
        except OSError:
            old = None
        if ver and old != ver:
            os.makedirs(self.dir, exist_ok=True)
            with open(p, "w") as f:
                f.write(ver)
            return old is not None
        return False

    def _defaults_invalid(self):
        if len(self.defaults) < 3:
            return True
        for t in self.defaults.values():
            for k in ("CPU", "GPU") if self.nv else ("CPU",):
                duties = [p["Duty"] for p in t[k]]
                if all(d == 0 for d in duties):
                    return True
                if any(duties[i] > duties[i + 1] for i in range(15)):
                    return True
        return False

    def init(self):
        self.seed_from_share()
        if self._ec_version_changed():
            log.info("EC firmware changed — regenerating fan tables")
            self.refresh()
            return
        for n in ("DefaultFanTable_Gaming", "DefaultFanTable_Office", "DefaultFanTable_Turbo"):
            t = self.load(n)
            if t:
                self.defaults[n] = t
        if all(os.path.exists(self._file(n)) for n in self.NAMES) and not self._defaults_invalid():
            for n in self.NAMES:
                self.tables[n] = self.load(n)
        else:
            self.refresh()

    def refresh(self):
        self.refresh_default_all()
        if len(self.defaults) < 3:
            log.error("default fan tables unavailable")
            return
        for n in self.NAMES:
            self.tables[n] = copy_table(self.defaults[TABLE_SOURCE[n[1]]], n)
            self.save(self.tables[n])

    def restore_default(self, name):
        src = self.defaults.get(TABLE_SOURCE.get(name[1:2], ""))
        if name not in self.NAMES or not src:
            return None
        t = copy_table(src, name)
        self.tables[name] = t
        self.save(t)
        return t

    def write_ec_table(self, t):
        # FanTable_Manager1p5.SetEcFanTable writes Duty*2 as is (no 0xFF clamp like the _CML variant)
        for kind, up, down, duty, enabled in (("CPU", R.FT_CPU_UP, R.FT_CPU_DOWN, R.FT_CPU_DUTY, True),
                                               ("GPU", R.FT_GPU_UP, R.FT_GPU_DOWN, R.FT_GPU_DUTY, self.nv)):
            pts = t.get(kind)
            if not enabled or not pts:
                continue
            for i in range(16):
                self.ec.write(up + i, pts[i + 1]["UpT"] if i < 15 else 0xFF)
                if i < 15:
                    self.ec.write(down + i + 1, pts[i]["DownT"])
                self.ec.write(duty + i, (pts[i]["Duty"] * 2) & 0xFF)

    def apply_default(self, name):
        """Fan safety protection: run the EC default table of the mode."""
        t = self.defaults.get(name)
        if t:
            self.apply_table(t)

    def pl_defaults(self, name):
        return {}


class PowerManagerStd(PowerManager):
    """MyFanManager_RamFan1p5."""

    manager = "std"
    TABLE_NAMES = STD_TABLE_NAMES
    MODES = (R.MODE_OFFICE, R.MODE_GAMING, R.MODE_TURBO, MODE_CUSTOM)

    def __init__(self, ec, platform, nvram, notify):
        super().__init__(ec, platform, nvram, notify)
        self.tables = FanTablesStd(ec, platform)
        self.smapc = {}
        self.limits = {}
        self.tcc_default = {}
        self.fan_safety = False
        self.tcc_extended = False      # settings: allow a CPU temperature limit down to TJMAX - TCC_EXTENDED
        self.gputemp = None            # GpuTargetTemperature (set by the service)

    # The original UI let the per-profile "Temperature Limit" go past the Smart APC TccOffset (5 on MAIBENBEN
    # project 0x10): its saved profiles hold 10 and 15. So: at least 15 (Tjmax - 15 = 85 °C), 40 when extended.
    TCC_STANDARD, TCC_EXTENDED = 15, 40

    def set_tcc_extended(self, on):
        self.tcc_extended = bool(on)
        if self.limits:
            self.limits["tcc_max"] = self._tcc_max()

    def _tcc_max(self):
        fw = self.smapc.get("TccOffset", 0)
        return max(fw, self.TCC_EXTENDED if self.tcc_extended else self.TCC_STANDARD)

    # -- defaults and limits ------------------------------------------------------------------------
    def read_limits(self):
        self.read_pl_defaults()
        g, o, t = (self.ec.read(a) for a in REG_TCC_DEFAULT)
        self.tcc_default = {"gaming": g, "office": o, "turbo": t}
        for k, v in self.tcc_default.items():
            self.pl_default[k]["TCC"] = v
        try:
            sm = self.ec.smart_apc_table()
            if sm.get("PL4", 0) == 0 or all(v == 0xFF for v in sm.values()):   # CheckIvalidSmartAPCTable
                raise ValueError(f"invalid table {sm}")
            sm = {k: (0 if v == 0xFF else v) for k, v in sm.items()}            # CheckInvalidSmartApcTable
            src = "firmware"
        except Exception as e:  # noqa: BLE001
            log.warning("Smart APC table unavailable (%s) — limits taken from the EC PL defaults", e)
            tb = self.pl_default["turbo"]
            sm = {"PL1": max(tb["PL1"], self.pl_default["gaming"]["PL1"]),
                  "PL2": max(tb["PL2"], self.pl_default["gaming"]["PL2"]),
                  "PL4": max(tb["PL4"], tb["PL2"]), "TccOffset": max(15, *self.tcc_default.values()),
                  "ConfigurableTGP": 0, "DynamicBoost": 0, "TargetTemperature": 87, "DefaultTGP": 0,
                  "DynamicBoostCpuTdp": 0}
            src = "ec-defaults"
        self.smapc = sm
        self.limits = {
            "source": src,
            "pl_min": 10,
            "pl1_max": sm["PL1"], "pl2_max": sm["PL2"], "pl4_max": sm["PL4"],
            "tcc_fw_max": sm["TccOffset"], "tcc_max": 0, "tjmax": tjmax(),
            "tgp_default": sm["DefaultTGP"], "tgp_max": sm["DefaultTGP"] + sm["ConfigurableTGP"],
            "ctgp_support": sm["ConfigurableTGP"] > 0, "db_max": sm["DynamicBoost"],
            "db_support": sm["DynamicBoost"] > 0,
        }
        self.limits["tcc_max"] = self._tcc_max()
        log.info("custom-mode limits (%s): %s", src, self.limits)

    def _refresh_mode(self, name, cname, pl, table, skip=0):
        """MyFanManager_RamFan1p5.RefreshMode (generic customer branch)."""
        sm, lim = self.smapc, self.limits
        p = copy.deepcopy(DEFAULT_PROFILE)
        p.update({"Activated": False, "Name": name, "CustomizeName": cname, "OverClockingEnabled": 0})
        p["FAN"].update({"FanSwitchSpeedEnabled": 0, "FanSwitchSpeed": 300, "TableName": table,
                         "SkipSafetyAbnormalProtection": 0})
        p["CPU"].update({"PL1": pl["PL1"], "PL2": pl["PL2"], "PL4": pl["PL4"], "TccOffsetSwitch": 0,
                         "TccOffset": pl.get("TCC", 5), "AmdSPL": pl["PL1"], "AmdSPPT": pl["PL2"],
                         "AmdFPPT": pl["PL4"], "AmdTccTarget": pl.get("TCC", 95),
                         "PL1_Enabled": True, "PL2_Enabled": True})
        gpu = p["GPU"]
        gpu.update({"ConfigurableTGPSwitch": 0, "ConfigurableTGPTarget": sm["DefaultTGP"],
                    "DynamicBoostSwitch": 0, "DynamicBoost": sm["DynamicBoost"],
                    "DynamicBoostTotalProcessingPowerTarget": 0xFF, "TargetTemperature": sm["TargetTemperature"] or 87})
        sku = self.ec.read(R.GPU_MODULE_ID) & 0x1F
        if name.startswith("Mode1"):
            if sku not in (0x10, 0x15):
                gpu.update({"ConfigurableTGPSwitch": 1, "ConfigurableTGPTarget": lim["tgp_max"]})
        elif name.startswith("Mode3"):
            gpu.update({"ConfigurableTGPSwitch": 1, "ConfigurableTGPTarget": lim["tgp_max"] + sm["DynamicBoost"],
                        "DynamicBoostSwitch": 0})
        elif name.startswith("Mode4"):
            gpu.update({"ConfigurableTGPSwitch": 1, "ConfigurableTGPTarget": lim["tgp_max"],
                        "DynamicBoostSwitch": 1 if sm["DynamicBoost"] else 0, "DynamicBoost": sm["DynamicBoost"]})
        self.profiles[name] = p
        store.save_json(self._pfile(name), p)

    def refresh_customize_values(self):
        self.custom = {}

    def load_profile_all(self):
        self.read_limits()
        if os.path.isdir(self.dir) and os.path.exists(self._pfile("MainOption")):
            self.option = {**self.option, **(store.load_json(self._pfile("MainOption"), {}) or {})}
            for name, *_ in PROFILE_SPEC:
                prof = store.load_json(self._pfile(name))
                self.profiles[name] = self._merge_profile(prof, name)
            self.refresh_default_profiles()
        else:
            self.load_default()
        for mode, key in INDEX_KEY.items():
            if not 0 <= int(self.option.get(key, 0)) < SLOTS[mode]:
                self.option[key] = 0
        if not self.pf.turbo_support and self.option["OperatingMode"] == R.MODE_TURBO:
            self.option["OperatingMode"] = self.pf.default_mode
        if self.option["OperatingMode"] not in self.MODES:
            self.option["OperatingMode"] = self.pf.default_mode

    def refresh_default_profiles(self):
        for name, cname, src, table in PROFILE_SPEC:
            if not (self.profiles.get(name) or {}).get("Activated"):
                self._refresh_mode(name, cname, self.pl_default[src], table)

    def load_default(self):
        self.option.update({"OperatingMode": self.pf.default_mode, "GamingProfileIndex": 0, "OfficeProfileIndex": 0,
                            "TurboProfileIndex": 0, "CustomProfileIndex": 0, "FanBoostEnable": 0,
                            "FanSafetyProtectNotify": 0, "DefaultNotify": 0})
        store.save_json(self._pfile("MainOption"), self.option)
        self.profiles = {}
        for name, cname, src, table in PROFILE_SPEC:
            self._refresh_mode(name, cname, self.pl_default[src], table)

    def sync_bios(self):
        self.nvram.set("ApExistFlag", 1)
        self.ec.set_bit(R.AP_EXIST, 0, True)
        if self.option["OperatingMode"] == MODE_CUSTOM:
            return
        pm = self.nvram.get("PowerMode") if self.nvram.verified else None
        if pm is None:
            return
        if pm != 0xFF:
            if pm in (0, 1, 2) and pm != self.option["OperatingMode"]:
                self.save_option(OperatingMode=pm)
        else:
            self.save_option(OperatingMode=self.pf.default_mode)

    # -- profile selection / application ----------------------------------------------------------------
    def profile_name(self, mode, idx=None):
        if idx is None:
            idx = int(self.option.get(INDEX_KEY[mode], 0))
        return f"Mode{MODE_PREFIX[mode]}_Profile{idx + 1}"

    def refresh_current_profile(self, mode):
        self.current = self.profiles[self.profile_name(mode)]

    def overclocking(self, *_):
        """Super performance switch (independent of the mode)."""
        return self.option.get("SuperPerformance") == 1

    def user_set_super(self, on):
        with self.lock:
            self.save_option(SuperPerformance=1 if on else 0)
            self.set_user_profile(self.option["OperatingMode"])
        log.info("super performance %s", "on" if on else "off")
        self.notify("super_performance", {"on": bool(on)})

    def set_fan_mode(self, mode):
        """MyFanManager_RamFan1p5.SetFanMode."""
        boost = 0x40 if self.option.get("FanBoostEnable") == 1 else 0
        if self.overclocking():
            # LoadOverClockingValue(1) -> SetFanMode(2): Turbo fan mode, Custom flag cleared
            self.ec.write(R.FAN_MODE, 0x10 | boost)
            self.ec.set_bit(REG_CUSTOM_FLAG, 7, False)
            return
        if mode == MODE_CUSTOM:
            base = 0x00
        else:
            base = R.MODE_BYTE.get(mode, 0)
        self.ec.write(R.FAN_MODE, base | boost)
        self.ec.set_bit(REG_CUSTOM_FLAG, 7, mode == MODE_CUSTOM)

    def set_tcc(self, value, on):
        self.ec.write(REG_TCC_OFFSET, ((int(value) & 0x7F) | 0x80) if on else 0)

    def set_fan_switch_speed(self, on, speed):
        v = int(speed) // 100
        self.ec.write(REG_FAN_SWITCH_SPEED, (v | 0x80) if (on and v > 0) else 0)

    def set_user_profile(self, mode, user=False):
        with self.lock:
            self.set_fan_mode(mode)
            p = self.current
            if not p:
                return
            oc = self.overclocking()
            self.fan_safety = bool(self.ec.read(REG_FAN_SAFETY) & 0x08)
            if getattr(self, "lc_override", None):          # LiquidHWOC: the EC table for liquid cooling
                self.lc_override(mode)
            elif oc:                                        # LoadOverClockingValue: the factory Turbo table
                self.tables.apply_default("DefaultFanTable_Turbo")
            elif self.fan_safety:
                self.save_option(FanSafetyProtectNotify=1)
                self.tables.apply_default(MODE_DEFAULT_TABLE[mode])
            else:
                self.save_option(FanSafetyProtectNotify=0)
                self.tables.apply(p["FAN"]["TableName"])
            cpu = p["CPU"]
            if self.pf.amd:
                if self.ac_online:
                    self.ec.write(R.PL1, cpu["AmdSPL"])
                    self.ec.write(R.PL2, cpu["AmdSPPT"])
                    self.ec.write(R.PL4, cpu["AmdFPPT"])
                    if cpu["AmdSPL"] >= 75 or cpu["AmdSPPT"] >= 75:
                        self.ec.write(REG_VRM_LIMIT[0], 0x41)
                        self.ec.write(REG_VRM_LIMIT[1], 0x78)
                else:
                    for reg in (R.PL1, R.PL2, R.PL4):
                        self.ec.write(reg, 0)
                self.set_tcc(cpu["AmdTccTarget"], cpu["TccOffsetSwitch"] == 1)
            else:
                if self.ac_online:
                    self.ec.write(R.PL1, cpu["PL1"])
                    self.ec.write(R.PL2, cpu["PL2"])
                    self.ec.write(R.PL4, cpu["PL4"])
                else:                       # 0 = let the EC use its battery limits
                    for reg in (R.PL1, R.PL2, R.PL4):
                        self.ec.write(reg, 0)
                self.set_tcc(cpu["TccOffset"], cpu["TccOffsetSwitch"] == 1)
            if self.pf.nv_gpu and oc and self.ac_online:
                self.apply_gpu_oc(p["GPU"])
            elif self.pf.nv_gpu:
                self.apply_gpu_std(p["GPU"])
                if self.gputemp:
                    g = p["GPU"]
                    threading.Thread(target=self.gputemp.apply, daemon=True, name="gpu-temp",
                                     args=(g.get("TargetTemperatureSwitch") == 1, g.get("TargetTemperature", 87))).start()
            f = p["FAN"]
            self.set_fan_switch_speed(f.get("FanSwitchSpeedEnabled") == 1, f.get("FanSwitchSpeed", 300))
            log.info("profile applied: mode=%s %s table=%s%s", STD_MODE_NAMES.get(mode), p["Name"],
                     "DefaultFanTable_Turbo" if oc else f["TableName"], " (super performance)" if oc else "")

    def apply_gpu_oc(self, g):
        """LoadOverClockingValue(1), generic customer branch: cTGP maximum + Dynamic Boost as cTGP, DB off."""
        lim, base = self.limits, self.smapc["DefaultTGP"]
        if lim.get("ctgp_support"):
            self.gpu.ctgp_fun_ctrl(1)
            self.gpu.ctgp_target(lim["tgp_max"] + self.smapc.get("DynamicBoost", 0), base)
        self.set_db_switch_std(g, False)
        self.gpu.db_fun_ctrl(1)

    def apply_gpu_std(self, g):
        lim, base = self.limits, self.smapc["DefaultTGP"]
        if not self.ac_online:
            self.gpu.ctgp_target(0, base)
            self.gpu.ctgp_fun_ctrl(0)
            self.set_db_switch_std(g, False)
            return
        target = g["ConfigurableTGPTarget"]
        if lim["ctgp_support"]:
            if g["DynamicBoostSwitch"] == 1:
                target = min(target, lim["tgp_max"])
            self.gpu.ctgp_target(target, base)
            self.gpu.ctgp_fun_ctrl(g["ConfigurableTGPSwitch"])
        elif g["DynamicBoostSwitch"] == 1:
            self.gpu.ctgp_target(0, base)
            self.gpu.ctgp_fun_ctrl(0)
        else:
            self.gpu.ctgp_target(target, base)
            self.gpu.ctgp_fun_ctrl(g["ConfigurableTGPSwitch"])
        self.set_db_switch_std(g, lim["db_support"] and g["DynamicBoostSwitch"] == 1)
        self.gpu.db_fun_ctrl(1)

    def set_db_switch_std(self, g, on):
        """SetGpuDynamicBoostSwitch."""
        self.gpu.db_tpp_target(g.get("DynamicBoostTotalProcessingPowerTarget", 0xFF) if on else 0)
        self.gpu.db_max_tgp(g["DynamicBoost"] if on else 0)
        self.gpu.db_enable(1 if on else 0)

    # -- user actions ---------------------------------------------------------------------------------
    def user_set_mode(self, mode, osd=False, next_slot=False):
        if mode not in self.MODES:
            raise ValueError("mode 0..3")
        if mode == R.MODE_TURBO and not self.pf.turbo_support:
            raise ValueError("turbo mode not supported")
        with self.lock:
            if mode == MODE_CUSTOM and next_slot:
                self.option["CustomProfileIndex"] = (int(self.option["CustomProfileIndex"]) + 1) % 5
            if mode != MODE_CUSTOM:
                self.option["FanBoostEnable"] = 0          # UserSet_ModeN -> UserSet_FanBoost(0)
            self.option["OperatingMode"] = mode
            self.refresh_current_profile(mode)
            self.set_user_profile(mode, user=True)
            self.save_option(OperatingMode=mode)
            if mode != MODE_CUSTOM:
                self.nvram.set("PowerMode", mode)
        self.notify("mode", {"mode": mode, "osd": osd, "slot": self.option["CustomProfileIndex"] if mode == MODE_CUSTOM else None})

    def set_profile_index(self, mode, idx):
        if mode not in self.MODES or not 0 <= idx < SLOTS[mode]:
            raise ValueError("profile index out of range")
        self.save_option(**{INDEX_KEY[mode]: idx})
        self.user_set_mode(mode)

    def mode_switch_key(self):
        """ModeSwitchChanged: Office -> Gaming -> Turbo -> Office; in Custom the key steps through the slots."""
        m = self.option["OperatingMode"]
        if m == MODE_CUSTOM:
            self.user_set_mode(MODE_CUSTOM, osd=True, next_slot=True)
        elif not self.pf.turbo_support:
            self.user_set_mode(R.MODE_OFFICE if m == R.MODE_GAMING else R.MODE_GAMING, osd=True)
        else:
            self.user_set_mode({R.MODE_OFFICE: R.MODE_GAMING, R.MODE_GAMING: R.MODE_TURBO,
                                R.MODE_TURBO: R.MODE_OFFICE}[m], osd=True)

    def update_profile(self, name, data):
        """UserSet_Mode_Detail — PL1/PL2/PL4, TCC offset, cTGP, Dynamic Boost, fan switch speed, slot name."""
        if name not in self.profiles:
            raise KeyError(name)
        lim = self.limits
        p = copy.deepcopy(self.profiles[name])
        cpu, gpu, fan = p["CPU"], p["GPU"], p["FAN"]
        c = data.get("CPU") or {}
        mx = {"PL1": lim["pl1_max"], "PL2": lim["pl2_max"], "PL4": lim["pl4_max"]}
        for k in ("PL1", "PL2", "PL4"):
            if k in c:
                v = int(c[k])
                if v != cpu[k] and not lim["pl_min"] <= v <= max(mx[k], lim["pl_min"]):
                    raise ValueError(f"{k} {lim['pl_min']}..{mx[k]} W")
                cpu[k] = v
                cpu["Amd" + {"PL1": "SPL", "PL2": "SPPT", "PL4": "FPPT"}[k]] = v
        if cpu["PL1"] > cpu["PL2"]:                    # CheckInvalidParameter
            cpu["PL2"] = cpu["AmdSPPT"] = cpu["PL1"]
        if cpu["PL4"] < cpu["PL2"]:
            raise ValueError("PL4 must not be lower than PL2")
        if "TccOffsetSwitch" in c:
            cpu["TccOffsetSwitch"] = 1 if c["TccOffsetSwitch"] else 0
        if "TccOffset" in c:
            v = int(c["TccOffset"])
            if not 0 <= v <= max(lim["tcc_max"], 0):
                raise ValueError(f"TCC offset 0..{lim['tcc_max']}")
            cpu["TccOffset"] = v
        g = data.get("GPU") or {}
        if "ConfigurableTGPSwitch" in g:
            gpu["ConfigurableTGPSwitch"] = 1 if g["ConfigurableTGPSwitch"] else 0
        if "ConfigurableTGPTarget" in g:
            v = int(g["ConfigurableTGPTarget"])
            hi = lim["tgp_max"] + (self.smapc["DynamicBoost"] if not gpu["DynamicBoostSwitch"] else 0)
            if not lim["tgp_default"] <= v <= max(hi, lim["tgp_default"]):
                raise ValueError(f"cTGP {lim['tgp_default']}..{hi} W")
            gpu["ConfigurableTGPTarget"] = v
        if "TargetTemperatureSwitch" in g:
            gpu["TargetTemperatureSwitch"] = 1 if g["TargetTemperatureSwitch"] else 0
        if "TargetTemperature" in g:
            v = int(g["TargetTemperature"])
            info = self.gputemp.info() if self.gputemp else None
            lo, hi = (info["min"], info["max"]) if info else (50, 95)
            if v != gpu.get("TargetTemperature") and not lo <= v <= hi:
                raise ValueError(f"GPU temperature limit {lo}..{hi} °C")
            gpu["TargetTemperature"] = v
        if "DynamicBoostSwitch" in g:
            gpu["DynamicBoostSwitch"] = 1 if g["DynamicBoostSwitch"] else 0
        if "DynamicBoost" in g:
            v = int(g["DynamicBoost"])
            if not 0 <= v <= lim["db_max"]:
                raise ValueError(f"Dynamic Boost 0..{lim['db_max']} W")
            gpu["DynamicBoost"] = v
        f = data.get("FAN") or {}
        if "FanSwitchSpeedEnabled" in f:
            fan["FanSwitchSpeedEnabled"] = 1 if f["FanSwitchSpeedEnabled"] else 0
        if "FanSwitchSpeed" in f:
            v = int(f["FanSwitchSpeed"])
            if not 100 <= v <= 12700:
                raise ValueError("fan switch speed 100..12700 rpm")
            fan["FanSwitchSpeed"] = v
        if "CustomizeName" in data:
            n = str(data["CustomizeName"]).strip()[:24]
            p["CustomizeName"] = n or name[-1]
        p["Activated"] = True
        with self.lock:
            self.profiles[name] = p
            store.save_json(self._pfile(name), p)
            if self.current and self.current["Name"] == name:
                self.current = p
                self.set_user_profile(self.option["OperatingMode"], user=True)
        return p

    def restore_profile(self, name):
        """RestoreCurrentProfile for one slot: factory values and the factory fan curve of its table."""
        spec = next((s for s in PROFILE_SPEC if s[0] == name), None)
        if not spec:
            raise KeyError(name)
        _, cname, src, table = spec
        with self.lock:
            self._refresh_mode(name, cname, self.pl_default[src], table)
            self.tables.restore_default(table)
            if self.current and self.current["Name"] == name:
                self.refresh_current_profile(self.option["OperatingMode"])
                self.set_user_profile(self.option["OperatingMode"])
        return self.profiles[name]

    def restore_table(self, name):
        t = self.tables.restore_default(name)
        if t and self.current and self.current["FAN"]["TableName"] == name:
            self.tables.apply(name)
        return t

    def shutdown(self):
        """Disable: default mode, TCC offset and fan switch speed off, Dynamic Boost off."""
        try:
            self.tables.disable()
            self.ec.set_bit(R.AP_EXIST, 0, False)
            self.option["FanBoostEnable"] = 0
            self.set_fan_mode(self.pf.default_mode)
            self.set_tcc(0, False)
            self.set_fan_switch_speed(False, 0)
            if self.pf.nv_gpu:
                self.gpu.db_enable(0)
        except Exception as e:  # noqa: BLE001
            log.warning("shutdown: %s", e)

    def status(self):
        fm = self.ec.read(R.FAN_MODE)
        custom = bool(self.ec.read(REG_CUSTOM_FLAG) & 0x80)
        ec_mode = MODE_CUSTOM if custom else (R.MODE_TURBO if fm & 0x10 else (R.MODE_OFFICE if fm & 0x80 else R.MODE_GAMING))
        cur = self.current or {}
        return {
            "manager": self.manager,
            "mode": self.option["OperatingMode"],
            "ec_mode": ec_mode,
            "fan_boost": bool(self.option.get("FanBoostEnable")),
            "profile_index": {"gaming": self.option["GamingProfileIndex"], "office": self.option["OfficeProfileIndex"],
                              "turbo": self.option["TurboProfileIndex"], "custom": self.option["CustomProfileIndex"]},
            "slots": {"gaming": 2, "office": 2, "turbo": 2, "custom": 5},
            "turbo_support": self.pf.turbo_support,
            "custom_support": True,
            "current_profile": cur.get("Name"),
            "current_table": (cur.get("FAN") or {}).get("TableName"),
            "ac_online": self.ac_online,
            "pl_default": self.pl_default,
            "limits": {**self.limits, "gpu_temp": self.gputemp.cache if self.gputemp else None,
                       "tcc_extended": self.tcc_extended},
            "fan_safety": self.fan_safety,
            "table_names": self.TABLE_NAMES,
            "super_performance": self.overclocking(),
        }
