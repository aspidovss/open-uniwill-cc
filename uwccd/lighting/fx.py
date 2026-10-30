"""BetterRGB effects: frames drawn by the service for ITE keyboards.

Rewritten in Python from BetterRGB ITE8291 Adaptive 3.7.0 (MIT; Copyright (c) 2026 TheYamo, Copyright (c) 2026
ZavierChen and BetterRGB Adaptive contributors — the MIT notice is in THIRD_PARTY_LICENSES.txt, see NOTICE.md). The effects, the
transitions, the white calibration, the top-row bar and the frame pacing follow the original; the key geometry is the
6 x 21 grid of Uniwill ITE keyboards (the original is laid out for a Tongfang ITE 048D:600B keyboard).

A frame is a list of 126 linear-light (r, g, b) floats 0..1, row 0 = top row. The engine composes the frame
(effect -> start reveal -> top-row bar -> idle fade -> white calibration), converts it to sRGB and sends it:
per-key keyboards as a 12h picture (the same packets BetterRGB sends: 08h user mode, 12h, 8 x 65-byte rows),
four-zone keyboards as four zone colours (the average of each zone).
"""
import base64
import colorsys
import logging
import math
import random
import threading
import time

log = logging.getLogger("uwccd.fx")

ROWS, COLS = 6, 21
N = ROWS * COLS
FX_BASE = 100

# ------------------------------------------------------------------------------------------- colour math
_S2L = [((v / 255.0) / 12.92 if v / 255.0 <= 0.04045 else (((v / 255.0) + 0.055) / 1.055) ** 2.4) for v in range(256)]


def s2l(v):
    return _S2L[max(0, min(255, int(v)))]


def l2s(x):
    if x <= 0.0:
        return 0
    if x >= 1.0:
        return 255
    c = x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1.0 / 2.4) - 0.055
    return max(0, min(255, int(c * 255.0 + 0.5)))


def lin(c):
    return (s2l(c[0]), s2l(c[1]), s2l(c[2]))


