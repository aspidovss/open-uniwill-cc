import sys  # deps: pip install dnfile dncil "pefile==2023.2.7"
import dnfile, struct
pe=dnfile.dnPE(sys.argv[1]); md=pe.net.mdtables
const={}
for c in md.Constant.rows:
    try:
        p=c.Parent.row; v=bytes(c.Value.value if hasattr(c.Value,'value') else c.Value)
        n={1:'<b',2:'<h',4:'<i',8:'<q'}.get(len(v))
        const[id(p)]=struct.unpack(n,v)[0] if n else v
    except Exception: pass
want=sys.argv[2:]
for t in md.TypeDef.rows:
    if str(t.TypeName) in want:
        print('enum',t.TypeNamespace,t.TypeName)
        for f in t.FieldList:
            r=f.row
            if id(r) in const: print('  ',r.Name,'=',hex(const[id(r)]))
