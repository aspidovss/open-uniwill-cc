"""Colour calibration of a lighting device (1.8.2.5).

The LEDs of a keyboard or a light bar do not always show the colour that is sent: channels can be wired in another
order (the front bar of XMG NEO 16 E25 shows some colours swapped — in every program, the OEM one too), one colour
can bleed into another, and white can be tinted. BetterRGB's own calibration only measures white (three gains);
this one also measures the three primaries:

    the device shows pure red, green and blue (and, optionally, white) as they are sent ("raw"), and the user picks
    the colour seen for each -> in linear light these are the columns of the 3 x 3 matrix M that the device applies
    (sent -> seen). Its inverse C = M^-1 turns the wanted colour into the one to send. With white, the columns of
    M are first scaled so that M * (1,1,1) has the hue of the white seen. C is scaled so that white stays as bright
    as possible; negative results are cut to 0.

A swap of channels gives a permutation matrix (C swaps them back), bleeding gives off-diagonal terms (subtracted),
a tint gives unequal column lengths (the strong channels are lowered). White alone gives the BetterRGB gains.

The correction sits before the device's own colour correction (WKDColor), so what is measured is what the user
sees through the whole path. The accuracy is that of the colours picked by eye.
"""
from ..lighting.fx import l2s, s2l

PRIMARIES = {"r": (255, 0, 0), "g": (0, 255, 0), "b": (0, 0, 255), "w": (255, 255, 255)}
_LIN = [s2l(i) for i in range(256)]


def _inv(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-6:
        raise ValueError("two of the colours are the same — pick the colour you see for each one")
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def _mul(m, v):
    return [m[k][0] * v[0] + m[k][1] * v[1] + m[k][2] * v[2] for k in range(3)]


def _lin(c):
    return [_LIN[max(0, min(255, int(x)))] for x in c[:3]]


def matrix(observed):
    """{"r": [r,g,b], "g": [...], "b": [...], "w": [...]} (any of them, sRGB 0..255) -> the correction C (3 x 3,
    linear light). Missing primaries count as shown correctly."""
    obs = {k: v for k, v in (observed or {}).items() if k in PRIMARIES and v}
    if not obs:
        raise ValueError("no colours to calibrate with")
    cols = [_lin(obs[k]) if k in obs else _lin(PRIMARIES[k]) for k in ("r", "g", "b")]
    for k, col in zip("rgb", cols):
        if max(col) < 0.01:
            raise ValueError(f"the colour picked for {'red green blue'.split()['rgb'.index(k)]} is too dark")
    m = [[cols[j][i] for j in range(3)] for i in range(3)]          # columns = what each channel looks like
    if "w" in obs:
        w = _lin(obs["w"])
        if max(w) < 0.01:
            raise ValueError("the colour picked for white is too dark")
        s = _mul(_inv(m), w)
        if min(s) <= 0:
            raise ValueError("the white does not match the three colours — check the picks or calibrate again")
        m = [[m[i][j] * s[j] for j in range(3)] for i in range(3)]
    c = _inv(m)
    u = _mul(c, (1.0, 1.0, 1.0))
    if min(u) <= 0:
        raise ValueError("these colours cannot be corrected (white would need a negative channel) — "
                         "check the picks or calibrate again")
    k = 1.0 / max(u)
    return [[round(x * k, 5) + 0.0 for x in row] for row in c]


def is_identity(m):
    return all(abs(m[i][j] - (1.0 if i == j else 0.0)) < 1e-4 for i in range(3) for j in range(3))


class Calibration:
    """C applied to sRGB bytes (0..255)."""

    def __init__(self, m):
        self.m = [list(map(float, row)) for row in m]
        self.identity = is_identity(self.m)
        self._cache = {}

    def apply(self, r, g, b):
        if self.identity:
            return (r, g, b)
        key = (r, g, b)
        hit = self._cache.get(key)
        if hit is None:
            v = _mul(self.m, _lin((r, g, b)))
            hit = tuple(l2s(max(0.0, min(1.0, x))) for x in v)
            if len(self._cache) > 4096:
                self._cache.clear()
            self._cache[key] = hit
        return hit


def from_store(entry):
    """the stored {"matrix": ...} -> Calibration, or None"""
    try:
        return Calibration(entry["matrix"]) if entry and entry.get("matrix") else None
    except (KeyError, TypeError, ValueError):
        return None
