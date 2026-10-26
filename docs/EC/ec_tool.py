r"""ec_tool - EC register tool for MAIBENBEN Tsunami X629 (Uniwill project 0x10) and similar Uniwill laptops.

Backends (choose with --backend or in ec_tool.json):
  driver   OEM driver UWACPIDriver.sys: \\.\ACPIDriver, IOCTL 0x9C40A488 read / 0x9C40A48C write /
           0x9C40A504 PWUP. Fast (~10 ms), needs the driver and administrator rights.
  wmi      Windows built-in WMI (wmiacpi.sys): root\WMI AcpiTest_MULong.GetSetULong.
           No extra driver, ~125 ms per read / ~150 ms per write, administrator rights.
  service  open-uniwill-cc service HTTP API (read only), token from %ProgramData%\UWCC\run\token.
  auto     driver if available, else wmi.

Commands:
  info                         platform summary (project, capabilities, mode, power, battery, cooler)
  read ADDR [ADDR ...]         read registers; ADDR may be a range: 0x740-0x746
  dump START [LEN]             hex dump (default 256 bytes)
  decode [GROUP ...]           read every known register and decode it (groups: see 'groups')
  groups                       list register groups
  fantable                     decode the EC fan table 0xF00-0xF5F
  watch ADDR [ADDR ...]        print values every --interval seconds (--count N, --csv FILE)
  write ADDR VALUE             write a byte (only registers listed as writable, unless --force)
  bit ADDR BIT on|off          set or clear one bit (same safety rule)
  compare [ADDR ...]           read through two backends (--with BACKEND) and compare
  bench [N]                    measure read speed (N reads of 0x740)
  pwup LEVEL                   call the firmware method PWUP(level) (driver backend only)

Options:
  --backend driver|wmi|service|auto   --with BACKEND (for compare)   --config FILE
  --interval SEC   --count N   --csv FILE   --json   --force   --restore SEC (write/bit: undo after SEC s)

Examples:
  python ec_tool.py info
  python ec_tool.py --backend wmi decode power fans
  python ec_tool.py read 0x783-0x787
  python ec_tool.py watch 0x464 0x465 0x75B --interval 2 --count 30 --csv fans.csv
  python ec_tool.py bit 0x74E 4 on --restore 5          (Fn Lock on for 5 s)
  python ec_tool.py --backend wmi compare --with driver
"""
import argparse
import csv
import ctypes
import json
import os
import struct
import sys
import time

IS_WIN = sys.platform == "win32"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------------------------------------
# Register map: address -> (group, name, description, decoder or None, writable_by_default)
# ---------------------------------------------------------------------------------------------------------
def u8(v):
    return str(v)


def bits(*names):
    def dec(v):
        on = [n for i, n in enumerate(names) if n and v & (1 << i)]
        return ", ".join(on) or "-"
    return dec


def watts(v):
    return f"{v} W"


def flag7(unit):
    return lambda v: (f"on, {v & 0x7F}{unit}" if v & 0x80 else "off")


def fan_mode(v):
    m = "Turbo" if v & 0x10 else "Office" if v & 0x80 else "Gaming/Custom"
    return f"{m}" + (" + FanBoost" if v & 0x40 else "")


def lc_target(unit):
    return lambda v: (f"{v & 0x7F}{unit}" if v & 0x80 else "not valid")


