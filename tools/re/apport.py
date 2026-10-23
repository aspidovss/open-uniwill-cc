"""Translate LM_ITE_RGB.AP_Effect_Task (software keyboard effects) + AlphabetEffect font into Python."""
import re
import sys

ap = open("/home/claude/cc/il/ap.txt").read()
lift = open("/home/claude/cc/il/GCUService.lift.txt").read()
out = open(sys.argv[1], "w")

rows = [(int(l.split(":")[0], 16), l.split(":", 1)[1].strip())
        for l in ap.split("\n") if re.match(r"\s+[0-9A-F]{5}:", l)]
EXCL = [(0x14F70, 0x15172), (0x15189, 0x15274)]
rows = [(o, s) for o, s in rows if o >= 0x14F46 and not any(a <= o < b for a, b in EXCL)]
offs = [o for o, _ in rows]


def target(t):
    for i, o in enumerate(offs):
        if o >= t:
            return i
    return len(offs)


def ex(e):
    e = e.replace("this.m_ap_effect_data.save_layout_color.ColorBuffer", "CB")
    e = e.replace("this.m_ap_effect_data.save_light", "ctx.light")
    e = e.replace("this.m_ap_effect_data.save_speed", "ctx.speed")
    e = e.replace("this.m_ap_effect_data.save_effect", "ctx.effect")
    e = e.replace("this.ColRightShift", "0").replace("this.ColShift", "0")
    e = e.replace("this.m_ITE_KB_Type", "ctx.kb_type")
    e = re.sub(r"Convert\.To\w+\(", "(", e)
    e = re.sub(r"Enumerable\.Count\((\w+)\)", r"len(\1)", e)
    e = e.replace(" / ", " // ")
    e = re.sub(r"!(?=[\w(])", "not ", e).replace("not =", "!=")
    e = e.replace("&v", "v")
    return e


out.write('''# Generated from GCUService LightingModel.LM_ITE_RGB.AP_Effect_Task / MyRgbKeyboard.AlphabetEffect.
# Software keyboard effects: Neon (0x0F), Alphabet (0x17), Impact (0x0D), Stack (0x0C).
# Do not edit by hand — regenerate with tools/apport.py.

class RGB:
    __slots__ = ("R", "G", "B", "ID")

    def __init__(self, R=0, G=0, B=0, ID=0):
        self.R, self.G, self.B, self.ID = R, G, B, ID

    def t(self):
        return (self.R & 255, self.G & 255, self.B & 255)

''')

# ---- AlphabetEffect font -----------------------------------------------------------
glyph = {}
for m in re.finditer(r"### MyControlCenter\.MyRgbKeyboard\.AlphabetEffect::(\w+)_ColorPosition\n(.*?)\n\n", lift, re.S):
    name = m.group(1)
    offsets = [int(x, 0) for x in re.findall(r"_an_color\[\(this\.shift \+ (0x[0-9a-f]+|\d+)\)\]", m.group(2))]
    offsets += [0 for _ in re.findall(r"_an_color\[this\.shift\]", m.group(2))]
    glyph["0" if name == "_0" else name] = sorted(offsets)
out.write("GLYPHS = {\n")
for k in sorted(glyph):
    out.write(f"    {k!r}: {glyph[k]},\n")
out.write("}\n\n")
out.write('''

def alphabet_frame(ch, colors, step, shift):
    """AlphabetEffect(ch, ColorBuffer, step).SetShift(shift).GetAlphbetEffect()"""
    buf = [RGB(ID=i) for i in range(126)]
    col = colors[step % 7] if colors else RGB(255, 255, 255)
    for o in GLYPHS.get(ch, []):
        if 0 <= shift + o < 126:
            buf[shift + o] = RGB(col.R, col.G, col.B, shift + o)
    for i in range(0x69, 0x7B):          # OutlerFixed
        buf[i] = RGB(ID=i)
    return buf


def run(ctx):
    CB = ctx.colors
    v0 = [RGB() for _ in range(3)]
    v1 = [RGB(ID=i) for i in range(126)]
    v2 = ctx.light
    v3 = 1
    v4 = v5 = 0
    v6 = 1.0
    v30 = v31 = v32 = v33 = v34 = v35 = v36 = v37 = v38 = v39 = v40 = v41 = v42 = v43 = 0
    pc = 0
    while True:
''')
for i, (o, s) in enumerate(rows):
    nxt = i + 1
    out.write(f"        if pc == {i}:  # {o:05X}: {s[:110]}\n")
    w = lambda code: out.write("            " + code + "\n")
    m = re.match(r"if \((.*)\) goto ([0-9A-F]+)$", s)
    if s == "if (this.m_effect_type != 4) goto 19D0A":
        w(f"pc = {target(0x19D0A)} if ctx.stopped() else {nxt}; continue"); continue
    if s == "if (!this.m_ap_effect_task_stop) goto 14F3A":
        w(f"pc = {target(0x14F3A)} if not ctx.stopped() else {nxt}; continue"); continue
    if s == "if (this.AlphabetString) goto 15378":
        w(f"pc = {nxt}; continue"); continue
    if s.startswith("v31 = Enumerable.ToArray("):
        w(f"v31 = list((ctx.alphabet or '').strip().upper()); pc = {nxt}; continue"); continue
    if s.startswith("new AlphabetEffect("):
        w(f"pc = {nxt}; continue"); continue
    if "new AlphabetEffect(" in s:
        w(f"v1 = alphabet_frame(v31[v5], CB, v4, v4 % v30); pc = {nxt}; continue"); continue
    if m:
        w(f"pc = {target(int(m.group(2), 16))} if ({ex(m.group(1))}) else {nxt}; continue"); continue
    m = re.match(r"goto ([0-9A-F]+)$", s)
    if m:
        w(f"pc = {target(int(m.group(1), 16))}; continue"); continue
    m = re.match(r"switch \((\w+)\) \[([^\]]*)\]$", s)
    if m:
        tg = [target(int(x)) for x in m.group(2).split(",")]
        w(f"_t = {tg}; pc = _t[{m.group(1)}] if 0 <= {m.group(1)} < len(_t) else {nxt}; continue"); continue
    m = re.match(r"this\.Set_ITE_Effect_Type_UserMode\(this\.m_ap_effect_data\.save_light, 0, (\w+), (\w+)\)$", s)
    if m:
        w(f"ctx.user_mode({m.group(1)}, {m.group(2)}); pc = {nxt}; continue"); continue
    m = re.match(r"this\.Set_ITE_Effect_Type_StaticMode\(this\.m_ap_effect_data\.save_light, 0, (\w+), (\w+)\)$", s)
    if m:
        w(f"ctx.static_mode({m.group(1)}[0], {m.group(2)}); pc = {nxt}; continue"); continue
    m = re.match(r"Thread\.Sleep\((.*)\)$", s)
    if m:
        w(f"if not ctx.sleep({ex(m.group(1))}): return"); w(f"pc = {nxt}; continue"); continue
    if s in ("this.m_ap_effect_task = null",):
        w(f"pc = {nxt}; continue"); continue
    if s.startswith("return"):
        w("return"); continue
    m = re.match(r"(.+?) = (.+)$", s)
    if m:
        w(f"{ex(m.group(1))} = {ex(m.group(2))}; pc = {nxt}; continue"); continue
    raise SystemExit(f"untranslated: {o:05X} {s}")
out.write(f"        if pc >= {len(rows)}:\n            return\n")
print("statements:", len(rows), "glyphs:", sorted(glyph))
