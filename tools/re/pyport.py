"""Translate lifted pseudocode of simple numeric C# methods (WKDColor.cheatRGB_*) into Python.
Usage: pyport.py lifted.txt ClassName out.py
"""
import re, sys

src = open(sys.argv[1]).read()
cls = sys.argv[2]
out = open(sys.argv[3], "w")

methods = []
for blk in src.split("\n### "):
    blk = blk.lstrip("# ")
    head, _, body = blk.partition("\n")
    if "::" not in head: continue
    name = head.split("::")[-1].strip()
    if not name.startswith("cheatRGB_"): continue
    stmts = []
    for l in body.split("\n"):
        m = re.match(r"\s+([0-9A-F]{5}): (.*)$", l)
        if m: stmts.append((int(m.group(1), 16), m.group(2)))
    methods.append((name, stmts))

def expr(e):
    e = e.replace("&v", "v").replace("*&v", "v")
    e = re.sub(r"\bWKDColor\.m_LED_Vender\b", "_S['vendor']", e)
    e = re.sub(r"Convert\.\w+\(", "(", e)
    e = e.replace(" / ", " // ")
    e = re.sub(r"!(?=[\w(])", "not ", e)
    e = e.replace("not =", "!=")
    return e

out.write("# Generated from GCUService LightingModel.WKDColor (colour correction per LED vendor)\n")
out.write("# Do not edit by hand.\n\n")
out.write("class RGB:\n    __slots__=('R','G','B')\n    def __init__(s,R=0,G=0,B=0): s.R=R; s.G=G; s.B=B\n")
out.write("    def __setattr__(s,k,v): object.__setattr__(s,k,int(v)&0xFF)\n    def t(s): return (s.R,s.G,s.B)\n\n")
out.write("_S={'vendor':4}\n\ndef set_vendor(v):\n    _S['vendor']=v\n\n")

for name, stmts in methods:
    offs = [o for o, _ in stmts]
    def target(t):
        for i, o in enumerate(offs):
            if o >= t: return i
        return len(offs)
    nargs = 0
    for _, s in stmts:
        for a in re.findall(r"arg(\d)", s): nargs = max(nargs, int(a) + 1)
    args = ", ".join(f"arg{i}" for i in range(nargs))
    out.write(f"def {name}({args}):\n    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()\n    pc=0\n    while True:\n")
    for i, (o, s) in enumerate(stmts):
        nxt = i + 1
        out.write(f"        if pc=={i}:  # {o:05X}: {s}\n")
        m = re.match(r"if \((.*)\) goto ([0-9A-F]+)$", s)
        if m:
            out.write(f"            pc = {target(int(m.group(2),16))} if ({expr(m.group(1))}) else {nxt}\n            continue\n")
            continue
        m = re.match(r"goto ([0-9A-F]+)$", s)
        if m:
            out.write(f"            pc = {target(int(m.group(1),16))}\n            continue\n"); continue
        if s.startswith("return"):
            r = s[6:].strip()
            rv = (expr(r) + '.t()') if re.fullmatch(r'v[0-9]', r) else (expr(r) or 'None')
            out.write("            return " + rv + "\n"); continue
        m = re.match(r"\*&(v\d) = default$", s)
        if m:
            out.write(f"            {m.group(1)}=RGB(); pc={nxt}; continue\n"); continue
        m = re.match(r"(.+?) = (.+)$", s)
        if m:
            out.write(f"            {expr(m.group(1))} = {expr(m.group(2))}; pc={nxt}; continue\n"); continue
        raise SystemExit(f"untranslated in {name}: {s}")
    out.write(f"        if pc>={len(stmts)}: return v0.t()\n\n")
print("ported", [m[0] for m in methods])