REGS = {
    # battery
    0x408: ("battery", "BAT_DESIGN_VOLT_L", "design voltage, low byte (mV, with 0x409)", None, False),
    0x409: ("battery", "BAT_DESIGN_VOLT_H", "design voltage, high byte", None, False),
    0x434: ("battery", "BAT_CURRENT_L", "battery current, low byte (with 0x435)", None, False),
    0x435: ("battery", "BAT_CURRENT_H", "battery current, high byte", None, False),
    0x494: ("battery", "BAT_ALERT", "battery alert (non-zero = alert)", u8, False),
    0x4A6: ("battery", "BAT_CYCLE_L", "charge cycles, low byte (with 0x4A7)", None, False),
    0x4A7: ("battery", "BAT_CYCLE_H", "charge cycles, high byte", None, False),
    0x7B9: ("battery", "CHARGE_LIMIT_UP", "upper charge limit, bits0..6 % (0 = 100 %), bit7 keep",
            lambda v: f"{v & 0x7F or 100} %", True),
    0x7D0: ("battery", "CHARGE_LIMIT_DOWN", "lower charge limit 1..95 %", lambda v: f"{v} %", True),
    0x7CC: ("battery", "TYPEC_PRIO", "bit7 charge from Type-C first (if 0x742 bit5)", bits(*[None] * 7, "Type-C first"), True),
    0x49F: ("platform", "ADAPTER_CAPS", "bit1 Turbo supported, bits3..6 adapter power code",
            lambda v: f"turbo={'yes' if v & 2 else 'no'}, adapter code {(v >> 3) & 0xF}", False),
    # platform
    0x456: ("platform", "SYSTEM_ID", "system id (bit7)", u8, False),
    0x740: ("platform", "PROJECT_ID", "Uniwill project id (Tsunami X629 = 0x10)", lambda v: f"0x{v:02X}", False),
    0x741: ("platform", "AP_EXIST", "bit0 control application present, bit3 pass key presses to the keyboard",
            bits("app present", None, None, "key presses to KB"), True),
    0x742: ("platform", "EC_CAPS_742", "capabilities: bits2/3/6/7 LED vendor, bit5 Type-C priority support",
            bits(None, None, "LED v.", "LED v.", None, "Type-C prio", "LED v.", "LED v."), False),
    0x74C: ("platform", "BIOS_PROJECT_ID", "project id written by the BIOS", lambda v: f"0x{v:02X}", False),
    0x771: ("platform", "ROM_ID", "ROM id", lambda v: f"0x{v:02X}", False),
    0x772: ("platform", "ROM_ID2", "ROM id 2", lambda v: f"0x{v:02X}", False),
    0x78E: ("platform", "EC_CAPS_78E", "bit4 RGB light bar, bit6 RamFan 1.5, bit7 LED vendor",
            bits(None, None, None, None, "RGB lightbar", None, "RamFan1.5", "LED vendor"), False),
    0x7CA: ("platform", "EC_CAPS_7CA", "bit0 6-bit BIOS project id", bits("6-bit project id"), False),
    0x7D2: ("platform", "GPU_MODULE_ID", "GPU module id", lambda v: f"0x{v:02X}", False),
    0x7D3: ("platform", "MODULE_ID", "module id", lambda v: f"0x{v:02X}", False),
    # modes
    0x751: ("modes", "FAN_MODE", "fan/performance mode: 0x00 Gaming, 0xA0 Office, 0x10 Turbo; bit6 FanBoost", fan_mode, True),
    0x726: ("modes", "BALANCED_PROTECT", "bit3 power-on with AC, bits4..5 protect, bit6 thermal protected, bit7 Custom",
            bits(None, None, None, "AC power-on", "protect", "protect", "thermal protected", "Custom"), False),
    0x706: ("modes", "CUSTOM_MODE", "custom-mode state", lambda v: f"0x{v:02X}", False),
    0x782: ("modes", "DEFAULT_MODE", "bit4 default mode Gaming, bit1 Q-key defined", bits(None, "Q-key", None, None, "default Gaming"), False),
    # power
    0x730: ("power", "PL_DEF_GAMING_PL1", "factory Gaming PL1", watts, False),
    0x731: ("power", "PL_DEF_GAMING_PL2", "factory Gaming PL2", watts, False),
    0x732: ("power", "PL_DEF_GAMING_PL4", "factory Gaming PL4", watts, False),
    0x733: ("power", "PL_DEF_GAMING_DSTATE", "factory Gaming GPU DState", u8, False),
    0x734: ("power", "PL_DEF_OFFICE_PL1", "factory Office PL1", watts, False),
    0x735: ("power", "PL_DEF_OFFICE_PL2", "factory Office PL2", watts, False),
    0x736: ("power", "PL_DEF_OFFICE_PL4", "factory Office PL4", watts, False),
    0x737: ("power", "PL_DEF_OFFICE_DSTATE", "factory Office GPU DState", u8, False),
    0x738: ("power", "TAU_DEF", "default Tau", u8, False),
    0x7A7: ("power", "PL_DEF_TURBO_PL1", "factory Turbo PL1", watts, False),
    0x7A8: ("power", "PL_DEF_TURBO_PL2", "factory Turbo PL2", watts, False),
    0x7A9: ("power", "PL_DEF_TURBO_PL4", "factory Turbo PL4", watts, False),
    0x7AA: ("power", "PL_DEF_TURBO_DSTATE", "factory Turbo GPU DState", u8, False),
    0x783: ("power", "PL1", "applied PL1 (0 on battery = EC limits)", watts, True),
    0x784: ("power", "PL2", "applied PL2", watts, True),
    0x785: ("power", "PL4", "applied PL4", watts, True),
    0x786: ("power", "TCC_OFFSET", "bit7 enable, bits0..6 degrees below TjMax", flag7(" C below TjMax"), True),
    0x7D8: ("power", "TCC_DEF_GAMING", "default TCC, Gaming", u8, False),
    0x7D9: ("power", "TCC_DEF_OFFICE", "default TCC, Office", u8, False),
    0x7DA: ("power", "TCC_DEF_TURBO", "default TCC, Turbo", u8, False),
    # gpu
    0x743: ("gpu", "GPU_FEAT_CTRL", "bit0 Dynamic Boost function, bit1 DB enable, bit2 cTGP function",
            bits("DB function", "DB enabled", "cTGP function"), True),
    0x744: ("gpu", "GPU_CTGP_TARGET", "cTGP above base, W", watts, True),
    0x745: ("gpu", "GPU_DB_TPP_TARGET", "Dynamic Boost total processing power target, W", watts, True),
    0x746: ("gpu", "GPU_DB_MAX_TGP", "Dynamic Boost max TGP, W", watts, True),
    0x78B: ("gpu", "GPU_DSTATE", "GPU DState", u8, False),
    # fans
    0x464: ("fans", "CPU_FAN_RPM_H", "CPU fan rpm, high byte (rpm = 0x464<<8 | 0x465)", None, False),
    0x465: ("fans", "CPU_FAN_RPM_L", "CPU fan rpm, low byte", None, False),
    0x46B: ("fans", "GPU_FAN_RPM_L", "GPU fan rpm, low byte (rpm = 0x46C<<8 | 0x46B)", None, False),
    0x46C: ("fans", "GPU_FAN_RPM_H", "GPU fan rpm, high byte", None, False),
    0x75B: ("fans", "CPU_FAN_DUTY", "CPU fan duty x2 (0..200)", lambda v: f"{v // 2} %", False),
    0x75C: ("fans", "GPU_FAN_DUTY", "GPU fan duty x2", lambda v: f"{v // 2} %", False),
    0x787: ("fans", "FAN_SWITCH_SPEED", "bit7 enable, bits0..6 speed / 100 rpm",
            lambda v: f"on, {(v & 0x7F) * 100} rpm" if v & 0x80 else "off", True),
    0x7A5: ("fans", "FAN_SAFETY", "bit3 fan safety protection active, bit7 power status",
            bits(None, None, None, "safety active", None, None, None, "power status"), False),
    0x7C5: ("fans", "FAN_CTRL_7C5", "bit4 skip safety protection, bit7 separate CPU/GPU curves",
            bits(None, None, None, None, "skip safety", None, None, "separate curves"), True),
    0x7C6: ("fans", "FAN_CTRL_7C6", "bit2 RAM fan table active", bits(None, None, "RAM table active"), True),
    0xF5D: ("fans", "FT_HS_A", "fan table handshake A (write 0xFD, EC replaces when done)", lambda v: f"0x{v:02X}", False),
    0xF5E: ("fans", "FT_HS_B", "fan table handshake B (write 0xC9)", lambda v: f"0x{v:02X}", False),
    0xF5F: ("fans", "FT_HS_MODE", "table code to load (liquid: Office 7, Gaming 6, Turbo 5)", lambda v: f"0x{v:02X}", False),
    # switches
    0x74E: ("switches", "FN_LOCK", "bit4 Fn Lock", bits(*[None] * 4, "Fn Lock"), True),
    0x767: ("switches", "TRIGGER_767", "bit0 Win-lock trigger, bit1 light bar trigger, bit4 USB charging in sleep",
            bits("WinKey trigger", "LightBar trigger", None, None, "USB charging"), True),
    0x768: ("switches", "STATUS_768", "bit0 Win key locked, bit1 light bar on", bits("WinKey locked", "LightBar on"), False),
    0x7A6: ("switches", "TOUCHPAD", "bit3 touchpad LED, bits4..5 battery mode (00 full, 01 balanced, 10 stationary), "
            "bit6 touchpad toggle off",
            lambda v: f"LED={'on' if v & 8 else 'off'}, battery={['full', 'balanced', 'stationary', '?'][(v >> 4) & 3]}, "
                      f"toggle={'off' if v & 0x40 else 'on'}", True),
    # lighting
    0x73C: ("lighting", "KB_ID", "ITE keyboard sub-type", lambda v: f"0x{v:02X}", False),
    0x73D: ("lighting", "LED_VENDOR_2", "LED vendor (2)", lambda v: f"0x{v:02X}", False),
    0x766: ("lighting", "EC_CAPS_766", "bit2 RGB keyboard through the EC", bits(None, None, "EC RGB keyboard"), False),
    0x78C: ("lighting", "KB_SINGLE", "single-colour backlight: bit1 off, bit4 valid, bits5..7 level",
            lambda v: f"level {v >> 5}, {'off' if v & 2 else 'on'}, {'valid' if v & 0x10 else 'not valid'}", True),
    # liquid cooler
    0x7A4: ("cooler", "LC_SUPPORT", "bit7 liquid cooling supported", bits(*[None] * 7, "supported"), False),
    0x7C7: ("cooler", "LC_CONNECTED", "bit1 cooler attached (set by the service), bits2..4 OC power level (EC-owned)",
            lambda v: f"attached={'yes' if v & 2 else 'no'}, level {(v >> 2) & 7}", False),
    0x7C8: ("cooler", "LC_TABLE_SUPPORT", "bit5 EC publishes cooler targets / liquid fan table", bits(*[None] * 5, "LC table"), False),
    0x7E6: ("cooler", "LC_EC_FAN", "EC target: cooler fan %, bit7 valid", lc_target(" %"), False),
    0x7E7: ("cooler", "LC_EC_PUMP", "EC target: pump voltage, bit7 valid", lc_target(" V"), False),
    0x708: ("cooler", "HWOC_708", "liquid OC state 0x708", lambda v: f"0x{v:02X}", False),
    0x709: ("cooler", "HWOC_709", "liquid OC state 0x709", lambda v: f"0x{v:02X}", False),
    0x718: ("cooler", "HWOC_718", "liquid OC state 0x718", lambda v: f"0x{v:02X}", False),
}
GROUPS = sorted({g for g, *_ in REGS.values()})


