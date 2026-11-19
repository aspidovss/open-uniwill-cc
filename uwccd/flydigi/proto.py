"""Flydigi BS protocol: frames, commands, decoders.

Port of THRM internal/deviceproto/protocol.go and commands.go (MIT, Copyright (c) 2025 Tianli,
https://github.com/TIANLI0/THRM). Names follow THRM's (snake_case).

Frame: 5A A5 <cmd> <len = 2 + len(payload)> <payload…> <checksum = (cmd + len + sum(payload)) & 0xFF>.
HID report (BS2 and later): Report ID 0x02 + frame, padded to the report length (25).
"""
import struct

MAGIC0, MAGIC1, REPORT_ID = 0x5A, 0xA5, 0x02

# commands.go
CMD_QUERY_FIRMWARE_VERSION = 0x01
CMD_QUERY_CONFIG_STATE = 0x02
CMD_INITIALIZE_CONTROLLER = 0x03
CMD_QUERY_DEVICE_ID = 0x04
CMD_CLEAR_INITIALIZATION_LATCH = 0x05
CMD_FACTORY_REINITIALIZE = 0x06
CMD_QUERY_CONTROLLER_CAPABILITY = 0x07
CMD_SET_FIXED_GEAR = 0x08
CMD_QUERY_RUNTIME_PROFILE = 0x09
CMD_SET_RUNTIME_PROFILE = 0x0A
CMD_QUERY_IDENTITY_BLOCK = 0x0B
CMD_SET_POWER_ON_START = 0x0C
CMD_SET_SMART_START_STOP = 0x0D
CMD_SET_REALTIME_RPM = 0x21
CMD_QUERY_RPM_STATE = 0x22
CMD_ENTER_REALTIME_RPM = 0x23
CMD_EXIT_REALTIME_RPM = 0x24
CMD_QUERY_WORK_MODE = 0x25
CMD_SET_GEAR_RPM = 0x26
CMD_QUERY_GEAR_RPM_TABLE = 0x27
CMD_RGB_STATUS = 0x45
CMD_RGB_ENABLE = 0x46
CMD_RGB_FRAME_WRITE = 0x47
CMD_GEAR_LIGHT = 0x48
CMD_STATUS_NOTIFY = 0xEF

# protocol.go: 0x47 writes 10 bytes at index*10 into a 256-byte buffer without a bounds check -> 25 frames
RGB_FRAME_BUFFER_SIZE, RGB_FRAME_WRITE_SIZE = 256, 10
RGB_FRAME_COUNT = RGB_FRAME_BUFFER_SIZE // RGB_FRAME_WRITE_SIZE

# types.go
MANUAL_GEAR_MIN_RPM, MANUAL_GEAR_MAX_RPM = 800, 5000
REALTIME_RPM_MAX = 5000
GEARS = ("quiet", "standard", "performance", "extreme")          # 1..4 (静音 / 标准 / 强劲 / 超频)
LEVELS = ("low", "mid", "high")                                  # 低 / 中 / 高
# DefaultManualGearRPM: the app's 12 virtual presets on the firmware's 4 slots (types.go)
DEFAULT_MANUAL_GEAR_RPM = {"quiet": {"low": 1300, "mid": 1700, "high": 1900},
                           "standard": {"low": 2100, "mid": 2400, "high": 2700},
                           "performance": {"low": 2800, "mid": 3000, "high": 3300},
                           "extreme": {"low": 3500, "mid": 3700, "high": 4000}}
BS1_GEAR_RPM = {1: 1300, 2: 2100, 3: 2800, 4: 3500}              # BS1GearCommands
# GetDefaultFanCurve (types.go): (°C, RPM)
DEFAULT_FAN_CURVE = [(30, 1000), (35, 1200), (40, 1400), (45, 1600), (50, 1800), (55, 2000), (60, 2300), (65, 2600),
                     (70, 2900), (75, 3200), (80, 3500), (85, 3800), (90, 4000), (95, 4000), (100, 4000),
                     (105, 4000), (110, 4000)]


def checksum(cmd, payload=b""):
    return (cmd + 2 + len(payload) + sum(payload)) & 0xFF


