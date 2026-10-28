"""Platform identification — port of MyEcCtrl.Get*FromEC / GetProject2ExID / ProjectID enum."""
import glob
import os
import sys

from . import regs as R

PROJECT_NAMES = {
    0x12: "PH4TRX1", 0x13: "PH4TUX1", 0x14: "PH4TQx1", 0x15: "PH6TRX1", 0x16: "PH6TQxx",
    0x17: "PHxAxxx", 0x1701: "PH4ARxx", 0x1702: "PH4AUxx", 0x1703: "PH4AXxx", 0x1704: "PH6AQxx",
    0x1705: "PH6ARxx", 0x1706: "PH6AGxx", 0x1707: "PH4AUxf",
    0x18: "PHxPxxx", 0x1801: "PH4PRxx", 0x1802: "PH4PUxx", 0x1803: "PH4PGx1", 0x1804: "PH4PGx2",
    0x1805: "PH6PRxx", 0x1806: "PH6PGEx", 0x1807: "PH6PG0x", 0x1808: "PH6PG3x", 0x1809: "PH6PG7x",
    0x180A: "PH4AQE3", 0x180B: "PH6PG0x150W", 0x180C: "PH6PG3x150W", 0x180D: "PH6PG7x150W",
}
# Names for the window only, for projects that are not in the tables of GCUService 1.0.2.70. project_name stays the
# raw "0x.." for them: it names the folder of the saved fan curves and the backup check.
DISPLAY_NAMES = {0x10: "MAIBENBEN Tsunami", 0x1A: "MECHREVO Kuangshi / Jiguang B2"}
# Support level shown in the window: "tested" — checked on real hardware with this program; "known" — in the
# platform tables of the original service this program was ported from; anything else is "experimental".
TESTED_IDS = {0x10}
# Platforms of the newer official service 1.2 (its code is protected, so nothing could be taken over from it):
# they report RamFan 1.5 like the others and run with the same port, but are untested.
SERVICE_1_2_IDS = {0x1A}
# Single-colour keyboard backlight through EC 0x78C (MyControlCenter.SingleColorKeyboard): projects 0x12..0x14 in
# GCUService 1.0.2.70; 0x1A (MECHREVO Kuangshi / Jiguang B2, Aurora X) from the log of its Control Center 5.56
# ("SingleZone | SetBrightness_EC | ADDR_SINGLEKBL_ENABLE 0x78C"). An ITE RGB keyboard is still looked for first.
SINGLE_COLOR_EC_IDS = {0x12, 0x13, 0x14, 0x1A}
# ProjectIdExtensions.CommercialProjectIDs — all of them select the "_CML" fan manager
COMMERCIAL_IDS = {9, 0xE, 0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x1701, 0x1702, 0x1703, 0x1704, 0x1705,
                  0x1707, 0x18, 0x1801, 0x1802, 0x1803, 0x1804, 0x1805, 0x1806, 0x1807, 0x1808,
                  0x1809, 0x180A, 0x180B, 0x180C, 0x180D}
COMMERCIAL_20DB_IDS = {9, 0xE, 0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x1701, 0x1702, 0x1703, 0x1704, 0x1705, 0x1707}
SINGLE_COLOR_KB_IDS = {9, 0xE, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18}

ADAPTER_WATT = {0x00: 330, 0x08: 230, 0x10: 180, 0x18: 150, 0x20: 120, 0x28: 90, 0x30: 65, 0x38: 40, 0x40: 280}


def adapter_watt(ec):
    return ADAPTER_WATT.get(ec.read(R.ADAPTER_CAPS) & 0x78, 150)