def hsv(h):
    """hue in degrees -> sRGB bytes (full saturation and value), as hsv_to_rgb of the original"""
    r, g, b = colorsys.hsv_to_rgb((h % 360.0) / 360.0, 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def smooth(v):
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return v * v * (3.0 - 2.0 * v)


def wrap(v):
    return v % 1.0


def palette(colors, phase):
    """three colours blended around a circle (sample_palette_linear) -> linear rgb"""
    n = len(colors)
    x = wrap(phase) * n
    i = min(int(x), n - 1)
    a, b = colors[i], colors[(i + 1) % n]
    m = smooth(x - math.floor(x))
    return tuple(a[k] * (1.0 - m) + b[k] * m for k in range(3))


def white_gains(observed):
    """calculate_white_calibration: the colour seen on the keyboard for raw white -> per-mille gains (50..1000) that
    bring the strong channels down to the weakest one (linear light). None if the colour is too dark."""
    r, g, b = lin(observed)
    strong, weak = max(r, g, b), min(r, g, b)
    if strong < 0.01 or weak < 0.0005:
        return None
    return [max(50, min(1000, int(weak / c * 1000.0 + 0.5))) if c > 0.000001 else 1000 for c in (r, g, b)]


# ------------------------------------------------------------------------------------------- key geometry
# Approximate key positions on the 6 x 21 grid of Uniwill per-key keyboards (anchored on the gaming zones of
# GCUService: W/A/S/D and the arrows). Used by the reactive effects to find the pressed key.
_ROWS = (
    ("Esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "PrtSc", "Ins", "Del", "Home",
     "End", "PgUp", "PgDn", "Pause"),
    ("Grave", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Minus", "Equals", "Backspace", None, None, None,
     "NumLock", "NumDiv", "NumMul", "NumMinus"),
    ("Tab", None, "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "BracketL", "BracketR", "Backslash", None, None,
     "Num7", "Num8", "Num9", "NumPlus"),
    ("CapsLock", None, "A", "S", "D", "F", "G", "H", "J", "K", "L", "Semicolon", "Quote", None, "Enter", None, None,
     "Num4", "Num5", "Num6", None),
    ("ShiftL", "IsoBackslash", None, "Z", "X", "C", "V", "B", "N", "M", "Comma", "Period", "Slash", "ShiftR", "Up",
     None, None, "Num1", "Num2", "Num3", "NumEnter"),
    ("CtrlL", "Fn", "Win", "AltL", None, None, "Space", None, None, "AltR", "Menu", "CtrlR", None, "Left", "Down",
     "Right", None, None, "Num0", "NumDot", None),
)
KEY_CELL = {name: r * COLS + c for r, row in enumerate(_ROWS) for c, name in enumerate(row) if name}

# Linux input-event-codes.h -> key name
EVDEV = {1: "Esc", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0", 12: "Minus",
         13: "Equals", 14: "Backspace", 15: "Tab", 16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U",
         23: "I", 24: "O", 25: "P", 26: "BracketL", 27: "BracketR", 28: "Enter", 29: "CtrlL", 30: "A", 31: "S",
         32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L", 39: "Semicolon", 40: "Quote", 41: "Grave",
         42: "ShiftL", 43: "Backslash", 44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M", 51: "Comma",
         52: "Period", 53: "Slash", 54: "ShiftR", 55: "NumMul", 56: "AltL", 57: "Space", 58: "CapsLock",
         59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5", 64: "F6", 65: "F7", 66: "F8", 67: "F9", 68: "F10",
         69: "NumLock", 71: "Num7", 72: "Num8", 73: "Num9", 74: "NumMinus", 75: "Num4", 76: "Num5", 77: "Num6",
         78: "NumPlus", 79: "Num1", 80: "Num2", 81: "Num3", 82: "Num0", 83: "NumDot", 86: "IsoBackslash", 87: "F11",
         88: "F12", 96: "NumEnter", 97: "CtrlR", 98: "NumDiv", 99: "PrtSc", 100: "AltR", 102: "Home", 103: "Up",
         104: "PgUp", 105: "Left", 106: "Right", 107: "End", 108: "Down", 109: "PgDn", 110: "Ins", 111: "Del",
         119: "Pause", 125: "Win", 127: "Menu"}

# Windows virtual-key codes -> key name (the tray program polls these while a reactive effect runs)
VK = {0x1B: "Esc", 0x09: "Tab", 0x14: "CapsLock", 0xA0: "ShiftL", 0xA1: "ShiftR", 0xA2: "CtrlL", 0xA3: "CtrlR",
      0xA4: "AltL", 0xA5: "AltR", 0x5B: "Win", 0x5D: "Menu", 0x20: "Space", 0x0D: "Enter", 0x08: "Backspace",
      0xC0: "Grave", 0xBD: "Minus", 0xBB: "Equals", 0xDB: "BracketL", 0xDD: "BracketR", 0xDC: "Backslash",
      0xBA: "Semicolon", 0xDE: "Quote", 0xBC: "Comma", 0xBE: "Period", 0xBF: "Slash", 0xE2: "IsoBackslash",
      0x2C: "PrtSc", 0x2D: "Ins", 0x2E: "Del", 0x24: "Home", 0x23: "End", 0x21: "PgUp", 0x22: "PgDn",
      0x13: "Pause", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down", 0x90: "NumLock", 0x6A: "NumMul",
      0x6B: "NumPlus", 0x6D: "NumMinus", 0x6E: "NumDot", 0x6F: "NumDiv"}
VK.update({0x41 + i: chr(0x41 + i) for i in range(26)})
VK.update({0x30 + i: str(i) for i in range(10)})
VK.update({0x70 + i: f"F{i + 1}" for i in range(12)})
VK.update({0x60 + i: f"Num{i}" for i in range(10)})

POS = [(float(i % COLS), float(i // COLS)) for i in range(N)]       # (x, y) of every cell, in key pitches
CENTER = (8.5, 3.0)                                                  # between J and K
BAR_KEYS = list(range(20))                                           # the top row: Esc .. PgDn


def cell_of(name):
    return KEY_CELL.get(str(name))


# ------------------------------------------------------------------------------------------- effects
class Effect:
    needs = ()          # inputs from the user session: "keys", "screen"

    def __init__(self, p):
        self.p = p
        self.rng = random.Random()

    def num(self, key, default, lo, hi):
        try:
            v = float(self.p.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    def colors(self, n, default):
        cols = [tuple(int(x) & 255 for x in c[:3]) for c in (self.p.get("colors") or []) if len(c) >= 3]
        cols = (cols + list(default))[:n]
        return cols

    def press(self, cell, now):
        pass

    def feed(self, image):
        pass

    def update_metrics(self, metrics):
        pass

    def status(self):
        return {}

    def frame(self, t, k):           # t: seconds since start, k: frames of the original at 30 fps since last frame
        raise NotImplementedError


def _fill(c):
    return [c] * N


class Breathing(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.phase, self.prev = 0.0, 0.5
        self.cur = self._random() if p.get("random") else self.colors(1, [(0, 120, 255)])[0]

    def _random(self):
        return hsv(self.rng.randrange(360))

    def frame(self, t, k):
        raw = (math.sin(self.phase) + 1.0) / 2.0
        if self.p.get("random") and raw > self.prev and self.prev < 0.03:
            self.cur = self._random()
        self.prev = raw
        levels = int(self.num("smooth", 60, 2, 100))
        bright = math.floor(raw * levels) / levels
        self.phase += self.num("speed", 12, 1, 30) / 100.0 * k
        return _fill(lin(tuple(int(v * bright) for v in self.cur)))


class Wave(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.hue = 0.0

    def frame(self, t, k):
        a = math.radians(self.num("angle", 0, 0, 359))
        dx, dy = math.cos(a), math.sin(a)
        out = [lin(hsv(self.hue + (x * dx + y * dy) * 15.0)) for x, y in POS]
        self.hue += self.num("speed", 4, 1, 10) * k
        return out


class Sparkle(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.age, self.life, self.col = [0.0] * N, [1.0] * N, [(0, 0, 0)] * N

    def frame(self, t, k):
        speed, target = self.num("speed", 5, 1, 10), int(self.num("density", 8, 1, 30))
        life = max(18, 70 - speed * 5)
        alive = sum(1 for a in self.age if a > 0)
        for _ in range(max(0, target - alive)):
            for _try in range(20):
                c = self.rng.randrange(N)
                if self.age[c] == 0:
                    self.age[c], self.life[c] = 1.0, life + self.rng.randrange(12)
                    self.col[c] = lin(hsv(self.rng.randrange(360)))
                    break
        out = []
        for i in range(N):
            if self.age[i] > 0:
                env = math.sin(math.pi * min(1.0, self.age[i] / self.life[i])) ** 2
                out.append(tuple(v * env for v in self.col[i]))
                self.age[i] += k
                if self.age[i] >= self.life[i]:
                    self.age[i] = 0.0
            else:
                out.append((0.0, 0.0, 0.0))
        return out


class Reactive(Effect):
    needs = ("keys",)
    DURATION = {"short": 10, "medium": 20, "long": 40}

    def __init__(self, p):
        super().__init__(p)
        self.life, self.col = [0.0] * N, [(0, 0, 0)] * N
        self.queue = []

    def press(self, cell, now):
        self.queue.append(cell)

    def frame(self, t, k):
        dur = self.DURATION.get(self.p.get("duration"), 20)
        base = self.colors(1, [(255, 255, 255)])[0]
        while self.queue:
            c = self.queue.pop(0)
            self.col[c] = tuple(self.rng.randrange(256) for _ in range(3)) if self.p.get("random", True) else base
            self.life[c] = float(dur)
        out = []
        for i in range(N):
            if self.life[i] > 0:
                f = self.life[i] / dur
                out.append(lin(tuple(int(v * f) for v in self.col[i])))
                self.life[i] -= k
            else:
                out.append((0.0, 0.0, 0.0))
        return out


class Wheel(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.t = 0.0
        cx = sum(x for x, _ in POS) / N
        cy = sum(y for _, y in POS) / N
        self.ang = [math.degrees(math.atan2(y - cy, x - cx)) for x, y in POS]

    def frame(self, t, k):
        d = -1.0 if self.p.get("reverse") else 1.0
        out = [lin(hsv(self.t * d + a)) for a in self.ang]
        self.t += self.num("speed", 4, 1, 10) * k
        return out


class Lightning(Effect):
    MAX = 4

    def __init__(self, p):
        super().__init__(p)
        r = self.rng
        self.head = [100.0] * self.MAX
        self.bx = [10.0] * self.MAX
        self.seed = [r.randrange(628) / 100.0 for _ in range(self.MAX)]
        self.count = [10.0 + r.randrange(30) for _ in range(self.MAX)]
        self.prev = [0.0] * N

    def frame(self, t, k):
        speed = 0.05 + self.num("speed", 5, 1, 10) * 0.08
        sm = self.num("smooth", 10, 0, 20)
        band = 0.4 + sm * 0.15
        tail = band * 2.5
        finish = 6.0 + tail + 0.5
        sigma = 0.18 + self.num("width", 2, 1, 5) * 0.10
        conc = int(self.num("concurrent", 1, 1, self.MAX))
        bright = [0.0] * N
        for s in range(conc):
            if self.head[s] > finish:
                self.count[s] -= k
                if self.count[s] <= 0:
                    self.head[s] = -2.0
                    self.bx[s] = self.rng.randrange(COLS * 100 - 100) / 100.0
                    self.seed[s] = self.rng.randrange(628) / 100.0
                    self.count[s] = 20.0 + self.rng.randrange(40)
            if self.head[s] <= finish:
                for i, (x, y) in enumerate(POS):
                    dv = self.head[s] - y
                    dh = x - (self.bx[s] + math.sin(y * 2.35 + self.seed[s]) * 0.32)
                    hz = math.exp(-0.5 * (dh / sigma) ** 2)
                    if hz < 0.02:
                        continue
                    front = smooth((dv + 0.85) / 0.85) if dv < 0 else 1.0
                    tl = math.exp(-dv / (tail * 0.52)) if dv > 0 else 1.0
                    bright[i] = max(bright[i], front * tl * hz)
                self.head[s] += speed * k
        attack = 0.62 / (1.0 + sm * 0.065)
        release = 0.24 / (1.0 + sm * 0.055)
        out = []
        for i in range(N):
            tgt = 0.0 if bright[i] < 0.002 else bright[i]
            c = attack if tgt > self.prev[i] else release
            self.prev[i] += (tgt - self.prev[i]) * min(1.0, c * k)
            g = self.prev[i]
            out.append((0.0012 + g * 0.90, 0.0012 + g * 0.90, 0.0044 + g))
        return out


class Flame(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.heat = [100.0 + self.rng.randrange(60) for _ in range(N)]
        self.frames = 0.0

    def frame(self, t, k):
        speed, sm = self.num("speed", 5, 1, 10), self.num("smooth", 8, 0, 15)
        alpha = 1.0 / (1.0 + sm * 0.6)
        vol = 40.0 + speed * 18.0
        every = max(1, 11 - int(speed))
        before = self.frames
        self.frames += k
        if int(self.frames / every) != int(before / every):
            for i, (_, y) in enumerate(POS):
                target = 90.0 + 40.0 * (y / 6.0) + (self.rng.randrange(int(vol)) - vol / 2.0)
                self.heat[i] = max(0.0, min(255.0, self.heat[i] * (1.0 - alpha) + target * alpha))
        out = []
        for h in self.heat:
            h = int(h)
            if h < 85:
                c = (h * 3, 0, 0)
            elif h < 170:
                c = (255, (h - 85) * 3, 0)
            else:
                c = (255, 255, (h - 170) * 3)
            out.append(lin(c))
        return out


class Rain(Effect):
    MAX = 20
    DEFAULT = [(80, 140, 255), (120, 80, 255), (80, 220, 255), (255, 255, 255), (80, 255, 180)]

    def __init__(self, p):
        super().__init__(p)
        r = self.rng
        self.x = [float(r.randrange(COLS - 1)) for _ in range(self.MAX)]
        self.row = [-float(r.randrange(8)) for _ in range(self.MAX)]
        self.ci = [r.randrange(5) for _ in range(self.MAX)]
        self.prev = [[0.0, 0.0, 0.0] for _ in range(N)]

    def frame(self, t, k):
        speed = 0.05 + self.num("speed", 5, 1, 10) * 0.03
        cols = [lin(c) for c in self.colors(int(self.num("color_count", 1, 1, 5)), self.DEFAULT)]
        drops = min(self.MAX, int(self.num("density", 3, 1, 5)) * 3)
        tgt = [[0.0, 0.0, 0.0] for _ in range(N)]
        for d in range(drops):
            cr, cg, cb = cols[self.ci[d] % len(cols)]
            for i, (x, y) in enumerate(POS):
                dx = (x - self.x[d]) / 0.46
                hz = math.exp(-0.5 * dx * dx)
                if hz < 0.003:
                    continue
                dy = self.row[d] - y
                head = math.exp(-0.5 * (dy / 0.34) ** 2)
                tail = 0.52 * math.exp(-dy / 1.15) if dy > 0 else 0.0
                it = hz * (head + tail)
                tg = tgt[i]
                tg[0] += cr * it
                tg[1] += cg * it
                tg[2] += cb * it
            self.row[d] += speed * k
            if self.row[d] > 8:
                self.row[d] = -float(self.rng.randrange(5))
                self.x[d] = float(self.rng.randrange(COLS - 1))
                self.ci[d] = self.rng.randrange(len(cols))
        out = []
        for i in range(N):
            pv, tg = self.prev[i], tgt[i]
            c = 0.42 if sum(tg) > sum(pv) else 0.19
            c = min(1.0, c * k)
            for j in range(3):
                pv[j] += (tg[j] - pv[j]) * c
            out.append(tuple(pv))
        return out


class Matrix(Effect):
    DEFAULT = [(0, 255, 60), (0, 180, 255), (255, 0, 120)]

    def __init__(self, p):
        super().__init__(p)
        r = self.rng
        n = max(1, min(3, int(self.num("color_count", 1, 1, 3))))
        self.angle = [math.radians(r.randrange(360)) for _ in range(5)]
        self.pos = [-30.0] * 5
        self.spd = [0.2 + r.randrange(100) / 100.0 for _ in range(5)]
        self.sci = [r.randrange(n) for _ in range(5)]
        self.active = int(self.num("density", 2, 1, 5))
        self.reroll = 0.0
        self.cpos = [-float(r.randrange(8)) for _ in range(24)]
        self.cspd = [0.05 + r.randrange(100) / 300.0 for _ in range(24)]
        self.cci = [r.randrange(n) for _ in range(24)]
        self.lang = [r.randrange(4) * math.pi / 2 for _ in range(3)]
        self.lpos = [-30.0 - i * 8.0 for i in range(3)]
        self.lspd = [0.6 + r.randrange(100) / 100.0 for _ in range(3)]
        self.lci = [r.randrange(n) for _ in range(3)]
        self.rx = [float(r.randrange(COLS - 1)) for _ in range(3)]
        self.ry = [float(r.randrange(ROWS + 1)) for _ in range(3)]
        self.rr = [i * 8.0 for i in range(3)]
        self.rci = [r.randrange(n) for _ in range(3)]

    def _prob(self, target):
        if target >= 5:
            return 5
        x = self.rng.randrange(100)
        return max(1, target - 1) if x < 25 else target if x < 75 else min(5, target + 1)

    def frame(self, t, k):
        n = max(1, min(3, int(self.num("color_count", 1, 1, 3))))
        cols = self.colors(3, self.DEFAULT)
        style = int(self.num("style", 0, 0, 3))
        mul = 0.3 + self.num("speed", 5, 1, 10) * 0.15
        r = self.rng
        bright, ci = [0.0] * N, [0] * N
        if style == 0:
            self.reroll += k
            if self.reroll >= 60:
                self.active, self.reroll = self._prob(int(self.num("density", 2, 1, 5))), 0.0
            for i, (x, y) in enumerate(POS):
                for s in range(self.active):
                    dist = abs(x * math.cos(self.angle[s]) + y * math.sin(self.angle[s]) - self.pos[s])
                    if dist < 1.5 and 1.0 - dist / 1.5 > bright[i]:
                        bright[i], ci[i] = 1.0 - dist / 1.5, self.sci[s] % n
            for s in range(self.active):
                self.pos[s] += self.spd[s] * mul * k
                if self.pos[s] > 30:
                    self.pos[s], self.angle[s] = -30.0, math.radians(r.randrange(360))
                    self.spd[s], self.sci[s] = 0.2 + r.randrange(100) / 100.0, r.randrange(n)
        elif style == 1:
            for i, (x, y) in enumerate(POS):
                c = max(0, min(23, int(x + 0.5)))
                dv = self.cpos[c] - y
                b = 1.0 if -0.3 <= dv < 0 else (1.0 - dv / 4.0 if 0 <= dv < 4.0 else 0.0)
                bright[i], ci[i] = max(0.0, b), self.cci[c] % n
            for c in range(24):
                self.cpos[c] += self.cspd[c] * mul * k
                if self.cpos[c] > 10:
                    self.cpos[c] = -float(r.randrange(6))
                    self.cspd[c], self.cci[c] = 0.05 + r.randrange(100) / 300.0, r.randrange(n)
        elif style == 2:
            lasers = 3 if self.num("density", 2, 1, 5) >= 4 else 2
            for i, (x, y) in enumerate(POS):
                for s in range(lasers):
                    dist = abs(x * math.cos(self.lang[s]) + y * math.sin(self.lang[s]) - self.lpos[s])
                    if dist < 0.6 and 1.0 - dist / 0.6 > bright[i]:
                        bright[i], ci[i] = 1.0 - dist / 0.6, self.lci[s] % n
            for s in range(lasers):
                self.lpos[s] += self.lspd[s] * mul * 1.5 * k
                if self.lpos[s] > 30:
                    self.lpos[s], self.lang[s] = -30.0 - r.randrange(20), r.randrange(4) * math.pi / 2
                    self.lspd[s], self.lci[s] = 0.6 + r.randrange(100) / 100.0, r.randrange(n)
        else:
            for i, (x, y) in enumerate(POS):
                for s in range(3):
                    ring = abs(math.hypot(x - self.rx[s], y - self.ry[s]) - self.rr[s])
                    if ring < 1.2 and 1.0 - ring / 1.2 > bright[i]:
                        bright[i], ci[i] = 1.0 - ring / 1.2, self.rci[s] % n
            for s in range(3):
                self.rr[s] += mul * 0.25 * k
                if self.rr[s] > 24:
                    self.rx[s], self.ry[s], self.rr[s] = float(r.randrange(COLS - 1)), float(r.randrange(ROWS + 1)), 0.0
                    self.rci[s] = r.randrange(n)
        return [lin(tuple(int(v * min(1.0, b)) for v in cols[c])) for b, c in zip(bright, ci)]


class Static(Effect):
    DEFAULT = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
               (255, 140, 0), (140, 0, 255), (0, 140, 140)]
    H_ZONES = {1: (0,) * 6, 2: (0, 0, 0, 0, 1, 1), 3: (0, 0, 1, 1, 1, 2), 4: (0, 1, 1, 2, 2, 3),
               5: (0, 1, 2, 3, 3, 4), 6: (0, 1, 2, 3, 4, 5)}

    def frame(self, t, k):
        vertical = self.p.get("layout") == "vertical"
        zones = int(self.num("zones", 1, 1, 10 if vertical else 6))
        cols = [lin(c) for c in self.colors(10, self.DEFAULT)]
        out = []
        for i in range(N):
            r, c = divmod(i, COLS)
            z = min(zones - 1, c * zones // COLS) if vertical else self.H_ZONES[zones][r]
            out.append(cols[z])
        return out


class Ripple(Effect):
    needs = ("keys",)

    def __init__(self, p):
        super().__init__(p)
        self.events = []

    def press(self, cell, now):
        x, y = POS[cell]
        c = hsv(self.rng.randrange(360)) if self.p.get("random", True) else self.colors(1, [(0, 180, 255)])[0]
        self.events = self.events[-19:] + [(x, y, now, c)]

    def frame(self, t, k):
        sp = self.num("speed", 5, 1, 10)
        speed = (0.006 + sp * 0.0015) * 1000.0          # key pitches per second
        width = 0.35 + self.num("width", 2, 1, 5) * 0.25
        life = (2300.0 - sp * 120.0) / 1000.0
        now = time.monotonic()
        self.events = [e for e in self.events if now - e[2] < life]
        out = []
        for x, y in POS:
            acc = [0.0, 0.0, 0.0]
            for ex, ey, st, c in self.events:
                el = now - st
                band = 1.0 - abs(math.hypot(x - ex, y - ey) - el * speed) / width
                if band <= 0:
                    continue
                it = band * (1.0 - el / life)
                for j in range(3):
                    acc[j] += c[j] * it
            out.append(lin(tuple(min(255.0, v) for v in acc)))
        return out


class Rainbow(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.hue, self.last = 0.0, None

    def frame(self, t, k):
        dt = 0.0 if self.last is None else t - self.last
        self.last = t
        self.hue = (self.hue + dt * (4.0 + self.num("speed", 6, 1, 10) * 2.0)) % 360.0
        return _fill(lin(hsv(self.hue)))


SAMPLE_X = (-0.28, 0.28, -0.28, 0.28)
SAMPLE_Y = (-0.22, -0.22, 0.22, 0.22)
CURRENT_X = (-0.44, -0.31, -0.19, -0.06, 0.06, 0.19, 0.31, 0.44)
RGB3 = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


class Quicksand(Effect):
    def frame(self, t, k):
        flow = t * (0.22 + self.num("speed", 5, 1, 10) * 0.16)
        wl = 1.15 + self.num("scale", 5, 1, 10) * 0.42
        pal = [lin(c) for c in self.colors(3, RGB3)]
        out = []
        for kx, ky in POS:
            acc = [0.0, 0.0, 0.0]
            for sx, sy in zip(SAMPLE_X, SAMPLE_Y):
                x, y = kx + sx, ky + sy
                wy = y - flow + 0.24 * math.sin(x * 0.68 + flow * 0.55) + 0.10 * math.sin(x * 1.73 - flow * 0.31)
                band = wy / wl
                it = (0.08 + 0.92 * smooth((math.sin(band * 2.0 * math.pi) + 1.0) * 0.5)) * \
                     (0.90 + 0.10 * math.sin(x * 2.41 + y * 3.17 + flow * 1.2))
                c = palette(pal, band + x * 0.035)
                for j in range(3):
                    acc[j] += c[j] * it
            out.append(tuple(v / 4.0 for v in acc))
        return out


class Current(Effect):
    def __init__(self, p):
        super().__init__(p)
        self.prev = [[0.0, 0.0, 0.0] for _ in range(N)]

    def frame(self, t, k):
        travel = 0.50 + self.num("speed", 5, 1, 10) * 0.40
        width = self.num("width", 4, 1, 10)
        cycle = 22.0 + width
        pal = [lin(c) for c in self.colors(3, RGB3)]
        out = []
        for i, (kx, row) in enumerate(POS):
            row = int(row)
            acc = [0.0, 0.0, 0.0]
            for sx in CURRENT_X:
                x = kx + sx
                tx = 19.0 - x if row & 1 else x
                behind = (math.fmod(t * travel + row * 3.35, cycle) - width) - tx
                if not -0.75 < behind < width + 0.75:
                    continue
                head = smooth((behind + 0.75) / 0.75) if behind < 0 else 1.0
                tail = smooth((width + 0.75 - behind) / 0.75) if behind > width else 1.0
                it = math.exp(-max(0.0, behind) / (0.42 * width + 0.45)) * head * tail
                c = palette(pal, row / 7.0 + tx * 0.045 + t * 0.075)
                for j in range(3):
                    acc[j] += c[j] * it
            pv = self.prev[i]
            tg = [v / 8.0 for v in acc]
            s = min(1.0, (0.30 if sum(tg) > sum(pv) else 0.14) * k)
            for j in range(3):
                pv[j] += (tg[j] - pv[j]) * s
            out.append(tuple(pv))
        return out


class TouchCurrent(Effect):
    needs = ("keys",)

    def __init__(self, p):
        super().__init__(p)
        self.events = []

    def press(self, cell, now):
        x, y = POS[cell]
        self.events = self.events[-19:] + [(int(y), x, self.rng.random(), now)]

    def frame(self, t, k):
        travel = 0.75 + self.num("speed", 5, 1, 10) * 0.58
        sigma = 0.20 + self.num("width", 2, 1, 5) * 0.20
        life = (21.0 + sigma * 3.0) / travel
        pal = [lin(c) for c in self.colors(3, RGB3)]
        now = time.monotonic()
        self.events = [e for e in self.events if now - e[3] < life]
        out = []
        for kx, ky in POS:
            row = int(ky)
            acc = [0.0, 0.0, 0.0]
            evs = [e for e in self.events if e[0] == row]
            if evs:
                for sx in SAMPLE_X:
                    x = kx + sx
                    smp = [0.0, 0.0, 0.0]
                    for _, ox, ph, st in evs:
                        el = now - st
                        d = abs(abs(x - ox) - el * travel)
                        it = math.exp(-(d * d) / (2.0 * sigma * sigma)) * (1.0 - smooth(el / life))
                        c = palette(pal, ph + (x - ox) * 0.045 + el * 0.12)
                        for j in range(3):
                            smp[j] += c[j] * it
                    for j in range(3):
                        acc[j] += min(1.0, smp[j])
            out.append(tuple(v / 4.0 for v in acc))
        return out


class ScreenAmbient(Effect):
    """The user-session program sends a small picture of the screen (W x H, sRGB); every key takes the blurred
    colour of its place on the screen. Nothing is stored."""
    needs = ("screen",)

    def __init__(self, p):
        super().__init__(p)
        self.img = None
        self.prev = None
        self.lock = threading.Lock()

    def feed(self, image):
        with self.lock:
            self.img = image

    def frame(self, t, k):
        with self.lock:
            img = self.img
        if not img:
            return self.prev and [tuple(c) for c in self.prev] or _fill((0.0, 0.0, 0.0))
        w, h, px = img
        rad = max(1, int(round(self.num("blur", 3, 1, 8) * w / 96.0)))
        resp = min(1.0, (0.08 + self.num("response", 5, 1, 10) * 0.052) * k)
        tgt = []
        for x, y in POS:
            cx = int(x / (COLS - 1) * (w - 1) + 0.5)
            cy = int(y / (ROWS - 1) * (h - 1) + 0.5)
            acc, wsum = [0.0, 0.0, 0.0], 0.0
            for dy in range(-rad, rad + 1):
                sy = cy + dy
                if not 0 <= sy < h:
                    continue
                for dx in range(-rad, rad + 1):
                    sx = cx + dx
                    if not 0 <= sx < w:
                        continue
                    wt = 1.0 - math.hypot(dx, dy) / (rad + 1)
                    if wt <= 0:
                        continue
                    o = (sy * w + sx) * 3
                    acc[0] += _S2L[px[o]] * wt
                    acc[1] += _S2L[px[o + 1]] * wt
                    acc[2] += _S2L[px[o + 2]] * wt
                    wsum += wt
            tgt.append([v / wsum if wsum else 0.0 for v in acc])
        if self.prev is None:
            self.prev = tgt
        else:
            for pv, tg in zip(self.prev, tgt):
                for j in range(3):
                    pv[j] += (tg[j] - pv[j]) * resp
        return [tuple(c) for c in self.prev]


class Temperature(Effect):
    """Two solid halves driven by the sampler, with colour smoothing in real time."""
    COLORS = ((0, 180, 255), (0, 218, 255), (0, 255, 255), (0, 255, 200), (0, 255, 120),
              (0, 255, 40), (80, 255, 0), (160, 255, 0), (220, 255, 0), (255, 230, 0),
              (255, 190, 0), (255, 145, 0), (255, 95, 0), (255, 45, 0), (255, 0, 0))
    # Equally spaced 40..85 °C, rounded to integer sensor temperatures; identical for CPU and GPU.
    DEFAULT_TEMPS = (40, 43, 46, 50, 53, 56, 59, 62, 66, 69, 72, 75, 79, 82, 85)

    def __init__(self, p):
        super().__init__(p)
        self.temperatures = {"cpu": None, "gpu": None}
        self.previous = {"cpu": None, "gpu": None}
        self.last_t = None
        self.points = {sensor: [(point["temp"], lin(point["color"])) for point in p[sensor + "_points"]]
                       for sensor in ("cpu", "gpu")}

    def update_metrics(self, metrics):
        temperatures = {}
        for sensor in ("cpu", "gpu"):
            v = metrics.get(sensor + "_temp")
            valid = (isinstance(v, (int, float)) and not isinstance(v, bool)
                     and 0 <= v <= 150 and math.isfinite(v))
            temperatures[sensor] = v if valid else None
        self.temperatures = temperatures

    def status(self):
        return {"temperatures": dict(self.temperatures)}

    def _color(self, sensor, temp):
        points = self.points[sensor]
        if temp <= points[0][0]:
            return points[0][1]
        for i in range(1, len(points)):
            if temp <= points[i][0]:
                low, a = points[i - 1]
                high, b = points[i]
                mix = (temp - low) / (high - low)
                return tuple(a[j] + (b[j] - a[j]) * mix for j in range(3))
        return points[-1][1]

    def frame(self, t, k):
        dt = max(0.0, t - self.last_t) if self.last_t is not None else 0.0
        self.last_t = t
        tau = self.p["smoothing_ms"] / 1000.0
        alpha = -math.expm1(-dt / tau) if tau else 1.0
        colors = {}
        for sensor, temp in self.temperatures.items():
            if temp is None:
                # Freeze the last displayed colour, including an unfinished smooth transition.
                # Before the first valid sample, use the first colour of this sensor's curve.
                prev = self.previous[sensor]
                colors[sensor] = prev if prev is not None else self.points[sensor][0][1]
                continue
            target = self._color(sensor, temp)
            prev = self.previous[sensor]
            color = target if prev is None else tuple(prev[j] + (target[j] - prev[j]) * alpha for j in range(3))
            self.previous[sensor] = colors[sensor] = color
        left = self.p["left"]
        right = "gpu" if left == "cpu" else "cpu"
        return [colors[left if x < COLS // 2 else right] for x, _ in POS]


def decode_screen(d):
    """{"w", "h", "rgb": base64 of w*h*3 sRGB bytes} from the user-session program -> (w, h, bytes)"""
    w, h = int(d["w"]), int(d["h"])
    if not (4 <= w <= 256 and 2 <= h <= 144):
        raise ValueError("screen: size")
    px = base64.b64decode(d["rgb"])
    if len(px) != w * h * 3:
        raise ValueError("screen: data length")
    return (w, h, px)


# id -> (name, class, parameters). Parameter: (key, kind, min, max, default) — kind: int | bool | choice | colors
P_SPEED = ("speed", "int", 1, 10, 5)
EFFECTS = {
    100: ("Breathing", Breathing, [("speed", "int", 1, 30, 12), ("smooth", "int", 2, 100, 60),
                                   ("random", "bool", 0, 1, False), ("colors", "colors", 1, 1, [[0, 120, 255]])]),
    101: ("Wave", Wave, [("speed", "int", 1, 10, 4), ("angle", "int", 0, 359, 0)]),
    102: ("Sparkle", Sparkle, [P_SPEED, ("density", "int", 1, 30, 8)]),
    103: ("Reactive", Reactive, [("duration", "choice", ["short", "medium", "long"], None, "medium"),
                                 ("random", "bool", 0, 1, True), ("colors", "colors", 1, 1, [[255, 255, 255]])]),
    104: ("Colour wheel", Wheel, [("speed", "int", 1, 10, 4), ("reverse", "bool", 0, 1, False)]),
    105: ("Lightning", Lightning, [P_SPEED, ("smooth", "int", 0, 20, 10), ("width", "int", 1, 5, 2),
                                   ("concurrent", "int", 1, 4, 1)]),
    106: ("Flame", Flame, [P_SPEED, ("smooth", "int", 0, 15, 8)]),
    107: ("Rain", Rain, [P_SPEED, ("density", "int", 1, 5, 3), ("color_count", "int", 1, 5, 1),
                         ("colors", "colors", 1, 5, [list(c) for c in Rain.DEFAULT])]),
    108: ("Matrix", Matrix, [P_SPEED, ("style", "choice", ["streaks", "columns", "lasers", "ripples"], None, "streaks"),
                             ("density", "int", 1, 5, 2), ("color_count", "int", 1, 3, 1),
                             ("colors", "colors", 1, 3, [list(c) for c in Matrix.DEFAULT])]),
    109: ("Static zones", Static, [("layout", "choice", ["horizontal", "vertical"], None, "horizontal"),
                                   ("zones", "int", 1, 10, 1), ("colors", "colors", 1, 10, [list(c) for c in Static.DEFAULT])]),
    110: ("Reactive ripple", Ripple, [P_SPEED, ("width", "int", 1, 5, 2), ("random", "bool", 0, 1, True),
                                      ("colors", "colors", 1, 1, [[0, 180, 255]])]),
    111: ("Rainbow", Rainbow, [("speed", "int", 1, 10, 6)]),
    112: ("Quicksand", Quicksand, [P_SPEED, ("scale", "int", 1, 10, 5), ("colors", "colors", 3, 3, [list(c) for c in RGB3])]),
    113: ("Current", Current, [P_SPEED, ("width", "int", 1, 10, 4), ("colors", "colors", 3, 3, [list(c) for c in RGB3])]),
    114: ("Reactive current", TouchCurrent, [P_SPEED, ("width", "int", 1, 5, 2),
                                             ("colors", "colors", 3, 3, [list(c) for c in RGB3])]),
    115: ("Screen ambient", ScreenAmbient, [("blur", "int", 1, 8, 3), ("response", "int", 1, 10, 5)]),
    116: ("CPU / GPU temperature", Temperature,
          [("left", "choice", ["cpu", "gpu"], None, "cpu")]
          + [(sensor + "_points", "temperature_points", 2, 15,
              [{"temp": temp, "color": list(color)} for temp, color in zip(Temperature.DEFAULT_TEMPS, Temperature.COLORS)])
             for sensor in ("cpu", "gpu")]
          + [("smoothing_ms", "int", 0, 5000, 1000)]),
}
CHOICE_INDEX = {"style": ["streaks", "columns", "lasers", "ripples"]}


def is_fx(idx):
    return idx in EFFECTS


def clean_params(idx, params):
    """user parameters -> only the known keys, within their ranges"""
    out = {}
    params = params or {}
    for key, kind, lo, hi, default in EFFECTS[idx][2]:
        v = params.get(key, default)
        if kind == "int":
            try:
                v = int(round(float(v)))
            except (TypeError, ValueError, OverflowError):
                v = default
            v = max(lo, min(hi, v))
        elif kind == "bool":
            v = bool(v)
        elif kind == "choice":
            v = v if v in lo else default
            if key in CHOICE_INDEX:
                out[key + "_i"] = CHOICE_INDEX[key].index(v)
        elif kind == "colors":
            cols = []
            for c in (v if isinstance(v, list) else default):
                if isinstance(c, (list, tuple)) and len(c) >= 3:
                    cols.append([max(0, min(255, int(x))) for x in c[:3]])
            v = (cols or default)[:hi]
        elif kind == "temperature_points":
            if not isinstance(v, list) or not lo <= len(v) <= hi:
                raise ValueError("temperature curve needs 2 to 15 points")
            points = []
            for point in v:
                temp = point.get("temp") if isinstance(point, dict) else None
                color = point.get("color") if isinstance(point, dict) else None
                if (isinstance(temp, bool) or not isinstance(temp, (int, float))
                        or not 0 <= temp <= 120 or not math.isfinite(temp) or int(temp) != temp):
                    raise ValueError("temperature points need integer temperatures from 0 to 120 °C")
                if (not isinstance(color, (list, tuple)) or len(color) != 3
                        or any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255 for c in color)):
                    raise ValueError("temperature points need RGB colours from 0 to 255")
                if points and temp <= points[-1]["temp"]:
                    raise ValueError("temperature points must have strictly increasing temperatures")
                points.append({"temp": int(temp), "color": list(color)})
            v = points
        out[key] = v
    return out


def make(idx, params):
    p = clean_params(idx, params)
    if "style_i" in p:
        p = {**p, "style": p["style_i"]}
    return EFFECTS[idx][1](p)


def catalog():
    """for the window: id -> name, parameters and the inputs the effect needs"""
    return {i: {"name": n, "needs": list(c.needs),
                "params": [{"key": k, "kind": kind, "min": lo if kind != "choice" else None,
                            "max": hi, "options": lo if kind == "choice" else None, "default": d}
                           for k, kind, lo, hi, d in ps]} for i, (n, c, ps) in EFFECTS.items()}


# ------------------------------------------------------------------------------------------- transitions
TRANSITIONS = ["off", "fade", "ripple_center", "ripple_edges", "ripple_top", "ripple_bottom", "ripple_left",
               "ripple_right", "snake_main_out_in", "snake_main_in_out", "snake_anti_out_in", "snake_anti_in_out"]
_RANKS = {}


def _snake_rank(nx, ny, main, inside_out):
    best, best_t = 1e30, 0.0
    start = 3 * math.pi / 4 if main else math.pi / 4
    direction = -1.0 if main else 1.0
    yu = -ny
    for s in range(120):
        t = s / 119.0
        rad = 1.4142135623730951 * (1.0 - t)
        ang = start + direction * 1.25 * 2 * math.pi * t
        sx, sy = rad * math.cos(ang), rad * math.sin(ang)
        d = min((nx - sx) ** 2 + (yu - sy) ** 2, (nx + sx) ** 2 + (yu + sy) ** 2)
        if d < best:
            best, best_t = d, t
    return 1.0 - best_t if inside_out else best_t


def ranks(mode):
    """per-cell rank 0..1 (when the cell is reached) and the feather of a transition"""
    if mode in _RANKS:
        return _RANKS[mode]
    xs, ys = [p[0] for p in POS], [p[1] for p in POS]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx, cy = CENTER
    maxd = max(0.5, max(math.hypot(x - cx, y - cy) for x, y in POS))
    out, feather = [], 0.18
    for x, y in POS:
        u, v = (x - x0) / (x1 - x0), (y - y0) / (y1 - y0)
        nx = (x - cx) / ((cx - x0) if x < cx else (x1 - cx))
        ny = (y - cy) / ((cy - y0) if y < cy else (y1 - cy))
        if mode == "ripple_center":
            r = max(0.0, math.hypot(x - cx, y - cy) - 0.5) / (maxd - 0.5)
        elif mode == "ripple_edges":
            r = 2.0 * min(u, 1 - u, v, 1 - v)
        elif mode == "ripple_top":
            r = v
        elif mode == "ripple_bottom":
            r = 1 - v
        elif mode == "ripple_left":
            r = u
        elif mode == "ripple_right":
            r = 1 - u
        elif mode.startswith("snake"):
            feather = 0.09
            r = _snake_rank(nx, ny, "_main_" in mode, mode.endswith("in_out"))
        else:
            r = 0.0
        out.append(max(0.0, min(1.0, r)))
    _RANKS[mode] = (out, feather)
    return _RANKS[mode]


def coverage(mode, progress):
    """per-cell coverage 0..1 of a transition at progress 0..1"""
    progress = max(0.0, min(1.0, progress))
    if mode == "off" or mode not in TRANSITIONS:
        return [1.0 if progress >= 1.0 else 0.0] * N
    if mode == "fade":
        return [smooth(progress)] * N
    rk, f = ranks(mode)
    return [smooth((progress - r * (1.0 - f)) / f) for r in rk]


def mask(frame, cov):
    return [(c[0] * m, c[1] * m, c[2] * m) for c, m in zip(frame, cov)]


# ------------------------------------------------------------------------------------------- top-row bar
BAR_MODES = ["off", "battery", "volume", "mic", "cpu", "gpu", "audio"]
BAR_DIRECTIONS = ["left_to_right", "right_to_left", "edges_to_center", "center_to_edges"]
BAR_DEFAULT = {"mode": "off", "direction": "left_to_right", "start": [0, 255, 80], "end": [255, 20, 0],
               "audio": [[255, 0, 0], [0, 255, 0], [0, 80, 255]]}


def bar_overlay(frame, level, mode, cfg, now):
    keys = len(BAR_KEYS)
    d = cfg.get("direction", "left_to_right")
    units = keys // 2 if d in ("edges_to_center", "center_to_edges") else keys
    level = max(0.0, min(1.0, level))
    filled = level * units
    a, z = lin(cfg.get("start") or BAR_DEFAULT["start"]), lin(cfg.get("end") or BAR_DEFAULT["end"])
    ph = smooth(1.0 - level if mode == "battery" else level)
    uni = tuple(a[j] * (1 - ph) + z[j] * ph for j in range(3))
    audio = [lin(c) for c in (cfg.get("audio") or BAR_DEFAULT["audio"])][:3]
    at = wrap(now / 12.0)
    out = list(frame)
    for i, cell in enumerate(BAR_KEYS):
        edge = min(i, keys - 1 - i)
        rank = (keys - 1 - i if d == "right_to_left" else edge if d == "edges_to_center"
                else units - 1 - edge if d == "center_to_edges" else i)
        cov = smooth(filled - rank)
        gp = rank / (units - 1) if units > 1 else 0.0
        c = palette(audio, at - gp * 0.72) if mode == "audio" and len(audio) == 3 else uni
        out[cell] = (c[0] * cov, c[1] * cov, c[2] * cov)
    return out


# ------------------------------------------------------------------------------------------- engine
DEFAULT_CONFIG = {"fps_ac": 30, "fps_battery": 15, "transition": "fade", "transition_ms": 800,
                  "gains": [1000, 1000, 1000], "bar": dict(BAR_DEFAULT)}
FPS_MIN, FPS_MAX = 10, 60
ZONE_FPS_MAX = 25            # four-zone keyboards: five feature reports per frame


def clean_config(cfg):
    c = dict(DEFAULT_CONFIG)
    c.update({k: v for k, v in (cfg or {}).items() if k in DEFAULT_CONFIG})
    c["fps_ac"] = max(FPS_MIN, min(FPS_MAX, int(c["fps_ac"])))
    c["fps_battery"] = max(FPS_MIN, min(FPS_MAX, int(c["fps_battery"])))
    c["transition"] = c["transition"] if c["transition"] in TRANSITIONS else "fade"
    c["transition_ms"] = max(100, min(5000, int(c["transition_ms"])))
    g = list(c.get("gains") or [1000, 1000, 1000])[:3] + [1000] * 3
    c["gains"] = [max(50, min(1000, int(x))) for x in g[:3]]
    b = dict(BAR_DEFAULT)
    b.update({k: v for k, v in (c.get("bar") or {}).items() if k in BAR_DEFAULT})
    b["mode"] = b["mode"] if b["mode"] in BAR_MODES else "off"
    b["direction"] = b["direction"] if b["direction"] in BAR_DIRECTIONS else "left_to_right"
    for key in ("start", "end"):
        v = b.get(key)
        b[key] = [max(0, min(255, int(x))) for x in v[:3]] if isinstance(v, list) and len(v) >= 3 else BAR_DEFAULT[key]
    au = [x for x in (b.get("audio") or []) if isinstance(x, list) and len(x) >= 3][:3]
    b["audio"] = [[max(0, min(255, int(x))) for x in c3[:3]] for c3 in au] if len(au) == 3 else BAR_DEFAULT["audio"]
    c["bar"] = b
    return c


def zones_linear(frame):
    """four-zone keyboards: the average colour of each zone (linear light), lifted a little so that effects with
    few lit keys still show (a single raindrop would vanish in the average)"""
    from .ite import ZONE_COLS
    out = []
    for c0, c1 in ZONE_COLS:
        cells = [frame[r * COLS + c] for r in range(ROWS) for c in range(c0, c1)]
        avg = [sum(p[j] for p in cells) / len(cells) for j in range(3)]
        peak = max(max(p) for p in cells)
        lift = min(3.0, peak / max(avg) if max(avg) > 1e-6 else 1.0) ** 0.5
        out.append(tuple(min(1.0, v * lift) for v in avg))
    return out


class FxEngine(threading.Thread):
    """The frame loop of one BetterRGB effect. kb: ITEKeyboard (write_picture / write_rows / write_zones).
    env: callable -> {"config": clean_config(...), "ac": bool, "metrics": {...}}"""

    def __init__(self, kb, idx, light, params, env):
        super().__init__(daemon=True, name="fx-" + EFFECTS[idx][0].lower().replace(" ", "-"))
        self.kb, self.idx, self.light = kb, idx, light
        self.params = clean_params(idx, params)
        self.effect = make(idx, params)
        self.env = env
        self._halt = threading.Event()
        self.lock = threading.Lock()
        self.fps = None
        self.effective = None
        self.slow = self.healthy = 0
        self.idle = "active"          # active | fading_out | asleep | fading_in
        self.idle_t0 = 0.0
        self.calibrating = False
        self.started = None
        self.bar_level = 0.0
        self.bar_mode_last = None
        self.last_volume, self.volume_until = None, 0.0
        self.last_out = None
        self.frames = 0
        self.errors = 0

    # -- control ---------------------------------------------------------------------------
    def stop(self):
        self._halt.set()

    def stopped(self):
        return self._halt.is_set()

    def needs(self):
        n = list(self.effect.needs)
        mode = self._cfg()["bar"]["mode"]
        if mode != "off" and not self.kb.four_zone():
            n.append("volume")              # a volume change shows the volume for 1.8 s
            if mode in ("mic", "audio"):
                n.append(mode)
        return n

    def press(self, names):
        now = time.monotonic()
        for name in names:
            c = cell_of(name)
            if c is not None:
                self.effect.press(c, now)

    def feed_screen(self, image):
        self.effect.feed(image)

    def set_idle(self, idle):
        with self.lock:
            now = time.monotonic()
            dur = self._cfg()["transition_ms"] / 1000.0
            if idle and self.idle in ("active", "fading_in"):
                done = (now - self.idle_t0) / dur if self.idle == "fading_in" else 1.0
                self.idle, self.idle_t0 = "fading_out", now - (1.0 - min(1.0, done)) * dur
            elif not idle and self.idle in ("asleep", "fading_out"):
                done = (now - self.idle_t0) / dur if self.idle == "fading_out" else 1.0
                self.idle, self.idle_t0 = "fading_in", now - (1.0 - min(1.0, done)) * dur
                self.last_out = None

    def calibrate(self, on):
        self.calibrating = bool(on)
        self.last_out = None

    def fade_out(self):
        """switching off: fade (or the chosen transition backwards) to black, then stop"""
        cfg = self._cfg()
        if cfg["transition"] == "off" or not self.is_alive():
            self.stop()
            return
        self.set_idle(True)
        end = time.monotonic() + cfg["transition_ms"] / 1000.0 + 0.3
        while time.monotonic() < end and self.idle != "asleep" and self.is_alive():
            time.sleep(0.02)
        self.stop()

    def info(self):
        return {"id": self.idx, "name": EFFECTS[self.idx][0], "fps": self.effective, "target_fps": self.fps,
                "needs": self.needs(), "idle": self.idle, "calibrating": self.calibrating, "frames": self.frames,
                **self.effect.status()}

    # -- frame pipeline -------------------------------------------------------------------
    def _cfg(self):
        try:
            return self.env()["config"]
        except Exception:  # noqa: BLE001
            return clean_config(None)

    def _bar(self, frame, env, now):
        cfg = env["config"]["bar"]
        mode = cfg["mode"]
        m = env.get("metrics") or {}
        vol = m.get("volume")
        if vol is not None:
            if self.last_volume is not None and abs(vol - self.last_volume) >= 0.004:
                self.volume_until = now + 1.8
            self.last_volume = vol
        if now < self.volume_until and mode != "off":
            mode = "volume"
        if mode == "off":
            self.bar_mode_last = None
            return frame
        target = {"battery": (m.get("battery") or 0) / 100.0, "volume": vol or 0.0,
                  "mic": math.sqrt(max(0.0, m.get("mic") or 0.0)), "audio": math.sqrt(max(0.0, m.get("audio") or 0.0)),
                  "cpu": (m.get("cpu") or 0) / 100.0, "gpu": (m.get("gpu") or 0) / 100.0}.get(mode, 0.0)
        target = max(0.0, min(1.0, target))
        c = 1.0 if mode != self.bar_mode_last else (0.48 if target > self.bar_level else 0.14)
        self.bar_level += (target - self.bar_level) * c
        self.bar_mode_last = mode
        return bar_overlay(frame, self.bar_level, mode, cfg, now)

    def compose(self, frame, env, now):
        cfg = env["config"]
        dur = cfg["transition_ms"] / 1000.0
        mode = cfg["transition"]
        if self.started is not None and now - self.started < dur and mode != "off":
            frame = mask(frame, coverage(mode, (now - self.started) / dur))
        if not self.kb.four_zone():
            frame = self._bar(frame, env, now)
        with self.lock:
            st = self.idle
            if st in ("fading_out", "fading_in"):
                p = (now - self.idle_t0) / dur if mode != "off" else 1.0
                if p >= 1.0:
                    self.idle = st = "asleep" if st == "fading_out" else "active"
                    p = 1.0
                if st in ("fading_out", "fading_in"):
                    frame = mask(frame, coverage(mode, 1.0 - p if st == "fading_out" else p))
            if st == "asleep":
                frame = [(0.0, 0.0, 0.0)] * N
        if self.calibrating:
            return [(1.0, 1.0, 1.0)] * N
        g = [x / 1000.0 for x in cfg["gains"]]
        if g != [1.0, 1.0, 1.0]:
            frame = [(c[0] * g[0], c[1] * g[1], c[2] * g[2]) for c in frame]
        return frame

    def send(self, frame, first):
        if self.kb.four_zone():
            out = [tuple(l2s(v) for v in z) for z in zones_linear(frame)]
            if out == self.last_out and not first:
                return
            self.kb.write_zones(out, self.light, announce=first)
        else:
            out = [(l2s(c[0]), l2s(c[1]), l2s(c[2])) for c in frame]
            if out == self.last_out and not first:
                return
            if getattr(self.kb, "pictures_ok", True):
                self.kb.write_picture(out, self.light, announce=first)
            else:
                self.kb.write_rows(out, self.light, announce=first)
        self.last_out = out
        self.frames += 1

    def _pace_result(self, ok, took):
        """record_transport_result: three slow frames -> 5 fps less, 10 s stable -> 1 fps more"""
        budget = 1.0 / self.effective
        if not ok:
            self.slow = self.healthy = 0
            self.effective = max(FPS_MIN, self.effective - 5)
            return
        if took >= budget * 0.9:
            self.healthy = 0
            self.slow += 1
            if self.slow >= 3:
                self.slow = 0
                self.effective = max(FPS_MIN, self.effective - 5)
                log.info("fx: frame rate lowered to %d (slow keyboard writes)", self.effective)
            return
        self.slow = 0
        if self.effective < self.fps:
            self.healthy += 1
            if self.healthy >= self.effective * 10:
                self.healthy = 0
                self.effective += 1

    def run(self):
        first, last = True, None
        t0 = time.monotonic()
        self.started = t0
        nxt = t0
        log.info("fx effect %s started", EFFECTS[self.idx][0])
        while not self._halt.is_set():
            env = self.env()
            cfg = env["config"]
            fps = cfg["fps_ac"] if env.get("ac", True) else cfg["fps_battery"]
            if self.kb.four_zone():
                fps = min(fps, ZONE_FPS_MAX)
            if fps != self.fps:
                self.fps = fps
                if self.effective is None or self.effective > fps:
                    self.effective = fps            # a higher target is reached step by step (_pace_result)
            now = time.monotonic()
            k = 1.0 if last is None else max(0.0, min(4.0, (now - last) * 30.0))
            last = now
            try:
                self.effect.update_metrics(env.get("metrics") or {})
                frame = self.effect.frame(now - t0, k)
                if self.idle == "asleep" and not self.calibrating and self.last_out is not None:
                    self._halt.wait(0.1)           # keys are dark: keep the effect state, send nothing
                    nxt = time.monotonic()
                    continue
                frame = self.compose(frame, env, now)
                ts = time.monotonic()
                self.send(frame, first)
                self._pace_result(True, time.monotonic() - ts)
                first = False
                self.errors = 0
            except OSError as e:
                self.errors += 1
                self._pace_result(False, 0)
                log.warning("fx frame: %s", e)
                if self.errors >= 20:
                    log.warning("fx effect stopped: the keyboard does not answer")
                    break
                self._halt.wait(0.5)
            except Exception:  # noqa: BLE001
                log.exception("fx effect %s", EFFECTS[self.idx][0])
                break
            nxt += 1.0 / self.effective
            now = time.monotonic()
            if now > nxt + 2.0 / self.effective:
                nxt = now
            self._halt.wait(max(0.0, nxt - now))
        log.info("fx effect %s stopped", EFFECTS[self.idx][0])
