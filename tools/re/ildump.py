import sys  # deps: pip install dnfile dncil "pefile==2023.2.7"
import sys, dnfile
from dnfile.enums import MetadataTables
from dncil.cil.body import CilMethodBody
from dncil.cil.error import MethodBodyFormatError
from dncil.clr.token import Token, StringToken, InvalidToken
from dncil.cil.body.reader import CilMethodBodyReaderBase

TBL = {t.value: t.name for t in MetadataTables}

class R(CilMethodBodyReaderBase):
    def __init__(s, pe, row): s.pe = pe; s.offset = pe.get_offset_from_rva(row.Rva)
    def read(s, n):
        d = s.pe.__data__[s.offset:s.offset + n]; s.offset += n; return bytes(d)
    def tell(s): return s.offset
    def seek(s, o): s.offset = o; return o

def main(path, out):
    pe = dnfile.dnPE(path)
    md = pe.net.mdtables
    # map methoddef index -> owning type, fielddef idx -> type
    owner, fowner = {}, {}
    types = list(md.TypeDef.rows) if md.TypeDef else []
    for t in types:
        full = (str(t.TypeNamespace) + "." if str(t.TypeNamespace) else "") + str(t.TypeName)
        for m in t.MethodList: owner[id(m.row)] = full
        for f in t.FieldList: fowner[id(f.row)] = full

    def tname(r):
        if r is None: return "?"
        if isinstance(r, (dnfile.mdtable.TypeRefRow, dnfile.mdtable.TypeDefRow)):
            ns = str(r.TypeNamespace); return (ns + "." if ns else "") + str(r.TypeName)
        if isinstance(r, dnfile.mdtable.TypeSpecRow): return "TypeSpec"
        if isinstance(r, dnfile.mdtable.MethodDefRow): return owner.get(id(r), "?")
        return type(r).__name__

    def fmt(op):
        if isinstance(op, StringToken):
            try:
                us = pe.net.user_strings.get(op.rid)
                return repr(us.value) if us is not None and not isinstance(us, bytes) else "<str?>"
            except Exception: return "<str?>"
        if isinstance(op, Token):
            tn = TBL.get(op.table, ""); tab = getattr(md, tn, None)
            try: r = tab.rows[op.rid - 1]
            except Exception: return f"tok_{op.value:08x}"
            if isinstance(r, dnfile.mdtable.MemberRefRow):
                return f"{tname(r.Class.row)}::{r.Name}"
            if isinstance(r, dnfile.mdtable.MethodDefRow):
                return f"{owner.get(id(r),'?')}::{r.Name}"
            if isinstance(r, dnfile.mdtable.FieldRow):
                return f"{fowner.get(id(r),'?')}::{r.Name}"
            if isinstance(r, dnfile.mdtable.MethodSpecRow):
                try:
                    m = r.Method.row
                    if isinstance(m, dnfile.mdtable.MemberRefRow): return f"{tname(m.Class.row)}::{m.Name}<>"
                    return f"{owner.get(id(m),'?')}::{m.Name}<>"
                except Exception: return "MethodSpec"
            return tname(r)
        if isinstance(op, int): return str(op) if -1000 < op < 1000 else hex(op)
        if op is None: return ""
        return str(op)

    with open(out, "w") as f:
        for row in md.MethodDef.rows:
            if not row.ImplFlags.miIL or row.Flags.mdAbstract or row.Flags.mdPinvokeImpl or not row.Rva:
                if row.Flags.mdPinvokeImpl:
                    f.write(f"\n### PINVOKE {owner.get(id(row),'?')}::{row.Name}\n")
                continue
            try: body = CilMethodBody(R(pe, row))
            except Exception as e:
                f.write(f"\n### {owner.get(id(row),'?')}::{row.Name}  <err {e}>\n"); continue
            f.write(f"\n### {owner.get(id(row),'?')}::{row.Name}\n")
            for i in body.instructions:
                f.write(f"  {i.offset:04X} {str(i.opcode):<12} {fmt(i.operand)}\n")
        # pinvoke map
        if md.ImplMap:
            f.write("\n\n### IMPLMAP\n")
            for im in md.ImplMap.rows:
                try: f.write(f"  {im.ImportName} <- {im.ImportScope.row.Name}\n")
                except Exception: pass

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