def build_frame(cmd, *payload):
    p = bytes(payload)
    return bytes((MAGIC0, MAGIC1, cmd, 2 + len(p))) + p + bytes((checksum(cmd, p),))


def build_report(frame, report_len):
    """BuildReport: Report ID 0x02 + frame, zero padded to report_len."""
    if report_len <= 0 or report_len < len(frame) + 1:
        report_len = len(frame) + 1
    return (bytes((REPORT_ID,)) + bytes(frame)).ljust(report_len, b"\0")


class Frame:
    __slots__ = ("report_id", "offset", "command", "length", "payload", "checksum", "checksum_ok", "frame")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return f"Frame(0x{self.command:02X} {hexs(self.payload)} ok={self.checksum_ok})"


def parse_frame(data):
    """ParseFrame: the frame at offset 0 (5A A5 …) or 1 (<report id> 5A A5 …); None when there is none."""
    data = bytes(data)
    if len(data) >= 2 and data[0] == MAGIC0 and data[1] == MAGIC1:
        offset, rid = 0, 0
    elif len(data) >= 3 and data[1] == MAGIC0 and data[2] == MAGIC1:
        offset, rid = 1, data[0]
    else:
        return None
    if len(data) < offset + 5:
        return None
    length = data[offset + 3]
    if length < 2:
        return None
    frame_len = 2 + length + 1
    if len(data) < offset + frame_len:
        return None
    ci = offset + 2 + length
    s = sum(data[offset + 2:ci]) & 0xFF
    return Frame(report_id=rid, offset=offset, command=data[offset + 2], length=length,
                 payload=data[offset + 4:offset + 4 + length - 2], checksum=data[ci], checksum_ok=s == data[ci],
                 frame=data[offset:offset + frame_len])


def validate_outbound_frame(frame):
    """ValidateOutboundFrame: refuse the frames that make the firmware write out of bounds."""
    f = parse_frame(frame)
    if f is None:
        return
    if f.command == CMD_RGB_FRAME_WRITE:
        if not f.payload:
            raise ValueError("command 0x47 needs a frame index")
        if f.payload[0] >= RGB_FRAME_COUNT:
            raise ValueError(f"command 0x47: frame index {f.payload[0]} is past the firmware buffer "
                             f"(0..{RGB_FRAME_COUNT - 1}); the firmware does not check it")
    elif f.command == CMD_SET_GEAR_RPM:
        if f.payload and f.payload[0] > 3:
            raise ValueError(f"command 0x26: gear index {f.payload[0]} is outside 0..3")
    elif f.command == CMD_SET_FIXED_GEAR:
        if not f.payload:
            raise ValueError("command 0x08 needs a gear number")
        if not 1 <= f.payload[0] <= 4:
            raise ValueError(f"command 0x08: gear {f.payload[0]} is outside 1..4; the firmware does not check it")


def hexs(b):
    return " ".join(f"{x:02X}" for x in bytes(b or b""))


# -- decoders (commands.go) ---------------------------------------------------------------------------------------
def mode_name(mode):
    """ModeName: the 0xEF bit field (bit 0 = realtime)."""
    return "realtime" if mode & 0x01 else "gear"


def work_state_name(state):
    """WorkStateName: the 0x25 enum -> (name, realtime)."""
    if state in (1, 2, 3):
        return f"fixed gear {state}", False
    if state == 4:
        return "fixed gear 4 / initialized fallback", False
    if state == 5:
        return "realtime", True
    return f"unknown work state (0x{state:02X})", False


def decode_smart_start_stop(mode):
    """DecodeSmartStartStop: bits 0x0E of the 0xEF mode byte."""
    return {0x02: "off", 0x04: "immediate", 0x08: "delayed"}.get(mode & 0x0E, "")


def decode_gear_setting(value):
    """DecodeGearSetting -> (max gear, selected gear) names."""
    hi, lo = (value >> 4) & 0x0F, value & 0x0F
    mx = {0x2: "standard", 0x4: "performance", 0x6: "extreme"}.get(hi, f"unknown(0x{hi:X})")
    sel = {0x8: "quiet", 0xA: "standard", 0xC: "performance", 0xE: "extreme"}.get(lo, f"unknown(0x{lo:X})")
    return mx, sel