def project2ex_id(ec, pid):
    if pid not in (0x17, 0x18):
        return pid
    sys_id = ec.read(R.SYSTEM_ID) & 0x80
    gpu_mod = ec.read(R.GPU_MODULE_ID) & 0x1F
    mod = ec.read(R.MODULE_ID) & 0x01
    mod2 = ec.read(R.MODULE_ID) & 0xF0
    rom = ec.read(R.ROM_ID) & 0x01
    rom2 = ec.read(R.ROM_ID2)
    watt = adapter_watt(ec)
    if pid == 0x17:
        if sys_id == 0 and rom == 0:
            if mod == 0:
                return 0x1701
            if mod == 1:
                return 0x1707 if rom2 == 3 else 0x1702
            return pid
        if sys_id == 0x80 and rom == 0:
            return 0x1703
        if sys_id == 0 and rom == 1:
            return 0x1705 if mod == 0 else pid
        if sys_id == 0x80 and rom == 1:
            return 0x1706 if mod2 in (0x30, 0x70, 0xA0) else 0x1704
        return pid
    # 0x18
    if sys_id == 0 and rom == 0:
        if mod == 0:
            return 0x1801
        return 0x1802 if mod == 1 else pid
    if sys_id == 0x80 and rom == 0:
        if rom2 == 1:
            return 0x1803
        return 0x180A if rom2 == 4 else 0x1804
    if sys_id == 0 and rom == 1:
        return 0x1805
    if sys_id == 0x80 and rom == 1:
        if gpu_mod == 8:
            return 0x1806
        if gpu_mod in (0x10, 0x15, 0x11):
            return 0x180B if watt == 150 else 0x1807
        if gpu_mod == 0x0C:
            return 0x180C if watt == 150 else 0x1808
        if gpu_mod == 0x12:
            return 0x180D if watt == 150 else 0x1809
    return pid


def pci_vendors_display():
    if sys.platform == "win32":
        from .win.winplat import display_vendors
        return display_vendors()
    out = set()
    for d in glob.glob("/sys/bus/pci/devices/*"):
        try:
            cls = open(os.path.join(d, "class")).read().strip()
            if cls.startswith("0x03"):
                out.add(open(os.path.join(d, "vendor")).read().strip().lower())
        except OSError:
            pass
    return out


def is_nv_gpu():
    return "0x10de" in pci_vendors_display()


def is_amd_platform():
    # MyEcCtrl.IsAMDPlatform reads PCI 00:00.0 vendor id
    if sys.platform == "win32":
        from .win.winplat import cpu_vendor
        return cpu_vendor() == "AuthenticAMD"
    try:
        return open("/sys/bus/pci/devices/0000:00:00.0/vendor").read().strip().lower() == "0x1022"
    except OSError:
        return False


class Platform:
    def __init__(self, ec):
        self.ec = ec
        self.project_raw = ec.read(R.PROJECT_ID)
        self.project_id = project2ex_id(ec, self.project_raw)
        self.project_name = PROJECT_NAMES.get(self.project_id, f"0x{self.project_id:X}")
        self.ramfan15 = bool(ec.bit(R.EC_CAPS_78E, 6))
        self.turbo_support = bool(ec.bit(R.ADAPTER_CAPS, 1))
        self.default_mode = R.MODE_GAMING if ec.read(R.DEFAULT_MODE) & 0x10 else R.MODE_OFFICE
        self.qkey_define = bool(ec.read(R.DEFAULT_MODE) & 0x02)
        self.nv_gpu = is_nv_gpu()
        self.amd = is_amd_platform()
        self.adapter_watt = adapter_watt(ec)
        self.typec_prio_support = bool(ec.bit(R.EC_CAPS_742, 5))
        self.rgb_lightbar = bool(ec.bit(R.EC_CAPS_78E, 4))
        self.commercial = self.project_id in COMMERCIAL_IDS
        self.balanced_protect = self.project_id in (0x1807, 0x1808, 0x1809)
        self.display_name = DISPLAY_NAMES.get(self.project_id, self.project_name)
        self.support = ("tested" if self.project_id in TESTED_IDS else
                        "experimental" if self.project_id in SERVICE_1_2_IDS or self.project_id not in PROJECT_NAMES else "known")

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != "ec"}


def dmi(field):
    if sys.platform == "win32":
        from .win.winplat import dmi as wdmi
        return wdmi(field)
    try:
        return open(f"/sys/class/dmi/id/{field}").read().strip()
    except OSError:
        return ""