# ---------------------------------------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------------------------------------
class Backend:
    name = "?"
    t_read = 0.0
    n_read = 0

    def read(self, addr):
        t = time.perf_counter()
        v = self._read(addr)
        self.t_read += time.perf_counter() - t
        self.n_read += 1
        return v

    def write(self, addr, val):
        raise NotImplementedError(f"{self.name}: write is not supported")

    def pwup(self, level):
        raise NotImplementedError(f"{self.name}: PWUP is only available through the OEM driver")


class DriverBackend(Backend):
    name = "driver"

    def __init__(self):
        if not IS_WIN:
            raise OSError("the OEM driver backend works on Windows only")
        import ctypes.wintypes as wt
        self.wt = wt
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32.CreateFileW.restype = wt.HANDLE
        self.k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE]
        self.k32.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, wt.LPVOID, wt.DWORD, wt.LPVOID, wt.DWORD,
                                             ctypes.POINTER(wt.DWORD), wt.LPVOID]
        self.h = self.k32.CreateFileW(r"\\.\ACPIDriver", 0xC0000000, 3, None, 3, 0, None)
        if not self.h or self.h in (-1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
            raise OSError(f"cannot open \\\\.\\ACPIDriver (error {ctypes.get_last_error()}); "
                          "is UWACPIDriver installed and the tool run as administrator?")

    def _io(self, code, inb):
        out, n = ctypes.create_string_buffer(4), self.wt.DWORD(0)
        if not self.k32.DeviceIoControl(self.h, code, inb, len(inb), out, 4, ctypes.byref(n), None):
            raise OSError(f"IOCTL 0x{code:08X} failed, error {ctypes.get_last_error()}")
        time.sleep(0.01)                                  # GCUService AcpiCtrl.DelayTime
        return out.raw

    def _read(self, addr):
        return int.from_bytes(self._io(0x9C40A488, struct.pack("<i", addr))[:4], "little") & 0xFF

    def write(self, addr, val):
        self._io(0x9C40A48C, struct.pack("<ii", addr, val & 0xFF))

    def pwup(self, level):
        self._io(0x9C40A504, b"PUWP" + struct.pack("<i", level))


class WmiBackend(Backend):
    name = "wmi"

    def __init__(self, instance="1_1"):
        if not IS_WIN:
            raise OSError("the WMI backend works on Windows only")
        try:
            import pythoncom
            import win32com.client
        except ImportError as e:
            raise OSError("pywin32 is missing: python -m pip install pywin32") from e
        pythoncom.CoInitialize()
        self.svc = win32com.client.GetObject(r"winmgmts:{impersonationLevel=impersonate}!\\.\root\WMI")
        try:
            insts = list(self.svc.ExecQuery("SELECT * FROM AcpiTest_MULong"))
        except Exception as e:  # noqa: BLE001
            raise OSError(f"AcpiTest_MULong is not accessible ({e}); run as administrator") from e
        if not insts:
            raise OSError("AcpiTest_MULong not found: this firmware has no WMI EC interface")
        inst = next((i for i in insts if i.InstanceName.endswith(instance)), insts[0])
        self.path = inst.Path_.Path
        self.meth = self.svc.Get("AcpiTest_MULong").Methods_("GetSetULong")

    def _call(self, data):
        p = self.meth.InParameters.SpawnInstance_()
        p.Data = str(data)                       # uint64 is passed as a string in SWbem
        return int(self.svc.ExecMethod(self.path, "GetSetULong", p).Return)

    def _read(self, addr):
        return self._call((1 << 40) | addr) & 0xFF

    def write(self, addr, val):
        self._call(((val & 0xFF) << 16) | addr)


class ServiceBackend(Backend):
    name = "service"

    def __init__(self, port=47321):
        import urllib.request
        self.ur = urllib.request
        self.port = port
        tf = (os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UWCC", "run", "token") if IS_WIN
              else "/run/uwcc/token")
        try:
            with open(os.environ.get("UWCC_TOKEN_FILE", tf)) as f:
                self.tok = os.environ.get("UWCC_TOKEN") or f.read().strip()
        except OSError as e:
            raise OSError(f"no access to the service token {tf} ({e})") from e

    def _read(self, addr):
        req = self.ur.Request(f"http://127.0.0.1:{self.port}/api/ec/{addr:x}", headers={"X-UWCC-Token": self.tok})
        return json.load(self.ur.urlopen(req, timeout=5))["value"]


def open_backend(name, cfg):
    if name == "auto":
        for n in ("driver", "wmi", "service"):
            try:
                return open_backend(n, cfg)
            except OSError:
                continue
        raise OSError("no backend available (driver, wmi, service)")
    if name == "driver":
        return DriverBackend()
    if name == "wmi":
        return WmiBackend(cfg.get("wmi_instance", "1_1"))
    if name == "service":
        return ServiceBackend(cfg.get("service_port", 47321))
    raise OSError(f"unknown backend {name}")


# ---------------------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------------------
def parse_addrs(items):
    out = []
    for it in items:
        if "-" in it:
            a, b = (int(x, 16) for x in it.split("-"))
            out += list(range(a, b + 1))
        else:
            out.append(int(it, 16))
    return out


def describe(addr, v):
    if addr not in REGS:
        return "", ""
    _, name, desc, dec, _ = REGS[addr]
    return name, (dec(v) if dec else "")


def emit(rows, args, header):
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    widths = [max(len(str(h)), *(len(str(r.get(h, ""))) for r in rows)) for h in header] if rows else [len(h) for h in header]
    print("  ".join(h.ljust(w) for h, w in zip(header, widths)))
    for r in rows:
        print("  ".join(str(r.get(h, "")).ljust(w) for h, w in zip(header, widths)))


def writable(addr, cfg):
    extra = {int(x, 16) for x in cfg.get("writable_extra", [])}
    deny = {int(x, 16) for x in cfg.get("writable_deny", [])}
    return (REGS.get(addr, (None,) * 5)[4] or addr in extra) and addr not in deny


# ---------------------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------------------
def cmd_read(ec, args, cfg):
    rows = []
    for a in parse_addrs(args.items):
        v = ec.read(a)
        name, dec = describe(a, v)
        rows.append({"addr": f"0x{a:03X}", "hex": f"0x{v:02X}", "dec": v, "bin": f"{v:08b}", "name": name, "decoded": dec})
    emit(rows, args, ["addr", "hex", "dec", "bin", "name", "decoded"])


def cmd_dump(ec, args, cfg):
    start = int(args.items[0], 16)
    n = int(args.items[1], 0) if len(args.items) > 1 else 256
    for row in range(start, start + n, 16):
        vals = [ec.read(row + i) for i in range(min(16, start + n - row))]
        print(f"{row:04X}: " + " ".join(f"{v:02X}" for v in vals))


def cmd_decode(ec, args, cfg):
    groups = [g.lower() for g in args.items] or GROUPS
    rows = []
    for a in sorted(REGS):
        g, name, desc, dec, _ = REGS[a]
        if g not in groups:
            continue
        v = ec.read(a)
        rows.append({"group": g, "addr": f"0x{a:03X}", "hex": f"0x{v:02X}", "name": name,
                     "decoded": dec(v) if dec else str(v), "description": desc})
    # combined values
    if "fans" in groups:
        rpm_c = (ec.read(0x464) << 8) | ec.read(0x465)
        rpm_g = (ec.read(0x46C) << 8) | ec.read(0x46B)
        rows.append({"group": "fans", "addr": "calc", "name": "FAN_RPM", "decoded": f"CPU {rpm_c} rpm, GPU {rpm_g} rpm"})
    if "battery" in groups:
        mv = (ec.read(0x409) << 8) | ec.read(0x408)
        cyc = (ec.read(0x4A7) << 8) | ec.read(0x4A6)
        rows.append({"group": "battery", "addr": "calc", "name": "BATTERY", "decoded": f"design {mv} mV, {cyc} cycles"})
    emit(rows, args, ["group", "addr", "hex", "name", "decoded", "description"])


def cmd_fantable(ec, args, cfg):
    t = {base: [ec.read(base + i) for i in range(16)] for base in (0xF00, 0xF10, 0xF20, 0xF30, 0xF40, 0xF50)}
    rows = []
    for kind, up, down, duty in (("CPU", 0xF00, 0xF10, 0xF20), ("GPU", 0xF30, 0xF40, 0xF50)):
        for lvl in range(16):
            u = 0 if lvl == 0 else t[up][lvl - 1]
            d = t[down][lvl + 1] if lvl < 15 else 0xFF
            p = t[duty][lvl]
            if lvl > 0 and (u in (0, 0xFF) or p > 200):
                break
            rows.append({"fan": kind, "level": lvl, "on_C": u, "off_C": d if d != 0xFF else "-",
                         "duty": f"{p // 2} %" if p <= 200 else "-"})
    emit(rows, args, ["fan", "level", "on_C", "off_C", "duty"])
    print(f"\nRAM table active (0x7C6 bit2): {bool(ec.read(0x7C6) & 4)}, separate curves (0x7C5 bit7): "
          f"{bool(ec.read(0x7C5) & 0x80)}, handshake 0xF5D/E/F: "
          + " ".join(f"0x{ec.read(a):02X}" for a in (0xF5D, 0xF5E, 0xF5F)))


def cmd_watch(ec, args, cfg):
    addrs = parse_addrs(args.items or [f"0x{a:03X}" for a in (0x464, 0x465, 0x75B, 0x75C, 0x751)])
    f = open(args.csv, "w", newline="") if args.csv else None
    w = csv.writer(f) if f else None
    if w:
        w.writerow(["time"] + [f"0x{a:03X}" for a in addrs])
    print("time      " + " ".join(f"{a:03X}" .rjust(5) for a in addrs))
    n = 0
    try:
        while not args.count or n < args.count:
            vals = [ec.read(a) for a in addrs]
            ts = time.strftime("%H:%M:%S")
            print(f"{ts}  " + " ".join(f"{v:5d}" for v in vals), flush=True)
            if w:
                w.writerow([ts] + vals)
            n += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if f:
            f.close()


def do_write(ec, args, cfg, addr, new):
    if not writable(addr, cfg) and not args.force:
        sys.exit(f"0x{addr:03X} is not in the writable list (see ec_tool.json 'writable_extra'); use --force at your own risk")
    old = ec.read(addr)
    ec.write(addr, new)
    time.sleep(0.2)
    now = ec.read(addr)
    name, _ = describe(addr, new)
    print(f"0x{addr:03X} {name}: 0x{old:02X} -> wrote 0x{new:02X}, read back 0x{now:02X} "
          f"({'OK' if now == new else 'DIFFERENT - the EC changed it'})")
    if args.restore:
        print(f"restoring in {args.restore} s...")
        time.sleep(args.restore)
        ec.write(addr, old)
        time.sleep(0.2)
        print(f"0x{addr:03X} restored: 0x{ec.read(addr):02X}")


def cmd_write(ec, args, cfg):
    if len(args.items) != 2:
        sys.exit("usage: write ADDR VALUE")
    do_write(ec, args, cfg, int(args.items[0], 16), int(args.items[1], 0) & 0xFF)


def cmd_bit(ec, args, cfg):
    if len(args.items) != 3 or args.items[2] not in ("on", "off"):
        sys.exit("usage: bit ADDR BIT on|off")
    addr, b = int(args.items[0], 16), int(args.items[1])
    v = ec.read(addr)
    do_write(ec, args, cfg, addr, (v | (1 << b)) if args.items[2] == "on" else (v & ~(1 << b) & 0xFF))


def cmd_compare(ec, args, cfg):
    other = open_backend(args.with_backend, cfg)
    addrs = parse_addrs(args.items) if args.items else sorted(REGS)
    rows, same = [], 0
    for a in addrs:
        v1, v2 = ec.read(a), other.read(a)
        same += v1 == v2
        rows.append({"addr": f"0x{a:03X}", ec.name: f"0x{v1:02X}", other.name: f"0x{v2:02X}",
                     "result": "same" if v1 == v2 else "DIFFERENT", "name": describe(a, v1)[0]})
    emit(rows, args, ["addr", ec.name, other.name, "result", "name"])
    print(f"\n{same}/{len(addrs)} equal; {ec.name} {ec.t_read / max(ec.n_read, 1) * 1000:.0f} ms/read, "
          f"{other.name} {other.t_read / max(other.n_read, 1) * 1000:.0f} ms/read")


def cmd_bench(ec, args, cfg):
    n = int(args.items[0]) if args.items else 50
    t = time.perf_counter()
    for _ in range(n):
        ec.read(0x740)
    dt = (time.perf_counter() - t) / n * 1000
    print(f"{ec.name}: {n} reads, {dt:.1f} ms per read; a 14-register poll takes ~{dt * 14:.0f} ms, "
          f"a full fan table write (96 bytes) ~{dt * 96 * 1.2 / 1000:.1f} s")


def cmd_info(ec, args, cfg):
    r = ec.read
    pid, mode, cap = r(0x740), r(0x751), r(0x78E)
    lc = r(0x7C7)
    print(f"Backend          : {ec.name}")
    print(f"Project ID       : 0x{pid:02X}" + ("  (MAIBENBEN Tsunami X629)" if pid == 0x10 else ""))
    print(f"Capabilities     : {bits(None, None, None, None, 'RGB lightbar', None, 'RamFan1.5', 'LED vendor')(cap)}; "
          f"Turbo {'yes' if r(0x49F) & 2 else 'no'}; Type-C priority {'yes' if r(0x742) & 0x20 else 'no'}; "
          f"liquid cooling {'yes' if r(0x7A4) & 0x80 else 'no'}")
    print(f"Mode             : {fan_mode(mode)}  (0x751=0x{mode:02X}), Custom flag {'yes' if r(0x726) & 0x80 else 'no'}")
    print(f"Power            : PL1/PL2/PL4 {r(0x783)}/{r(0x784)}/{r(0x785)} W, TCC {flag7(' C')(r(0x786))}")
    print(f"Factory PL       : Gaming {r(0x730)}/{r(0x731)}/{r(0x732)}, Office {r(0x734)}/{r(0x735)}/{r(0x736)}, "
          f"Turbo {r(0x7A7)}/{r(0x7A8)}/{r(0x7A9)} W")
    print(f"GPU              : {REGS[0x743][3](r(0x743))}; cTGP +{r(0x744)} W, DB TPP {r(0x745)} W, DB max {r(0x746)} W")
    print(f"Fans             : CPU {(r(0x464) << 8) | r(0x465)} rpm ({r(0x75B) // 2} %), "
          f"GPU {(r(0x46C) << 8) | r(0x46B)} rpm ({r(0x75C) // 2} %), RAM table {'on' if r(0x7C6) & 4 else 'off'}")
    print(f"Battery          : limits {r(0x7D0)}-{r(0x7B9) & 0x7F or 100} %, {REGS[0x7A6][3](r(0x7A6))}, "
          f"{(r(0x4A7) << 8) | r(0x4A6)} cycles")
    print(f"Keyboard         : Fn Lock {'on' if r(0x74E) & 0x10 else 'off'}, Win key {'locked' if r(0x768) & 1 else 'free'}")
    print(f"Liquid cooler    : attached {'yes' if lc & 2 else 'no'}, EC level {(lc >> 2) & 7}, "
          f"EC targets fan {lc_target(' %')(r(0x7E6))}, pump {lc_target(' V')(r(0x7E7))}")


def cmd_groups(ec, args, cfg):
    for g in GROUPS:
        regs = [f"0x{a:03X}" for a, x in sorted(REGS.items()) if x[0] == g]
        print(f"{g:9} {' '.join(regs)}")


def cmd_pwup(ec, args, cfg):
    if not args.items:
        sys.exit("usage: pwup LEVEL (0..5)")
    lvl = int(args.items[0])
    if not 0 <= lvl <= 5:
        sys.exit("level 0..5")
    ec.pwup(lvl)
    print(f"PWUP({lvl}) passed to the firmware; EC level is {(ec.read(0x7C7) >> 2) & 7}. "
          "The service passes the EC level again on its next event - restart it to undo.")


COMMANDS = {"read": cmd_read, "dump": cmd_dump, "decode": cmd_decode, "fantable": cmd_fantable, "watch": cmd_watch,
            "write": cmd_write, "bit": cmd_bit, "compare": cmd_compare, "bench": cmd_bench, "info": cmd_info,
            "groups": cmd_groups, "pwup": cmd_pwup}
NO_EC = {"groups"}


def main():
    ap = argparse.ArgumentParser(description="EC register tool for Uniwill laptops (MAIBENBEN Tsunami X629)",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("items", nargs="*")
    ap.add_argument("--config", default=os.path.join(HERE, "ec_tool.json"))
    ap.add_argument("--backend")
    ap.add_argument("--with", dest="with_backend")
    ap.add_argument("--interval", type=float)
    ap.add_argument("--count", type=int)
    ap.add_argument("--csv")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--restore", type=float)
    args = ap.parse_args()
    cfg = {}
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    args.backend = args.backend or cfg.get("backend", "auto")
    args.with_backend = args.with_backend or cfg.get("compare_with", "driver")
    args.interval = args.interval if args.interval is not None else cfg.get("interval", 2.0)
    args.count = args.count if args.count is not None else cfg.get("count", 0)
    if args.command == "watch" and not args.items:
        args.items = cfg.get("watch", [])
    for a, n in cfg.get("names", {}).items():              # user labels for unknown registers
        addr = int(a, 16)
        if addr not in REGS:
            REGS[addr] = ("user", n, n, None, False)
    if IS_WIN and args.command not in NO_EC and args.backend != "service":
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                sys.exit("Run as administrator (PowerShell -> Run as administrator).")
        except AttributeError:
            pass
    try:
        ec = None if args.command in NO_EC else open_backend(args.backend, cfg)
        COMMANDS[args.command](ec, args, cfg)
    except (OSError, NotImplementedError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