def decode_selected_gear(value):
    """DecodeSelectedGear: the low nibble of the 0xEF gear byte -> 1..4, 0 unknown."""
    return {0x8: 1, 0xA: 2, 0xC: 3, 0xE: 4}.get(value & 0x0F, 0)


def gear_code_name(gear):
    return GEARS[gear - 1] if 1 <= gear <= 4 else ""


ACK_NAMES = {(CMD_INITIALIZE_CONTROLLER, 5): "already initialized",
             (CMD_SET_REALTIME_RPM, 2): "realtime mode is not active",
             (CMD_ENTER_REALTIME_RPM, 3): "already in realtime mode",
             (CMD_EXIT_REALTIME_RPM, 2): "already outside realtime mode",
             (CMD_SET_GEAR_RPM, 0): "invalid gear index"}


def ack_status_name(command, status):
    if status == 1:
        return "success"
    n = ACK_NAMES.get((command, status))
    if n:
        return n
    return "busy or unavailable" if status == 5 else "invalid or rejected"


def decode_status(payload):
    """The 0xEF status notification (THRM parseFanData / DecodeFrame CmdStatusNotify); None if too short."""
    if len(payload) < 7:
        return None
    gear, mode = payload[0], payload[1]
    cur, tgt = struct.unpack_from("<HH", payload, 3)
    mx, sel = decode_gear_setting(gear)
    return {"gear_byte": gear, "mode_byte": mode, "max_gear": mx, "selected": sel,
            "selected_gear": decode_selected_gear(gear), "realtime": bool(mode & 1),
            "smart_start_stop": decode_smart_start_stop(mode), "current_rpm": cur, "target_rpm": tgt}


def decode_frame(f):
    """DecodeFrame for the responses this service reads; {} for the others."""
    p = f.payload
    c = f.command
    if c == CMD_QUERY_FIRMWARE_VERSION and len(p) >= 4:
        d = {"firmware": "%d.%d.%d.%d" % tuple(p[:4])}
        if len(p) >= 5 and p[4]:
            d["thrm_firmware"] = p[4]                    # THRM custom firmware appends its own version
        return d
    if c == CMD_QUERY_CONFIG_STATE and p:
        return {"config_state": {1: "not initialized", 2: "initialized"}.get(p[0], "unknown")}
    if c == CMD_QUERY_DEVICE_ID and len(p) >= 6:
        return {"device_id": ":".join(f"{x:02X}" for x in p[:6])}
    if c == CMD_QUERY_CONTROLLER_CAPABILITY and p:
        return {"capability_tier": p[0]}
    if c == CMD_QUERY_RPM_STATE and len(p) >= 4:
        m, t = struct.unpack_from("<HH", p, 0)
        return {"measured_rpm": m, "target_rpm": t}
    if c == CMD_QUERY_GEAR_RPM_TABLE and len(p) >= 8:
        return {"gear_table": [struct.unpack_from("<H", p, i * 2)[0] for i in range(4)]}
    if c == CMD_QUERY_WORK_MODE and p:
        name, rt = work_state_name(p[0])
        return {"work_state": name, "work_state_realtime": rt}
    if c == CMD_RGB_STATUS and p:
        return {"rgb": "on" if p[0] else "off"}
    if c == CMD_STATUS_NOTIFY:
        return decode_status(p) or {}
    return {}


# -- gear helpers (query.go / types.go) -----------------------------------------------------------------------------
def max_gear_for_fixed_gear_command(tier):
    """MaxGearForFixedGearCommand: tier 1 refuses gear 4 on 0x08 (still ACKs it)."""
    return 3 if tier == 1 else 4


def max_gear_for_gear_rpm_command(tier):
    """MaxGearForGearRPMCommand: 0x26 selects only gears 1..2 on tier 1, 1..3 on tier 2."""
    return {1: 2, 2: 3}.get(tier, 4)


def fixed_gear_for_wake(status):
    """fixedGearForWake: the gear the 0xEF status reports, 1 when unknown."""
    g = (status or {}).get("selected_gear") or 0
    return g if 1 <= g <= 4 else 1
