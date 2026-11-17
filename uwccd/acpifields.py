"""Named EC fields from the laptop's own DSDT (1.8.1.1).

Some boards keep a flag in a different EC bit than the official service assumes. The firmware itself names its EC
bits in the DSDT (Field (ECMG, ...) { Offset (0x727), , 6, CUME, 1, ... }), so instead of guessing per project the
service reads the DSDT once and looks the name up. Only Field() declarations are parsed (names, byte and bit
offsets) — no AML is executed.

    ec_field("CUME") -> (0x727, 6, 1) on MECHREVO Yaoshi / Aurora X / XMG NEO 16 E25 (project 0x1A), None elsewhere
"""
import functools
import glob
import logging
import os
import struct
import sys

log = logging.getLogger("uwccd.acpi")


def _read_dsdt():
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        prov, tid = 0x41435049, int.from_bytes(b"DSDT", "little")       # 'ACPI', 'DSDT'
        n = k32.GetSystemFirmwareTable(prov, tid, None, 0)
        if not n:
            return None
        buf = (ctypes.c_ubyte * n)()
        k32.GetSystemFirmwareTable(prov, tid, buf, n)
        return bytes(buf)
    for p in ("/sys/firmware/acpi/tables/DSDT",) + tuple(sorted(glob.glob("/sys/firmware/acpi/tables/DSDT*"))):
        try:
            with open(p, "rb") as f:
                return f.read()
        except OSError:
            continue
    return None


def _pkglen(b, i):
    b0 = b[i]
    n = b0 >> 6
    if n == 0:
        return b0 & 0x3F, i + 1
    v = b0 & 0x0F
    for k in range(n):
        v |= b[i + 1 + k] << (4 + 8 * k)
    return v, i + 1 + n


def _namestring(b, i):
    s = ""
    while b[i] in (0x5C, 0x5E):
        s += chr(b[i])
        i += 1
    if b[i] == 0x2E:
        return s + b[i + 1:i + 5].decode("latin1") + "." + b[i + 5:i + 9].decode("latin1"), i + 9
    if b[i] == 0x2F:
        n = b[i + 1]
        return s + ".".join(b[i + 2 + 4 * k:i + 6 + 4 * k].decode("latin1") for k in range(n)), i + 2 + 4 * n
    if b[i] == 0x00:
        return s, i + 1
    return s + b[i:i + 4].decode("latin1"), i + 4


def parse_fields(table):
    """{(region, name): (byte, bit, length)} of every named field declared with Field() in an AML table."""
    data = table[36:]
    out = {}
    i = 0
    while True:
        i = data.find(b"\x5b\x81", i)                     # FieldOp
        if i < 0:
            return out
        try:
            plen, j = _pkglen(data, i + 2)
            end = i + 2 + plen
            region, j = _namestring(data, j)
            j += 1                                         # field flags
            bit = 0
            while j < end:
                c = data[j]
                if c == 0x00:                              # ReservedField
                    n, j = _pkglen(data, j + 1)
                    bit += n
                elif c == 0x01:                            # AccessField
                    j += 3
                elif c == 0x03:                            # ExtendedAccessField
                    j += 4
                elif c == 0x02:                            # ConnectField: stop at this field list
                    break
                else:
                    name = data[j:j + 4].decode("latin1")
                    n, j = _pkglen(data, j + 4)
                    out[(region.split(".")[-1], name)] = (bit // 8, bit % 8, n)
                    bit += n
        except (IndexError, struct.error, UnicodeDecodeError):
            pass
        i += 2


@functools.lru_cache(maxsize=1)
def _ec_fields():
    try:
        t = _read_dsdt()
    except Exception as e:  # noqa: BLE001
        log.info("DSDT not readable: %s", e)
        return {}
    if not t:
        return {}
    f = {name: v for (region, name), v in parse_fields(t).items() if region == "ECMG"}
    log.info("DSDT: %d named EC fields (ECMG)", len(f))
    return f


def ec_field(name):
    """(byte, bit, length) of a named field of the EC RAM region ECMG, or None (not in this DSDT / not readable)."""
    return _ec_fields().get(name)


if __name__ == "__main__":                                 # python3 -m uwccd.acpifields DSDT.aml [NAME ...]
    path = sys.argv[1] if len(sys.argv) > 1 else None
    tbl = open(path, "rb").read() if path and os.path.isfile(path) else _read_dsdt()
    fl = parse_fields(tbl or b"")
    for (reg, nm), (by, bi, ln) in sorted(fl.items(), key=lambda x: (x[0][0], x[1])):
        if len(sys.argv) <= 2 or nm in sys.argv[2:]:
            print(f"{reg:6} 0x{by:03X} bit {bi} len {ln:3} {nm}")
