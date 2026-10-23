import sys  # deps: pip install dnfile dncil "pefile==2023.2.7"
import re, dnfile
from dnfile.enums import MetadataTables
from dncil.cil.body import CilMethodBody
from dncil.clr.token import Token, StringToken
from dncil.cil.body.reader import CilMethodBodyReaderBase

TBL = {t.value: t.name for t in MetadataTables}

class R(CilMethodBodyReaderBase):
    def __init__(s, pe, row): s.pe = pe; s.offset = pe.get_offset_from_rva(row.Rva)
    def read(s, n):
        d = s.pe.__data__[s.offset:s.offset + n]; s.offset += n; return bytes(d)
    def tell(s): return s.offset
    def seek(s, o): s.offset = o; return o

def cint(b, i):
    x = b[i]
    if x & 0x80 == 0: return x, i + 1
    if x & 0xC0 == 0x80: return ((x & 0x3F) << 8) | b[i + 1], i + 2
    return ((x & 0x1F) << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3], i + 4

def sig_info(blob):
    """returns (hasthis, nparams, retvoid)"""
    try:
        b = bytes(blob)
        cc = b[0]; i = 1
        if cc & 0x10: _, i = cint(b, i)  # generic param count
        n, i = cint(b, i)
        ret = b[i]
        return bool(cc & 0x20), n, ret == 0x01
    except Exception:
        return False, 0, False

