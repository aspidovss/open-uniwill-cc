import sys  # deps: pip install dnfile dncil "pefile==2023.2.7"
import dnfile
pe=dnfile.dnPE(sys.argv[1]); md=pe.net.mdtables
ET={0x02:'bool',0x03:'char',0x04:'i8',0x05:'u8',0x06:'i16',0x07:'u16',0x08:'i32',0x09:'u32',0x0a:'i64',0x0b:'u64',0x0c:'f32',0x0d:'f64',0x0e:'string',0x1d:'arr',0x11:'valuetype',0x12:'class'}
marsh={}
if md.FieldMarshal:
    for fm in md.FieldMarshal.rows:
        try: marsh[id(fm.Parent.row)]=bytes(fm.NativeType.value if hasattr(fm.NativeType,'value') else fm.NativeType).hex()
        except Exception as e: pass
lay={}
if md.ClassLayout:
    for cl in md.ClassLayout.rows: lay[id(cl.Parent.row)]=(cl.PackingSize,cl.ClassSize)
foff={}
if md.FieldLayout:
    for fl in md.FieldLayout.rows: foff[id(fl.Field.row)]=fl.Offset
for t in md.TypeDef.rows:
    if str(t.TypeName)==sys.argv[2]:
        print(t.TypeNamespace, t.TypeName, 'layout', lay.get(id(t)), 'flags', t.Flags)
        for f in t.FieldList:
            r=f.row; sig=bytes(r.Signature.value if hasattr(r.Signature,'value') else r.Signature)
            if r.Flags.fdStatic: continue
            et=sig[1]
            print('  ',r.Name, ET.get(et,hex(et)), sig.hex(), 'marshal',marsh.get(id(r)), 'off',foff.get(id(r)))
