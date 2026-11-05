"""Control Center 3.0 / Clevo fan curves as a file: export and import, separate from the Uniwill fan tables.

A Clevo curve has 3 points per fan (the first is the factory one, then the firmware rises to 100 % at 100 °C); a
Uniwill table has up to 16 points and other limits. The two formats do not mix: this file has its own "format" name,
and the Uniwill import (backup.py) and this one each refuse the other.

    {"format": "open-uniwill-cc-clevo-fan-curve", "version": 1, "program": "...", "laptop": "...",
     "fans": ["cpu", "gpu1"], "curves": {"cpu": [[t, %], [t, %], [t, %]], ...}, "factory": {...}}
"""
import time

from .manager import FANS, check_curve

FORMAT = "open-uniwill-cc-clevo-fan-curve"
VERSION = 1


def export(clevo, laptop="", program=""):
    """The custom curve in use (or the factory one) of every fan this laptop has."""
    factory = {k: [list(p) for p in v[:3]] for k, v in ((clevo.table or {}).get("curves") or {}).items()}
    own = (clevo.state().get("curve") or {})
    curves = {k: [list(p) for p in (own.get(k) or factory[k])[:3]] for k in factory}
    return {"format": FORMAT, "version": VERSION, "program": program, "laptop": laptop,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "fans": sorted(curves, key=FANS.index),
            "curves": curves, "factory": factory}


def load(data, clevo):
    """A file from export() -> {fan: 3 points}, checked for this laptop; nothing is sent to the firmware.
    The first point stays the factory one of this laptop; fans it does not have are left out."""
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    fmt = data.get("format")
    if fmt != FORMAT:
        if fmt == "open-uniwill-cc" or "tables" in data or "profiles" in data:
            raise ValueError("this is a Uniwill fan table, not a Clevo curve")
        raise ValueError(f"unknown format {fmt!r}")
    if int(data.get("version", 0)) > VERSION:
        raise ValueError(f"version {data.get('version')} is newer than this program")
    factory = (clevo.table or {}).get("curves") or {}
    out = {}
    for fan, pts in (data.get("curves") or {}).items():
        if fan not in FANS:
            raise ValueError(f"fan {fan}")
        if fan not in factory:
            continue
        pts = check_curve(pts)
        pts[0] = list(factory[fan][0])
        out[fan] = check_curve(pts)
    if not out:
        raise ValueError("no curve for the fans of this laptop")
    return out