class Lifter:
    def __init__(self, path):
        self.pe = pe = dnfile.dnPE(path)
        self.md = md = pe.net.mdtables
        self.owner, self.fowner = {}, {}
        enc = {}
        if md.NestedClass:
            for nc in md.NestedClass.rows:
                enc[id(nc.NestedClass.row)] = nc.EnclosingClass.row
        def fulln(t):
            n = (str(t.TypeNamespace) + "." if str(t.TypeNamespace) else "") + str(t.TypeName)
            e = enc.get(id(t))
            return (fulln(e) + "/" + n) if e is not None else n
        for t in md.TypeDef.rows:
            full = fulln(t)
            for m in t.MethodList: self.owner[id(m.row)] = full
            for f in t.FieldList: self.fowner[id(f.row)] = full

    def tname(self, r):
        if isinstance(r, (dnfile.mdtable.TypeRefRow, dnfile.mdtable.TypeDefRow)):
            return str(r.TypeName)
        if isinstance(r, dnfile.mdtable.TypeSpecRow): return "TSpec"
        if isinstance(r, dnfile.mdtable.MethodDefRow): return self.owner.get(id(r), "?").split(".")[-1]
        return "?"

    def row(self, tok):
        tab = getattr(self.md, TBL.get(tok.table, ""), None)
        return tab.rows[tok.rid - 1]

    def method_ref(self, tok):
        r = self.row(tok)
        if isinstance(r, dnfile.mdtable.MethodSpecRow): r = r.Method.row
        if isinstance(r, dnfile.mdtable.MemberRefRow):
            name = f"{self.tname(r.Class.row)}.{r.Name}"
            hasthis, n, void = sig_info(r.Signature.value if hasattr(r.Signature, 'value') else r.Signature)
        else:
            name = f"{self.owner.get(id(r), '?').split('.')[-1]}.{r.Name}"
            hasthis, n, void = sig_info(r.Signature.value if hasattr(r.Signature, 'value') else r.Signature)
            if r.Flags.mdStatic: hasthis = False
            else: hasthis = True
        return name, hasthis, n, void

    def field(self, tok):
        r = self.row(tok)
        if isinstance(r, dnfile.mdtable.MemberRefRow): return f"{self.tname(r.Class.row)}.{r.Name}"
        return f"{self.fowner.get(id(r), '?').split('.')[-1]}.{r.Name}"

    def operand_s(self, op):
        if isinstance(op, StringToken):
            try:
                us = self.pe.net.user_strings.get(op.rid); return repr(us.value)
            except Exception: return '"?"'
        if isinstance(op, Token):
            try:
                r = self.row(op)
                if isinstance(r, (dnfile.mdtable.TypeRefRow, dnfile.mdtable.TypeDefRow, dnfile.mdtable.TypeSpecRow)): return self.tname(r)
                if isinstance(r, dnfile.mdtable.FieldRow): return self.field(op)
                if isinstance(r, dnfile.mdtable.MemberRefRow): return self.tname(r.Class.row) + "." + str(r.Name)
                if isinstance(r, dnfile.mdtable.MethodDefRow): return self.owner.get(id(r), "?").split('.')[-1] + "." + str(r.Name)
            except Exception: pass
            return f"tok{op.value:x}"
        if isinstance(op, int): return hex(op) if abs(op) > 9 else str(op)
        return str(op)

    def lift(self, row):
        body = CilMethodBody(R(self.pe, row))
        st = []; out = []
        BIN = {"add": "+", "sub": "-", "mul": "*", "div": "/", "rem": "%", "and": "&", "or": "|", "xor": "^",
               "shl": "<<", "shr": ">>", "shr.un": ">>", "ceq": "==", "cgt": ">", "clt": "<", "cgt.un": ">", "clt.un": "<",
               "div.un": "/", "rem.un": "%", "add.ovf": "+", "mul.ovf": "*", "sub.ovf": "-"}
        CB = {"beq": "==", "bne.un": "!=", "bge": ">=", "bgt": ">", "ble": "<=", "blt": "<", "bge.un": ">=", "bgt.un": ">", "ble.un": "<=", "blt.un": "<"}
        def pop():
            return st.pop() if st else "<?>"
        def emit(off, s): out.append(f"  {off:05X}: {s}")
        tmp = [0]
        for ins in body.instructions:
            o = str(ins.opcode); a = ins.operand; off = ins.offset
            base = o.replace(".s", "") if o.endswith(".s") and not o.startswith("ldc") else o
            try:
                if o.startswith("ldarg"):
                    if "." in o and o.split(".")[1].isdigit(): idx = int(o.split(".")[1])
                    else: idx = a if isinstance(a, int) else getattr(a, 'index', a)
                    st.append("&arg" + str(idx) if o.startswith("ldarga") else ("this" if str(idx) == "0" and not row.Flags.mdStatic else f"arg{idx}"))
                elif o.startswith("ldloc"):
                    idx = o.split(".")[1] if "." in o and o.split(".")[1].isdigit() else str(a).replace("local(", "").replace(")", "")
                    try: idx = str(int(idx, 0))
                    except Exception: pass
                    st.append(("&" if o.startswith("ldloca") else "") + "v" + idx)
                elif o.startswith("stloc"):
                    idx = o.split(".")[1] if "." in o and o.split(".")[1].isdigit() else str(a).replace("local(", "").replace(")", "")
                    try: idx = str(int(idx, 0))
                    except Exception: pass
                    emit(off, f"v{idx} = {pop()}")
                elif o.startswith("starg"):
                    emit(off, f"arg{a} = {pop()}")
                elif o.startswith("ldc.i4") or o.startswith("ldc.i8") or o.startswith("ldc.r"):
                    if o == "ldc.i4.m1": st.append("-1")
                    elif a is None: st.append(o.split(".")[-1])
                    else: st.append(self.operand_s(a))
                elif o == "ldstr": st.append(self.operand_s(a))
                elif o == "ldnull": st.append("null")
                elif o in ("ldfld", "ldflda"):
                    obj = pop(); st.append(f"{obj}.{self.field(a).split('.')[-1]}")
                elif o in ("ldsfld", "ldsflda"): st.append(self.field(a))
                elif o == "stfld":
                    v = pop(); obj = pop(); emit(off, f"{obj}.{self.field(a).split('.')[-1]} = {v}")
                elif o == "stsfld": emit(off, f"{self.field(a)} = {pop()}")
                elif o in ("call", "callvirt", "newobj"):
                    name, hasthis, n, void = self.method_ref(a)
                    args = [pop() for _ in range(n)][::-1]
                    if o == "newobj":
                        st.append(f"new {name.split('.')[0]}({', '.join(args)})"); continue
                    obj = pop() + "." if hasthis else ""
                    s = f"{obj}{name.split('.')[-1] if hasthis else name}({', '.join(args)})"
                    if s.startswith("LogCtrl.") or ".TraceMessage(" in s: continue
                    if void: emit(off, s)
                    else: st.append(s)
                elif o in BIN:
                    b = pop(); x = pop(); st.append(f"({x} {BIN[o]} {b})")
                elif o in ("neg", "not"): st.append(("-" if o == "neg" else "~") + pop())
                elif o.startswith("conv") or o in ("box", "unbox.any", "castclass", "nop", "volatile.", "readonly.", "constrained.", "unbox"):
                    if o == "castclass": st.append(f"({self.operand_s(a)}){pop()}")
                    else: pass
                elif o == "isinst": st.append(f"{pop()} as {self.operand_s(a)}")
                elif o == "dup": v = pop(); st.append(v); st.append(v)
                elif o == "pop":
                    v = pop()
                    if "(" in v: emit(off, v)
                elif o == "ret":
                    emit(off, f"return {pop()}" if st else "return")
                elif base in ("br", "leave"):
                    emit(off, f"goto {a:05X}" if isinstance(a, int) else f"goto {a}")
                elif base in ("brtrue", "brfalse", "brinst", "brnull", "brzero"):
                    c = pop(); neg = base in ("brfalse", "brnull", "brzero")
                    emit(off, f"if ({'!' if neg else ''}{c}) goto {a:05X}")
                elif base in CB:
                    b = pop(); x = pop(); emit(off, f"if ({x} {CB[base]} {b}) goto {a:05X}")
                elif o == "switch":
                    emit(off, f"switch ({pop()}) {a}")
                elif o == "newarr": st.append(f"new {self.operand_s(a)}[{pop()}]")
                elif o.startswith("ldelem"):
                    i = pop(); arr = pop(); st.append(f"{arr}[{i}]")
                elif o.startswith("stelem"):
                    v = pop(); i = pop(); arr = pop(); emit(off, f"{arr}[{i}] = {v}")
                elif o == "ldlen": st.append(f"{pop()}.Length")
                elif o == "ldtoken": st.append(self.operand_s(a))
                elif o in ("ldftn", "ldvirtftn"):
                    if o == "ldvirtftn": pop()
                    st.append("&" + self.operand_s(a))
                elif o.startswith("ldind"): st.append("*" + pop())
                elif o.startswith("stind"): v = pop(); p = pop(); emit(off, f"*{p} = {v}")
                elif o in ("throw", "rethrow"): emit(off, "throw " + (pop() if o == "throw" else ""))
                elif o in ("endfinally", "endfilter"): emit(off, o); st.clear()
                elif o == "initobj": emit(off, f"*{pop()} = default")
                elif o == "sizeof": st.append(f"sizeof({self.operand_s(a)})")
                else: emit(off, f"<{o} {self.operand_s(a) if a is not None else ''}>")
            except Exception as e:
                emit(off, f"<err {o}: {e}>")
        return out

    def dump(self, pattern, f=sys.stdout):
        rx = re.compile(pattern)
        for row in self.md.MethodDef.rows:
            full = f"{self.owner.get(id(row), '?')}::{row.Name}"
            if not rx.search(full): continue
            if not row.Rva or row.Flags.mdAbstract:
                continue
            f.write(f"\n### {full}\n")
            try:
                for l in self.lift(row): f.write(l + "\n")
            except Exception as e:
                f.write(f"  <lift error {e}>\n")

if __name__ == "__main__":
    L = Lifter(sys.argv[1])
    L.dump(sys.argv[2] if len(sys.argv) > 2 else ".")
