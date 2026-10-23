# Generated from GCUService LightingModel.WKDColor (colour correction per LED vendor)
# Do not edit by hand.

class RGB:
    __slots__=('R','G','B')
    def __init__(s,R=0,G=0,B=0): s.R=R; s.G=G; s.B=B
    def __setattr__(s,k,v): object.__setattr__(s,k,int(v)&0xFF)
    def t(s): return (s.R,s.G,s.B)

_S={'vendor':4}

def set_vendor(v):
    _S['vendor']=v

def cheatRGB_2ndME(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 20C2E: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 20C39: if (WKDColor.m_LED_Vender) goto 20E3C
            pc = 65 if (_S['vendor']) else 2
            continue
        if pc==2:  # 20C44: if (arg0 != 0xff) goto 20C7C
            pc = 9 if (arg0 != 0xff) else 3
            continue
        if pc==3:  # 20C4C: if (arg1 != 0xff) goto 20C7C
            pc = 9 if (arg1 != 0xff) else 4
            continue
        if pc==4:  # 20C54: if (arg2 != 0xff) goto 20C7C
            pc = 9 if (arg2 != 0xff) else 5
            continue
        if pc==5:  # 20C5D: &v0.R = 0xff
            v0.R = 0xff; pc=6; continue
        if pc==6:  # 20C66: &v0.G = 0x32
            v0.G = 0x32; pc=7; continue
        if pc==7:  # 20C72: &v0.B = 0xaa
            v0.B = 0xaa; pc=8; continue
        if pc==8:  # 20C77: goto 215C8
            pc = 300
            continue
        if pc==9:  # 20C82: if (arg0 != 0xff) goto 20CB1
            pc = 16 if (arg0 != 0xff) else 10
            continue
        if pc==10:  # 20C8A: if (arg1 != 0xa5) goto 20CB1
            pc = 16 if (arg1 != 0xa5) else 11
            continue
        if pc==11:  # 20C8D: if (arg2) goto 20CB1
            pc = 16 if (arg2) else 12
            continue
        if pc==12:  # 20C96: &v0.R = 0xff
            v0.R = 0xff; pc=13; continue
        if pc==13:  # 20C9F: &v0.G = 0x13
            v0.G = 0x13; pc=14; continue
        if pc==14:  # 20CA7: &v0.B = 0
            v0.B = 0; pc=15; continue
        if pc==15:  # 20CAC: goto 215C8
            pc = 300
            continue
        if pc==16:  # 20CB7: if (arg0 != 0xff) goto 20CE6
            pc = 23 if (arg0 != 0xff) else 17
            continue
        if pc==17:  # 20CBF: if (arg1 != 0xff) goto 20CE6
            pc = 23 if (arg1 != 0xff) else 18
            continue
        if pc==18:  # 20CC2: if (arg2) goto 20CE6
            pc = 23 if (arg2) else 19
            continue
        if pc==19:  # 20CCB: &v0.R = 0xff
            v0.R = 0xff; pc=20; continue
        if pc==20:  # 20CD4: &v0.G = 0x32
            v0.G = 0x32; pc=21; continue
        if pc==21:  # 20CDC: &v0.B = 0
            v0.B = 0; pc=22; continue
        if pc==22:  # 20CE1: goto 215C8
            pc = 300
            continue
        if pc==23:  # 20CE7: if (arg0) goto 20D1B
            pc = 30 if (arg0) else 24
            continue
        if pc==24:  # 20CEF: if (arg1 != 0xff) goto 20D1B
            pc = 30 if (arg1 != 0xff) else 25
            continue
        if pc==25:  # 20CF7: if (arg2 != 0xff) goto 20D1B
            pc = 30 if (arg2 != 0xff) else 26
            continue
        if pc==26:  # 20CFC: &v0.R = 0
            v0.R = 0; pc=27; continue
        if pc==27:  # 20D05: &v0.G = 0x32
            v0.G = 0x32; pc=28; continue
        if pc==28:  # 20D11: &v0.B = 0xaa
            v0.B = 0xaa; pc=29; continue
        if pc==29:  # 20D16: goto 215C8
            pc = 300
            continue
        if pc==30:  # 20D21: if (arg0 != 0x8b) goto 20D53
            pc = 37 if (arg0 != 0x8b) else 31
            continue
        if pc==31:  # 20D24: if (arg1) goto 20D53
            pc = 37 if (arg1) else 32
            continue
        if pc==32:  # 20D2C: if (arg2 != 0xff) goto 20D53
            pc = 37 if (arg2 != 0xff) else 33
            continue
        if pc==33:  # 20D35: &v0.R = 0x8a
            v0.R = 0x8a; pc=34; continue
        if pc==34:  # 20D3D: &v0.G = 0
            v0.G = 0; pc=35; continue
        if pc==35:  # 20D49: &v0.B = 0xaa
            v0.B = 0xaa; pc=36; continue
        if pc==36:  # 20D4E: goto 215C8
            pc = 300
            continue
        if pc==37:  # 20D59: if (arg0 <= 0xf9) goto 20DAF
            pc = 49 if (arg0 <= 0xf9) else 38
            continue
        if pc==38:  # 20D5E: if (arg1 >= 0x14) goto 20DAF
            pc = 49 if (arg1 >= 0x14) else 39
            continue
        if pc==39:  # 20D66: if (arg2 >= 0x80) goto 20DAF
            pc = 49 if (arg2 >= 0x80) else 40
            continue
        if pc==40:  # 20D6B: if (arg2 >= 0x64) goto 20D8E
            pc = 45 if (arg2 >= 0x64) else 41
            continue
        if pc==41:  # 20D70: &v0.R = arg0
            v0.R = arg0; pc=42; continue
        if pc==42:  # 20D78: &v0.G = arg1
            v0.G = arg1; pc=43; continue
        if pc==43:  # 20D84: &v0.B = (arg2 / 0xa)
            v0.B = (arg2 // 0xa); pc=44; continue
        if pc==44:  # 20D89: goto 215C8
            pc = 300
            continue
        if pc==45:  # 20D91: &v0.R = arg0
            v0.R = arg0; pc=46; continue
        if pc==46:  # 20D99: &v0.G = arg1
            v0.G = arg1; pc=47; continue
        if pc==47:  # 20DA5: &v0.B = (arg2 - 0xa)
            v0.B = (arg2 - 0xa); pc=48; continue
        if pc==48:  # 20DAA: goto 215C8
            pc = 300
            continue
        if pc==49:  # 20DB2: if (arg0 >= 0x14) goto 20DE2
            pc = 55 if (arg0 >= 0x14) else 50
            continue
        if pc==50:  # 20DB6: if (arg2 >= arg1) goto 20DE2
            pc = 55 if (arg2 >= arg1) else 51
            continue
        if pc==51:  # 20DBB: &v0.R = arg0
            v0.R = arg0; pc=52; continue
        if pc==52:  # 20DC3: &v0.G = arg1
            v0.G = arg1; pc=53; continue
        if pc==53:  # 20DD8: &v0.B = ((0xaa * arg2) / 0xff)
            v0.B = ((0xaa * arg2) // 0xff); pc=54; continue
        if pc==54:  # 20DDD: goto 215C8
            pc = 300
            continue
        if pc==55:  # 20DE5: if (arg1 >= 0x14) goto 20E08
            pc = 61 if (arg1 >= 0x14) else 56
            continue
        if pc==56:  # 20DE9: if (arg0 >= arg2) goto 20E08
            pc = 61 if (arg0 >= arg2) else 57
            continue
        if pc==57:  # 20DEE: &v0.R = arg0
            v0.R = arg0; pc=58; continue
        if pc==58:  # 20DF6: &v0.G = arg1
            v0.G = arg1; pc=59; continue
        if pc==59:  # 20DFE: &v0.B = arg2
            v0.B = arg2; pc=60; continue
        if pc==60:  # 20E03: goto 215C8
            pc = 300
            continue
        if pc==61:  # 20E0B: &v0.R = arg0
            v0.R = arg0; pc=62; continue
        if pc==62:  # 20E1D: &v0.G = ((0x32 * arg1) / 0xff)
            v0.G = ((0x32 * arg1) // 0xff); pc=63; continue
        if pc==63:  # 20E32: &v0.B = ((0xaa * arg2) / 0xff)
            v0.B = ((0xaa * arg2) // 0xff); pc=64; continue
        if pc==64:  # 20E37: goto 215C8
            pc = 300
            continue
        if pc==65:  # 20E42: if (WKDColor.m_LED_Vender != 1) goto 210A0
            pc = 143 if (_S['vendor'] != 1) else 66
            continue
        if pc==66:  # 20E4D: if (arg0 != 0xff) goto 20E82
            pc = 73 if (arg0 != 0xff) else 67
            continue
        if pc==67:  # 20E55: if (arg1 != 0xff) goto 20E82
            pc = 73 if (arg1 != 0xff) else 68
            continue
        if pc==68:  # 20E5D: if (arg2 != 0xff) goto 20E82
            pc = 73 if (arg2 != 0xff) else 69
            continue
        if pc==69:  # 20E66: &v0.R = 0xff
            v0.R = 0xff; pc=70; continue
        if pc==70:  # 20E6F: &v0.G = 0x6e
            v0.G = 0x6e; pc=71; continue
        if pc==71:  # 20E78: &v0.B = 0x78
            v0.B = 0x78; pc=72; continue
        if pc==72:  # 20E7D: goto 215C8
            pc = 300
            continue
        if pc==73:  # 20E88: if (arg0 != 0xff) goto 20EB7
            pc = 80 if (arg0 != 0xff) else 74
            continue
        if pc==74:  # 20E90: if (arg1 != 0xa5) goto 20EB7
            pc = 80 if (arg1 != 0xa5) else 75
            continue
        if pc==75:  # 20E93: if (arg2) goto 20EB7
            pc = 80 if (arg2) else 76
            continue
        if pc==76:  # 20E9C: &v0.R = 0xff
            v0.R = 0xff; pc=77; continue
        if pc==77:  # 20EA5: &v0.G = 0x1e
            v0.G = 0x1e; pc=78; continue
        if pc==78:  # 20EAD: &v0.B = 0
            v0.B = 0; pc=79; continue
        if pc==79:  # 20EB2: goto 215C8
            pc = 300
            continue
        if pc==80:  # 20EBD: if (arg0 != 0xf1) goto 20EEA
            pc = 87 if (arg0 != 0xf1) else 81
            continue
        if pc==81:  # 20EC2: if (arg1 != 0x5a) goto 20EEA
            pc = 87 if (arg1 != 0x5a) else 82
            continue
        if pc==82:  # 20EC7: if (arg2 != 0x24) goto 20EEA
            pc = 87 if (arg2 != 0x24) else 83
            continue
        if pc==83:  # 20ED0: &v0.R = 0xff
            v0.R = 0xff; pc=84; continue
        if pc==84:  # 20ED8: &v0.G = 5
            v0.G = 5; pc=85; continue
        if pc==85:  # 20EE0: &v0.B = 0
            v0.B = 0; pc=86; continue
        if pc==86:  # 20EE5: goto 215C8
            pc = 300
            continue
        if pc==87:  # 20EF0: if (arg0 != 0xf7) goto 20F21
            pc = 94 if (arg0 != 0xf7) else 88
            continue
        if pc==88:  # 20EF8: if (arg1 != 0x93) goto 20F21
            pc = 94 if (arg1 != 0x93) else 89
            continue
        if pc==89:  # 20EFD: if (arg2 != 0x1e) goto 20F21
            pc = 94 if (arg2 != 0x1e) else 90
            continue
        if pc==90:  # 20F06: &v0.R = 0xff
            v0.R = 0xff; pc=91; continue
        if pc==91:  # 20F0F: &v0.G = 0xf
            v0.G = 0xf; pc=92; continue
        if pc==92:  # 20F17: &v0.B = 0
            v0.B = 0; pc=93; continue
        if pc==93:  # 20F1C: goto 215C8
            pc = 300
            continue
        if pc==94:  # 20F27: if (arg0 != 0xff) goto 20F56
            pc = 101 if (arg0 != 0xff) else 95
            continue
        if pc==95:  # 20F2F: if (arg1 != 0xff) goto 20F56
            pc = 101 if (arg1 != 0xff) else 96
            continue
        if pc==96:  # 20F32: if (arg2) goto 20F56
            pc = 101 if (arg2) else 97
            continue
        if pc==97:  # 20F3B: &v0.R = 0xff
            v0.R = 0xff; pc=98; continue
        if pc==98:  # 20F44: &v0.G = 0x32
            v0.G = 0x32; pc=99; continue
        if pc==99:  # 20F4C: &v0.B = 0
            v0.B = 0; pc=100; continue
        if pc==100:  # 20F51: goto 215C8
            pc = 300
            continue
        if pc==101:  # 20F57: if (arg0) goto 20F88
            pc = 108 if (arg0) else 102
            continue
        if pc==102:  # 20F5F: if (arg1 != 0xff) goto 20F88
            pc = 108 if (arg1 != 0xff) else 103
            continue
        if pc==103:  # 20F67: if (arg2 != 0xff) goto 20F88
            pc = 108 if (arg2 != 0xff) else 104
            continue
        if pc==104:  # 20F6C: &v0.R = 0
            v0.R = 0; pc=105; continue
        if pc==105:  # 20F75: &v0.G = 0x6e
            v0.G = 0x6e; pc=106; continue
        if pc==106:  # 20F7E: &v0.B = 0x78
            v0.B = 0x78; pc=107; continue
        if pc==107:  # 20F83: goto 215C8
            pc = 300
            continue
        if pc==108:  # 20F8E: if (arg0 != 0x8b) goto 20FBD
            pc = 115 if (arg0 != 0x8b) else 109
            continue
        if pc==109:  # 20F91: if (arg1) goto 20FBD
            pc = 115 if (arg1) else 110
            continue
        if pc==110:  # 20F99: if (arg2 != 0xff) goto 20FBD
            pc = 115 if (arg2 != 0xff) else 111
            continue
        if pc==111:  # 20FA2: &v0.R = 0xff
            v0.R = 0xff; pc=112; continue
        if pc==112:  # 20FAA: &v0.G = 0
            v0.G = 0; pc=113; continue
        if pc==113:  # 20FB3: &v0.B = 0x78
            v0.B = 0x78; pc=114; continue
        if pc==114:  # 20FB8: goto 215C8
            pc = 300
            continue
        if pc==115:  # 20FC3: if (arg0 <= 0xf9) goto 21019
            pc = 127 if (arg0 <= 0xf9) else 116
            continue
        if pc==116:  # 20FC8: if (arg1 >= 0x14) goto 21019
            pc = 127 if (arg1 >= 0x14) else 117
            continue
        if pc==117:  # 20FD0: if (arg2 >= 0x80) goto 21019
            pc = 127 if (arg2 >= 0x80) else 118
            continue
        if pc==118:  # 20FD5: if (arg2 >= 0x64) goto 20FF8
            pc = 123 if (arg2 >= 0x64) else 119
            continue
        if pc==119:  # 20FDA: &v0.R = arg0
            v0.R = arg0; pc=120; continue
        if pc==120:  # 20FE2: &v0.G = arg1
            v0.G = arg1; pc=121; continue
        if pc==121:  # 20FEE: &v0.B = (arg2 / 0xa)
            v0.B = (arg2 // 0xa); pc=122; continue
        if pc==122:  # 20FF3: goto 215C8
            pc = 300
            continue
        if pc==123:  # 20FFB: &v0.R = arg0
            v0.R = arg0; pc=124; continue
        if pc==124:  # 21003: &v0.G = arg1
            v0.G = arg1; pc=125; continue
        if pc==125:  # 2100F: &v0.B = (arg2 - 0xa)
            v0.B = (arg2 - 0xa); pc=126; continue
        if pc==126:  # 21014: goto 215C8
            pc = 300
            continue
        if pc==127:  # 2101C: if (arg0 >= 0x14) goto 21049
            pc = 133 if (arg0 >= 0x14) else 128
            continue
        if pc==128:  # 21020: if (arg2 >= arg1) goto 21049
            pc = 133 if (arg2 >= arg1) else 129
            continue
        if pc==129:  # 21025: &v0.R = arg0
            v0.R = arg0; pc=130; continue
        if pc==130:  # 2102D: &v0.G = arg1
            v0.G = arg1; pc=131; continue
        if pc==131:  # 2103F: &v0.B = ((0x50 * arg2) / 0xff)
            v0.B = ((0x50 * arg2) // 0xff); pc=132; continue
        if pc==132:  # 21044: goto 215C8
            pc = 300
            continue
        if pc==133:  # 2104C: if (arg1 >= 0x14) goto 2106F
            pc = 139 if (arg1 >= 0x14) else 134
            continue
        if pc==134:  # 21050: if (arg0 >= arg2) goto 2106F
            pc = 139 if (arg0 >= arg2) else 135
            continue
        if pc==135:  # 21055: &v0.R = arg0
            v0.R = arg0; pc=136; continue
        if pc==136:  # 2105D: &v0.G = arg1
            v0.G = arg1; pc=137; continue
        if pc==137:  # 21065: &v0.B = arg2
            v0.B = arg2; pc=138; continue
        if pc==138:  # 2106A: goto 215C8
            pc = 300
            continue
        if pc==139:  # 21072: &v0.R = arg0
            v0.R = arg0; pc=140; continue
        if pc==140:  # 21084: &v0.G = ((0x6e * arg1) / 0xff)
            v0.G = ((0x6e * arg1) // 0xff); pc=141; continue
        if pc==141:  # 21096: &v0.B = ((0x78 * arg2) / 0xff)
            v0.B = ((0x78 * arg2) // 0xff); pc=142; continue
        if pc==142:  # 2109B: goto 215C8
            pc = 300
            continue
        if pc==143:  # 210A6: if (WKDColor.m_LED_Vender == 2) goto 210B3
            pc = 145 if (_S['vendor'] == 2) else 144
            continue
        if pc==144:  # 210AE: if (WKDColor.m_LED_Vender != 3) goto 211FD
            pc = 184 if (_S['vendor'] != 3) else 145
            continue
        if pc==145:  # 210B9: if (arg0 != 0xff) goto 210EE
            pc = 152 if (arg0 != 0xff) else 146
            continue
        if pc==146:  # 210C1: if (arg1 != 0xff) goto 210EE
            pc = 152 if (arg1 != 0xff) else 147
            continue
        if pc==147:  # 210C9: if (arg2 != 0xff) goto 210EE
            pc = 152 if (arg2 != 0xff) else 148
            continue
        if pc==148:  # 210D2: &v0.R = 0xdc
            v0.R = 0xdc; pc=149; continue
        if pc==149:  # 210DB: &v0.G = 0x78
            v0.G = 0x78; pc=150; continue
        if pc==150:  # 210E4: &v0.B = 0x6e
            v0.B = 0x6e; pc=151; continue
        if pc==151:  # 210E9: goto 215C8
            pc = 300
            continue
        if pc==152:  # 210F4: if (arg0 != 0xff) goto 21123
            pc = 159 if (arg0 != 0xff) else 153
            continue
        if pc==153:  # 210FC: if (arg1 != 0xa5) goto 21123
            pc = 159 if (arg1 != 0xa5) else 154
            continue
        if pc==154:  # 210FF: if (arg2) goto 21123
            pc = 159 if (arg2) else 155
            continue
        if pc==155:  # 21108: &v0.R = 0xdc
            v0.R = 0xdc; pc=156; continue
        if pc==156:  # 21111: &v0.G = 0x1e
            v0.G = 0x1e; pc=157; continue
        if pc==157:  # 21119: &v0.B = 0
            v0.B = 0; pc=158; continue
        if pc==158:  # 2111E: goto 215C8
            pc = 300
            continue
        if pc==159:  # 21129: if (arg0 != 0xff) goto 21158
            pc = 166 if (arg0 != 0xff) else 160
            continue
        if pc==160:  # 21131: if (arg1 != 0xff) goto 21158
            pc = 166 if (arg1 != 0xff) else 161
            continue
        if pc==161:  # 21134: if (arg2) goto 21158
            pc = 166 if (arg2) else 162
            continue
        if pc==162:  # 2113D: &v0.R = 0xdc
            v0.R = 0xdc; pc=163; continue
        if pc==163:  # 21146: &v0.G = 0x78
            v0.G = 0x78; pc=164; continue
        if pc==164:  # 2114E: &v0.B = 0
            v0.B = 0; pc=165; continue
        if pc==165:  # 21153: goto 215C8
            pc = 300
            continue
        if pc==166:  # 21159: if (arg0) goto 2118A
            pc = 173 if (arg0) else 167
            continue
        if pc==167:  # 21161: if (arg1 != 0xff) goto 2118A
            pc = 173 if (arg1 != 0xff) else 168
            continue
        if pc==168:  # 21169: if (arg2 != 0xff) goto 2118A
            pc = 173 if (arg2 != 0xff) else 169
            continue
        if pc==169:  # 2116E: &v0.R = 0
            v0.R = 0; pc=170; continue
        if pc==170:  # 21177: &v0.G = 0x78
            v0.G = 0x78; pc=171; continue
        if pc==171:  # 21180: &v0.B = 0x6e
            v0.B = 0x6e; pc=172; continue
        if pc==172:  # 21185: goto 215C8
            pc = 300
            continue
        if pc==173:  # 21190: if (arg0 != 0x8b) goto 211BF
            pc = 180 if (arg0 != 0x8b) else 174
            continue
        if pc==174:  # 21193: if (arg1) goto 211BF
            pc = 180 if (arg1) else 175
            continue
        if pc==175:  # 2119B: if (arg2 != 0xff) goto 211BF
            pc = 180 if (arg2 != 0xff) else 176
            continue
        if pc==176:  # 211A4: &v0.R = 0xdc
            v0.R = 0xdc; pc=177; continue
        if pc==177:  # 211AC: &v0.G = 0
            v0.G = 0; pc=178; continue
        if pc==178:  # 211B5: &v0.B = 0x6e
            v0.B = 0x6e; pc=179; continue
        if pc==179:  # 211BA: goto 215C8
            pc = 300
            continue
        if pc==180:  # 211CF: &v0.R = ((0xdc * arg0) / 0xff)
            v0.R = ((0xdc * arg0) // 0xff); pc=181; continue
        if pc==181:  # 211E1: &v0.G = ((0x78 * arg1) / 0xff)
            v0.G = ((0x78 * arg1) // 0xff); pc=182; continue
        if pc==182:  # 211F3: &v0.B = ((0x6e * arg2) / 0xff)
            v0.B = ((0x6e * arg2) // 0xff); pc=183; continue
        if pc==183:  # 211F8: goto 215C8
            pc = 300
            continue
        if pc==184:  # 21203: if (WKDColor.m_LED_Vender != 5) goto 2135E
            pc = 224 if (_S['vendor'] != 5) else 185
            continue
        if pc==185:  # 2120E: if (arg0 != 0xff) goto 21246
            pc = 192 if (arg0 != 0xff) else 186
            continue
        if pc==186:  # 21216: if (arg1 != 0xff) goto 21246
            pc = 192 if (arg1 != 0xff) else 187
            continue
        if pc==187:  # 2121E: if (arg2 != 0xff) goto 21246
            pc = 192 if (arg2 != 0xff) else 188
            continue
        if pc==188:  # 21227: &v0.R = 0xdc
            v0.R = 0xdc; pc=189; continue
        if pc==189:  # 21230: &v0.G = 0x5f
            v0.G = 0x5f; pc=190; continue
        if pc==190:  # 2123C: &v0.B = 0xa0
            v0.B = 0xa0; pc=191; continue
        if pc==191:  # 21241: goto 215C8
            pc = 300
            continue
        if pc==192:  # 2124C: if (arg0 != 0xff) goto 2127B
            pc = 199 if (arg0 != 0xff) else 193
            continue
        if pc==193:  # 21254: if (arg1 != 0xa5) goto 2127B
            pc = 199 if (arg1 != 0xa5) else 194
            continue
        if pc==194:  # 21257: if (arg2) goto 2127B
            pc = 199 if (arg2) else 195
            continue
        if pc==195:  # 21260: &v0.R = 0xfa
            v0.R = 0xfa; pc=196; continue
        if pc==196:  # 21269: &v0.G = 0x1e
            v0.G = 0x1e; pc=197; continue
        if pc==197:  # 21271: &v0.B = 0
            v0.B = 0; pc=198; continue
        if pc==198:  # 21276: goto 215C8
            pc = 300
            continue
        if pc==199:  # 21281: if (arg0 != 0xff) goto 212B0
            pc = 206 if (arg0 != 0xff) else 200
            continue
        if pc==200:  # 21289: if (arg1 != 0xff) goto 212B0
            pc = 206 if (arg1 != 0xff) else 201
            continue
        if pc==201:  # 2128C: if (arg2) goto 212B0
            pc = 206 if (arg2) else 202
            continue
        if pc==202:  # 21295: &v0.R = 0xdc
            v0.R = 0xdc; pc=203; continue
        if pc==203:  # 2129E: &v0.G = 0x5f
            v0.G = 0x5f; pc=204; continue
        if pc==204:  # 212A6: &v0.B = 0
            v0.B = 0; pc=205; continue
        if pc==205:  # 212AB: goto 215C8
            pc = 300
            continue
        if pc==206:  # 212B1: if (arg0) goto 212E5
            pc = 213 if (arg0) else 207
            continue
        if pc==207:  # 212B9: if (arg1 != 0xff) goto 212E5
            pc = 213 if (arg1 != 0xff) else 208
            continue
        if pc==208:  # 212C1: if (arg2 != 0xff) goto 212E5
            pc = 213 if (arg2 != 0xff) else 209
            continue
        if pc==209:  # 212C6: &v0.R = 0
            v0.R = 0; pc=210; continue
        if pc==210:  # 212CF: &v0.G = 0x5f
            v0.G = 0x5f; pc=211; continue
        if pc==211:  # 212DB: &v0.B = 0xa0
            v0.B = 0xa0; pc=212; continue
        if pc==212:  # 212E0: goto 215C8
            pc = 300
            continue
        if pc==213:  # 212EB: if (arg0 != 0x8b) goto 2131D
            pc = 220 if (arg0 != 0x8b) else 214
            continue
        if pc==214:  # 212EE: if (arg1) goto 2131D
            pc = 220 if (arg1) else 215
            continue
        if pc==215:  # 212F6: if (arg2 != 0xff) goto 2131D
            pc = 220 if (arg2 != 0xff) else 216
            continue
        if pc==216:  # 212FF: &v0.R = 0xdc
            v0.R = 0xdc; pc=217; continue
        if pc==217:  # 21307: &v0.G = 0
            v0.G = 0; pc=218; continue
        if pc==218:  # 21313: &v0.B = 0xa0
            v0.B = 0xa0; pc=219; continue
        if pc==219:  # 21318: goto 215C8
            pc = 300
            continue
        if pc==220:  # 2132D: &v0.R = ((0xdc * arg0) / 0xff)
            v0.R = ((0xdc * arg0) // 0xff); pc=221; continue
        if pc==221:  # 2133F: &v0.G = ((0x5f * arg1) / 0xff)
            v0.G = ((0x5f * arg1) // 0xff); pc=222; continue
        if pc==222:  # 21354: &v0.B = ((0xa0 * arg2) / 0xff)
            v0.B = ((0xa0 * arg2) // 0xff); pc=223; continue
        if pc==223:  # 21359: goto 215C8
            pc = 300
            continue
        if pc==224:  # 21364: if (arg0 != 0xff) goto 2139F
            pc = 231 if (arg0 != 0xff) else 225
            continue
        if pc==225:  # 2136C: if (arg1 != 0xff) goto 2139F
            pc = 231 if (arg1 != 0xff) else 226
            continue
        if pc==226:  # 21374: if (arg2 != 0xff) goto 2139F
            pc = 231 if (arg2 != 0xff) else 227
            continue
        if pc==227:  # 2137D: &v0.R = 0xff
            v0.R = 0xff; pc=228; continue
        if pc==228:  # 21389: &v0.G = 0xb4
            v0.G = 0xb4; pc=229; continue
        if pc==229:  # 21395: &v0.B = 0xc8
            v0.B = 0xc8; pc=230; continue
        if pc==230:  # 2139A: goto 215C8
            pc = 300
            continue
        if pc==231:  # 213A5: if (arg0 != 0xff) goto 213D4
            pc = 238 if (arg0 != 0xff) else 232
            continue
        if pc==232:  # 213AD: if (arg1 != 0xa5) goto 213D4
            pc = 238 if (arg1 != 0xa5) else 233
            continue
        if pc==233:  # 213B0: if (arg2) goto 213D4
            pc = 238 if (arg2) else 234
            continue
        if pc==234:  # 213B9: &v0.R = 0xff
            v0.R = 0xff; pc=235; continue
        if pc==235:  # 213C2: &v0.G = 0x2a
            v0.G = 0x2a; pc=236; continue
        if pc==236:  # 213CA: &v0.B = 0
            v0.B = 0; pc=237; continue
        if pc==237:  # 213CF: goto 215C8
            pc = 300
            continue
        if pc==238:  # 213DA: if (arg0 != 0xf1) goto 21408
            pc = 245 if (arg0 != 0xf1) else 239
            continue
        if pc==239:  # 213DF: if (arg1 != 0x5a) goto 21408
            pc = 245 if (arg1 != 0x5a) else 240
            continue
        if pc==240:  # 213E4: if (arg2 != 0x24) goto 21408
            pc = 245 if (arg2 != 0x24) else 241
            continue
        if pc==241:  # 213ED: &v0.R = 0xff
            v0.R = 0xff; pc=242; continue
        if pc==242:  # 213F6: &v0.G = 0x19
            v0.G = 0x19; pc=243; continue
        if pc==243:  # 213FE: &v0.B = 0
            v0.B = 0; pc=244; continue
        if pc==244:  # 21403: goto 215C8
            pc = 300
            continue
        if pc==245:  # 2140E: if (arg0 != 0xf7) goto 2143F
            pc = 252 if (arg0 != 0xf7) else 246
            continue
        if pc==246:  # 21416: if (arg1 != 0x93) goto 2143F
            pc = 252 if (arg1 != 0x93) else 247
            continue
        if pc==247:  # 2141B: if (arg2 != 0x1e) goto 2143F
            pc = 252 if (arg2 != 0x1e) else 248
            continue
        if pc==248:  # 21424: &v0.R = 0xff
            v0.R = 0xff; pc=249; continue
        if pc==249:  # 2142D: &v0.G = 0x2a
            v0.G = 0x2a; pc=250; continue
        if pc==250:  # 21435: &v0.B = 0
            v0.B = 0; pc=251; continue
        if pc==251:  # 2143A: goto 215C8
            pc = 300
            continue
        if pc==252:  # 21445: if (arg0 != 0xff) goto 21477
            pc = 259 if (arg0 != 0xff) else 253
            continue
        if pc==253:  # 2144D: if (arg1 != 0xff) goto 21477
            pc = 259 if (arg1 != 0xff) else 254
            continue
        if pc==254:  # 21450: if (arg2) goto 21477
            pc = 259 if (arg2) else 255
            continue
        if pc==255:  # 21459: &v0.R = 0xff
            v0.R = 0xff; pc=256; continue
        if pc==256:  # 21465: &v0.G = 0xb4
            v0.G = 0xb4; pc=257; continue
        if pc==257:  # 2146D: &v0.B = 0
            v0.B = 0; pc=258; continue
        if pc==258:  # 21472: goto 215C8
            pc = 300
            continue
        if pc==259:  # 21478: if (arg0) goto 214AF
            pc = 266 if (arg0) else 260
            continue
        if pc==260:  # 21480: if (arg1 != 0xff) goto 214AF
            pc = 266 if (arg1 != 0xff) else 261
            continue
        if pc==261:  # 21488: if (arg2 != 0xff) goto 214AF
            pc = 266 if (arg2 != 0xff) else 262
            continue
        if pc==262:  # 2148D: &v0.R = 0
            v0.R = 0; pc=263; continue
        if pc==263:  # 21499: &v0.G = 0xb4
            v0.G = 0xb4; pc=264; continue
        if pc==264:  # 214A5: &v0.B = 0xc8
            v0.B = 0xc8; pc=265; continue
        if pc==265:  # 214AA: goto 215C8
            pc = 300
            continue
        if pc==266:  # 214B5: if (arg0 != 0x8b) goto 214E7
            pc = 273 if (arg0 != 0x8b) else 267
            continue
        if pc==267:  # 214B8: if (arg1) goto 214E7
            pc = 273 if (arg1) else 268
            continue
        if pc==268:  # 214C0: if (arg2 != 0xff) goto 214E7
            pc = 273 if (arg2 != 0xff) else 269
            continue
        if pc==269:  # 214C9: &v0.R = 0x8a
            v0.R = 0x8a; pc=270; continue
        if pc==270:  # 214D1: &v0.G = 0
            v0.G = 0; pc=271; continue
        if pc==271:  # 214DD: &v0.B = 0xc8
            v0.B = 0xc8; pc=272; continue
        if pc==272:  # 214E2: goto 215C8
            pc = 300
            continue
        if pc==273:  # 214ED: if (arg0 <= 0xf9) goto 21543
            pc = 285 if (arg0 <= 0xf9) else 274
            continue
        if pc==274:  # 214F2: if (arg1 >= 0x14) goto 21543
            pc = 285 if (arg1 >= 0x14) else 275
            continue
        if pc==275:  # 214FA: if (arg2 >= 0x80) goto 21543
            pc = 285 if (arg2 >= 0x80) else 276
            continue
        if pc==276:  # 214FF: if (arg2 >= 0x64) goto 21522
            pc = 281 if (arg2 >= 0x64) else 277
            continue
        if pc==277:  # 21504: &v0.R = arg0
            v0.R = arg0; pc=278; continue
        if pc==278:  # 2150C: &v0.G = arg1
            v0.G = arg1; pc=279; continue
        if pc==279:  # 21518: &v0.B = (arg2 / 0xa)
            v0.B = (arg2 // 0xa); pc=280; continue
        if pc==280:  # 2151D: goto 215C8
            pc = 300
            continue
        if pc==281:  # 21525: &v0.R = arg0
            v0.R = arg0; pc=282; continue
        if pc==282:  # 2152D: &v0.G = arg1
            v0.G = arg1; pc=283; continue
        if pc==283:  # 21539: &v0.B = (arg2 - 0xa)
            v0.B = (arg2 - 0xa); pc=284; continue
        if pc==284:  # 2153E: goto 215C8
            pc = 300
            continue
        if pc==285:  # 21546: if (arg0 >= 0x14) goto 21573
            pc = 291 if (arg0 >= 0x14) else 286
            continue
        if pc==286:  # 2154A: if (arg2 >= arg1) goto 21573
            pc = 291 if (arg2 >= arg1) else 287
            continue
        if pc==287:  # 2154F: &v0.R = arg0
            v0.R = arg0; pc=288; continue
        if pc==288:  # 21557: &v0.G = arg1
            v0.G = arg1; pc=289; continue
        if pc==289:  # 2156C: &v0.B = ((0xc8 * arg2) / 0xff)
            v0.B = ((0xc8 * arg2) // 0xff); pc=290; continue
        if pc==290:  # 21571: goto 215C8
            pc = 300
            continue
        if pc==291:  # 21576: if (arg1 >= 0x14) goto 21596
            pc = 297 if (arg1 >= 0x14) else 292
            continue
        if pc==292:  # 2157A: if (arg0 >= arg2) goto 21596
            pc = 297 if (arg0 >= arg2) else 293
            continue
        if pc==293:  # 2157F: &v0.R = arg0
            v0.R = arg0; pc=294; continue
        if pc==294:  # 21587: &v0.G = arg1
            v0.G = arg1; pc=295; continue
        if pc==295:  # 2158F: &v0.B = arg2
            v0.B = arg2; pc=296; continue
        if pc==296:  # 21594: goto 215C8
            pc = 300
            continue
        if pc==297:  # 21599: &v0.R = arg0
            v0.R = arg0; pc=298; continue
        if pc==298:  # 215AE: &v0.G = ((0xb4 * arg1) / 0xff)
            v0.G = ((0xb4 * arg1) // 0xff); pc=299; continue
        if pc==299:  # 215C3: &v0.B = ((0xc8 * arg2) / 0xff)
            v0.B = ((0xc8 * arg2) // 0xff); pc=300; continue
        if pc==300:  # 215C9: return v0
            return v0.t()
        if pc>=301: return v0.t()

def cheatRGB_2p1ndME(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 215DA: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 215E6: if (arg0 != 0xff) goto 2161B
            pc = 8 if (arg0 != 0xff) else 2
            continue
        if pc==2:  # 215EE: if (arg1 != 0xff) goto 2161B
            pc = 8 if (arg1 != 0xff) else 3
            continue
        if pc==3:  # 215F6: if (arg2 != 0xff) goto 2161B
            pc = 8 if (arg2 != 0xff) else 4
            continue
        if pc==4:  # 215FF: &v0.R = 0xff
            v0.R = 0xff; pc=5; continue
        if pc==5:  # 21608: &v0.G = 0x64
            v0.G = 0x64; pc=6; continue
        if pc==6:  # 21611: &v0.B = 0x50
            v0.B = 0x50; pc=7; continue
        if pc==7:  # 21616: goto 21712
            pc = 39
            continue
        if pc==8:  # 21621: if (arg0 != 0xff) goto 21650
            pc = 15 if (arg0 != 0xff) else 9
            continue
        if pc==9:  # 21629: if (arg1 != 0xa5) goto 21650
            pc = 15 if (arg1 != 0xa5) else 10
            continue
        if pc==10:  # 2162C: if (arg2) goto 21650
            pc = 15 if (arg2) else 11
            continue
        if pc==11:  # 21635: &v0.R = 0xff
            v0.R = 0xff; pc=12; continue
        if pc==12:  # 2163E: &v0.G = 0x1e
            v0.G = 0x1e; pc=13; continue
        if pc==13:  # 21646: &v0.B = 0
            v0.B = 0; pc=14; continue
        if pc==14:  # 2164B: goto 21712
            pc = 39
            continue
        if pc==15:  # 21656: if (arg0 != 0xff) goto 21685
            pc = 22 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 2165E: if (arg1 != 0xff) goto 21685
            pc = 22 if (arg1 != 0xff) else 17
            continue
        if pc==17:  # 21661: if (arg2) goto 21685
            pc = 22 if (arg2) else 18
            continue
        if pc==18:  # 2166A: &v0.R = 0xff
            v0.R = 0xff; pc=19; continue
        if pc==19:  # 21673: &v0.G = 0x64
            v0.G = 0x64; pc=20; continue
        if pc==20:  # 2167B: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21680: goto 21712
            pc = 39
            continue
        if pc==22:  # 21686: if (arg0) goto 216B4
            pc = 29 if (arg0) else 23
            continue
        if pc==23:  # 2168E: if (arg1 != 0xff) goto 216B4
            pc = 29 if (arg1 != 0xff) else 24
            continue
        if pc==24:  # 21696: if (arg2 != 0xff) goto 216B4
            pc = 29 if (arg2 != 0xff) else 25
            continue
        if pc==25:  # 2169B: &v0.R = 0
            v0.R = 0; pc=26; continue
        if pc==26:  # 216A4: &v0.G = 0x64
            v0.G = 0x64; pc=27; continue
        if pc==27:  # 216AD: &v0.B = 0x50
            v0.B = 0x50; pc=28; continue
        if pc==28:  # 216B2: goto 21712
            pc = 39
            continue
        if pc==29:  # 216BA: if (arg0 != 0x8b) goto 216E6
            pc = 36 if (arg0 != 0x8b) else 30
            continue
        if pc==30:  # 216BD: if (arg1) goto 216E6
            pc = 36 if (arg1) else 31
            continue
        if pc==31:  # 216C5: if (arg2 != 0xff) goto 216E6
            pc = 36 if (arg2 != 0xff) else 32
            continue
        if pc==32:  # 216CE: &v0.R = 0xff
            v0.R = 0xff; pc=33; continue
        if pc==33:  # 216D6: &v0.G = 0
            v0.G = 0; pc=34; continue
        if pc==34:  # 216DF: &v0.B = 0x50
            v0.B = 0x50; pc=35; continue
        if pc==35:  # 216E4: goto 21712
            pc = 39
            continue
        if pc==36:  # 216E9: &v0.R = arg0
            v0.R = arg0; pc=37; continue
        if pc==37:  # 216FB: &v0.G = ((0x64 * arg1) / 0xff)
            v0.G = ((0x64 * arg1) // 0xff); pc=38; continue
        if pc==38:  # 2170D: &v0.B = ((0x50 * arg2) / 0xff)
            v0.B = ((0x50 * arg2) // 0xff); pc=39; continue
        if pc==39:  # 21713: return v0
            return v0.t()
        if pc>=40: return v0.t()

def cheatRGB_2p2ndME(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21722: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 2172E: if (WKDColor.m_LED_Vender != 5) goto 21797
            pc = 12 if (_S['vendor'] != 5) else 2
            continue
        if pc==2:  # 21733: &v0.R = arg0
            v0.R = arg0; pc=3; continue
        if pc==3:  # 21745: &v0.G = ((0x46 * arg1) / 0xff)
            v0.G = ((0x46 * arg1) // 0xff); pc=4; continue
        if pc==4:  # 21757: &v0.B = ((0x50 * arg2) / 0xff)
            v0.B = ((0x50 * arg2) // 0xff); pc=5; continue
        if pc==5:  # 21762: if (arg0 != 0xff) goto 21800
            pc = 21 if (arg0 != 0xff) else 6
            continue
        if pc==6:  # 2176D: if (arg1 != 0xa5) goto 21800
            pc = 21 if (arg1 != 0xa5) else 7
            continue
        if pc==7:  # 21773: if (arg2) goto 21800
            pc = 21 if (arg2) else 8
            continue
        if pc==8:  # 2177F: &v0.R = 0xff
            v0.R = 0xff; pc=9; continue
        if pc==9:  # 21788: &v0.G = 0x19
            v0.G = 0x19; pc=10; continue
        if pc==10:  # 21790: &v0.B = 0
            v0.B = 0; pc=11; continue
        if pc==11:  # 21795: goto 21800
            pc = 21
            continue
        if pc==12:  # 217A7: &v0.R = ((0xdc * arg0) / 0xff)
            v0.R = ((0xdc * arg0) // 0xff); pc=13; continue
        if pc==13:  # 217B9: &v0.G = ((0x78 * arg1) / 0xff)
            v0.G = ((0x78 * arg1) // 0xff); pc=14; continue
        if pc==14:  # 217CB: &v0.B = ((0x6e * arg2) / 0xff)
            v0.B = ((0x6e * arg2) // 0xff); pc=15; continue
        if pc==15:  # 217D6: if (arg0 != 0xff) goto 21800
            pc = 21 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 217DE: if (arg1 != 0xa5) goto 21800
            pc = 21 if (arg1 != 0xa5) else 17
            continue
        if pc==17:  # 217E1: if (arg2) goto 21800
            pc = 21 if (arg2) else 18
            continue
        if pc==18:  # 217EA: &v0.R = 0xdc
            v0.R = 0xdc; pc=19; continue
        if pc==19:  # 217F3: &v0.G = 0x1e
            v0.G = 0x1e; pc=20; continue
        if pc==20:  # 217FB: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21801: return v0
            return v0.t()
        if pc>=22: return v0.t()

def cheatRGB_4Zone(arg0, arg1, arg2, arg3):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21812: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 2181A: if (arg0 == 6) goto 21823
            pc = 3 if (arg0 == 6) else 2
            continue
        if pc==2:  # 2181E: if (arg0 != 7) goto 218C1
            pc = 21 if (arg0 != 7) else 3
            continue
        if pc==3:  # 21829: if (arg1 != 0xff) goto 21858
            pc = 10 if (arg1 != 0xff) else 4
            continue
        if pc==4:  # 21831: if (arg2 != 0xa5) goto 21858
            pc = 10 if (arg2 != 0xa5) else 5
            continue
        if pc==5:  # 21834: if (arg3) goto 21858
            pc = 10 if (arg3) else 6
            continue
        if pc==6:  # 2183D: &v0.R = 0xff
            v0.R = 0xff; pc=7; continue
        if pc==7:  # 21846: &v0.G = 0x3c
            v0.G = 0x3c; pc=8; continue
        if pc==8:  # 2184E: &v0.B = 0
            v0.B = 0; pc=9; continue
        if pc==9:  # 21853: goto 21951
            pc = 38
            continue
        if pc==10:  # 2185E: if (arg1 != 0xff) goto 2188D
            pc = 17 if (arg1 != 0xff) else 11
            continue
        if pc==11:  # 21866: if (arg2 != 0xff) goto 2188D
            pc = 17 if (arg2 != 0xff) else 12
            continue
        if pc==12:  # 21869: if (arg3) goto 2188D
            pc = 17 if (arg3) else 13
            continue
        if pc==13:  # 21872: &v0.R = 0xff
            v0.R = 0xff; pc=14; continue
        if pc==14:  # 2187B: &v0.G = 0x78
            v0.G = 0x78; pc=15; continue
        if pc==15:  # 21883: &v0.B = 0
            v0.B = 0; pc=16; continue
        if pc==16:  # 21888: goto 21951
            pc = 38
            continue
        if pc==17:  # 21890: &v0.R = arg1
            v0.R = arg1; pc=18; continue
        if pc==18:  # 218A2: &v0.G = ((0x78 * arg2) / 0xff)
            v0.G = ((0x78 * arg2) // 0xff); pc=19; continue
        if pc==19:  # 218B7: &v0.B = ((0xdc * arg3) / 0xff)
            v0.B = ((0xdc * arg3) // 0xff); pc=20; continue
        if pc==20:  # 218BC: goto 21951
            pc = 38
            continue
        if pc==21:  # 218C7: if (arg1 != 0xff) goto 218F0
            pc = 28 if (arg1 != 0xff) else 22
            continue
        if pc==22:  # 218CC: if (arg2 != 0x64) goto 218F0
            pc = 28 if (arg2 != 0x64) else 23
            continue
        if pc==23:  # 218CF: if (arg3) goto 218F0
            pc = 28 if (arg3) else 24
            continue
        if pc==24:  # 218D8: &v0.R = 0xff
            v0.R = 0xff; pc=25; continue
        if pc==25:  # 218E1: &v0.G = 0x28
            v0.G = 0x28; pc=26; continue
        if pc==26:  # 218E9: &v0.B = 0
            v0.B = 0; pc=27; continue
        if pc==27:  # 218EE: goto 21951
            pc = 38
            continue
        if pc==28:  # 218F6: if (arg1 != 0xff) goto 21922
            pc = 35 if (arg1 != 0xff) else 29
            continue
        if pc==29:  # 218FE: if (arg2 != 0xa5) goto 21922
            pc = 35 if (arg2 != 0xa5) else 30
            continue
        if pc==30:  # 21901: if (arg3) goto 21922
            pc = 35 if (arg3) else 31
            continue
        if pc==31:  # 2190A: &v0.R = 0xff
            v0.R = 0xff; pc=32; continue
        if pc==32:  # 21913: &v0.G = 0x46
            v0.G = 0x46; pc=33; continue
        if pc==33:  # 2191B: &v0.B = 0
            v0.B = 0; pc=34; continue
        if pc==34:  # 21920: goto 21951
            pc = 38
            continue
        if pc==35:  # 21925: &v0.R = arg1
            v0.R = arg1; pc=36; continue
        if pc==36:  # 21937: &v0.G = ((0x64 * arg2) / 0xff)
            v0.G = ((0x64 * arg2) // 0xff); pc=37; continue
        if pc==37:  # 2194C: &v0.B = ((0xc8 * arg3) / 0xff)
            v0.B = ((0xc8 * arg3) // 0xff); pc=38; continue
        if pc==38:  # 21952: return v0
            return v0.t()
        if pc>=39: return v0.t()

def cheatRGB_HIDLightbar(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21962: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 2196E: if (arg0 != 0xff) goto 219A3
            pc = 8 if (arg0 != 0xff) else 2
            continue
        if pc==2:  # 21976: if (arg1 != 0xff) goto 219A3
            pc = 8 if (arg1 != 0xff) else 3
            continue
        if pc==3:  # 2197E: if (arg2 != 0xff) goto 219A3
            pc = 8 if (arg2 != 0xff) else 4
            continue
        if pc==4:  # 21987: &v0.R = 0xdc
            v0.R = 0xdc; pc=5; continue
        if pc==5:  # 21990: &v0.G = 0x78
            v0.G = 0x78; pc=6; continue
        if pc==6:  # 21999: &v0.B = 0x6e
            v0.B = 0x6e; pc=7; continue
        if pc==7:  # 2199E: goto 21AA7
            pc = 39
            continue
        if pc==8:  # 219A9: if (arg0 != 0xff) goto 219D8
            pc = 15 if (arg0 != 0xff) else 9
            continue
        if pc==9:  # 219B1: if (arg1 != 0xa5) goto 219D8
            pc = 15 if (arg1 != 0xa5) else 10
            continue
        if pc==10:  # 219B4: if (arg2) goto 219D8
            pc = 15 if (arg2) else 11
            continue
        if pc==11:  # 219BD: &v0.R = 0xdc
            v0.R = 0xdc; pc=12; continue
        if pc==12:  # 219C6: &v0.G = 0x1e
            v0.G = 0x1e; pc=13; continue
        if pc==13:  # 219CE: &v0.B = 0
            v0.B = 0; pc=14; continue
        if pc==14:  # 219D3: goto 21AA7
            pc = 39
            continue
        if pc==15:  # 219DE: if (arg0 != 0xff) goto 21A0D
            pc = 22 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 219E6: if (arg1 != 0xff) goto 21A0D
            pc = 22 if (arg1 != 0xff) else 17
            continue
        if pc==17:  # 219E9: if (arg2) goto 21A0D
            pc = 22 if (arg2) else 18
            continue
        if pc==18:  # 219F2: &v0.R = 0xdc
            v0.R = 0xdc; pc=19; continue
        if pc==19:  # 219FB: &v0.G = 0x78
            v0.G = 0x78; pc=20; continue
        if pc==20:  # 21A03: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21A08: goto 21AA7
            pc = 39
            continue
        if pc==22:  # 21A0E: if (arg0) goto 21A3C
            pc = 29 if (arg0) else 23
            continue
        if pc==23:  # 21A16: if (arg1 != 0xff) goto 21A3C
            pc = 29 if (arg1 != 0xff) else 24
            continue
        if pc==24:  # 21A1E: if (arg2 != 0xff) goto 21A3C
            pc = 29 if (arg2 != 0xff) else 25
            continue
        if pc==25:  # 21A23: &v0.R = 0
            v0.R = 0; pc=26; continue
        if pc==26:  # 21A2C: &v0.G = 0x3c
            v0.G = 0x3c; pc=27; continue
        if pc==27:  # 21A35: &v0.B = 0x6e
            v0.B = 0x6e; pc=28; continue
        if pc==28:  # 21A3A: goto 21AA7
            pc = 39
            continue
        if pc==29:  # 21A42: if (arg0 != 0x8b) goto 21A6E
            pc = 36 if (arg0 != 0x8b) else 30
            continue
        if pc==30:  # 21A45: if (arg1) goto 21A6E
            pc = 36 if (arg1) else 31
            continue
        if pc==31:  # 21A4D: if (arg2 != 0xff) goto 21A6E
            pc = 36 if (arg2 != 0xff) else 32
            continue
        if pc==32:  # 21A56: &v0.R = 0xdc
            v0.R = 0xdc; pc=33; continue
        if pc==33:  # 21A5E: &v0.G = 0
            v0.G = 0; pc=34; continue
        if pc==34:  # 21A67: &v0.B = 0x6e
            v0.B = 0x6e; pc=35; continue
        if pc==35:  # 21A6C: goto 21AA7
            pc = 39
            continue
        if pc==36:  # 21A7E: &v0.R = ((0xdc * arg0) / 0xff)
            v0.R = ((0xdc * arg0) // 0xff); pc=37; continue
        if pc==37:  # 21A90: &v0.G = ((0x78 * arg1) / 0xff)
            v0.G = ((0x78 * arg1) // 0xff); pc=38; continue
        if pc==38:  # 21AA2: &v0.B = ((0x6e * arg2) / 0xff)
            v0.B = ((0x6e * arg2) // 0xff); pc=39; continue
        if pc==39:  # 21AA8: return v0
            return v0.t()
        if pc>=40: return v0.t()

def cheatRGB_HIDLightbar2(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21ABA: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 21AC6: if (arg0 != 0xff) goto 21AFB
            pc = 8 if (arg0 != 0xff) else 2
            continue
        if pc==2:  # 21ACE: if (arg1 != 0xff) goto 21AFB
            pc = 8 if (arg1 != 0xff) else 3
            continue
        if pc==3:  # 21AD6: if (arg2 != 0xff) goto 21AFB
            pc = 8 if (arg2 != 0xff) else 4
            continue
        if pc==4:  # 21ADF: &v0.R = 0xdc
            v0.R = 0xdc; pc=5; continue
        if pc==5:  # 21AE8: &v0.G = 0x64
            v0.G = 0x64; pc=6; continue
        if pc==6:  # 21AF1: &v0.B = 0x64
            v0.B = 0x64; pc=7; continue
        if pc==7:  # 21AF6: goto 21B98
            pc = 25
            continue
        if pc==8:  # 21B01: if (arg0 != 0xff) goto 21B2D
            pc = 15 if (arg0 != 0xff) else 9
            continue
        if pc==9:  # 21B09: if (arg1 != 0xa5) goto 21B2D
            pc = 15 if (arg1 != 0xa5) else 10
            continue
        if pc==10:  # 21B0C: if (arg2) goto 21B2D
            pc = 15 if (arg2) else 11
            continue
        if pc==11:  # 21B15: &v0.R = 0xff
            v0.R = 0xff; pc=12; continue
        if pc==12:  # 21B1E: &v0.G = 0x2d
            v0.G = 0x2d; pc=13; continue
        if pc==13:  # 21B26: &v0.B = 0
            v0.B = 0; pc=14; continue
        if pc==14:  # 21B2B: goto 21B98
            pc = 25
            continue
        if pc==15:  # 21B33: if (arg0 != 0xff) goto 21B5F
            pc = 22 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 21B3B: if (arg1 != 0xff) goto 21B5F
            pc = 22 if (arg1 != 0xff) else 17
            continue
        if pc==17:  # 21B3E: if (arg2) goto 21B5F
            pc = 22 if (arg2) else 18
            continue
        if pc==18:  # 21B47: &v0.R = 0xff
            v0.R = 0xff; pc=19; continue
        if pc==19:  # 21B50: &v0.G = 0x73
            v0.G = 0x73; pc=20; continue
        if pc==20:  # 21B58: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21B5D: goto 21B98
            pc = 25
            continue
        if pc==22:  # 21B6F: &v0.R = ((0xff * arg0) / 0xff)
            v0.R = ((0xff * arg0) // 0xff); pc=23; continue
        if pc==23:  # 21B81: &v0.G = ((0x64 * arg1) / 0xff)
            v0.G = ((0x64 * arg1) // 0xff); pc=24; continue
        if pc==24:  # 21B93: &v0.B = ((0x64 * arg2) / 0xff)
            v0.B = ((0x64 * arg2) // 0xff); pc=25; continue
        if pc==25:  # 21B99: return v0
            return v0.t()
        if pc>=26: return v0.t()

def cheatRGB_HIDLightbar3(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21BAA: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 21BB6: if (arg0 != 0xff) goto 21BEB
            pc = 8 if (arg0 != 0xff) else 2
            continue
        if pc==2:  # 21BBE: if (arg1 != 0xff) goto 21BEB
            pc = 8 if (arg1 != 0xff) else 3
            continue
        if pc==3:  # 21BC6: if (arg2 != 0xff) goto 21BEB
            pc = 8 if (arg2 != 0xff) else 4
            continue
        if pc==4:  # 21BCF: &v0.R = 0xdc
            v0.R = 0xdc; pc=5; continue
        if pc==5:  # 21BD8: &v0.G = 0x64
            v0.G = 0x64; pc=6; continue
        if pc==6:  # 21BE1: &v0.B = 0x64
            v0.B = 0x64; pc=7; continue
        if pc==7:  # 21BE6: goto 21CEF
            pc = 39
            continue
        if pc==8:  # 21BF1: if (arg0 != 0xff) goto 21C1D
            pc = 15 if (arg0 != 0xff) else 9
            continue
        if pc==9:  # 21BF6: if (arg1 != 0x7b) goto 21C1D
            pc = 15 if (arg1 != 0x7b) else 10
            continue
        if pc==10:  # 21BF9: if (arg2) goto 21C1D
            pc = 15 if (arg2) else 11
            continue
        if pc==11:  # 21C02: &v0.R = 0xff
            v0.R = 0xff; pc=12; continue
        if pc==12:  # 21C0B: &v0.G = 0x28
            v0.G = 0x28; pc=13; continue
        if pc==13:  # 21C13: &v0.B = 0
            v0.B = 0; pc=14; continue
        if pc==14:  # 21C18: goto 21CEF
            pc = 39
            continue
        if pc==15:  # 21C23: if (arg0 != 0xff) goto 21C52
            pc = 22 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 21C2B: if (arg1 != 0xa5) goto 21C52
            pc = 22 if (arg1 != 0xa5) else 17
            continue
        if pc==17:  # 21C2E: if (arg2) goto 21C52
            pc = 22 if (arg2) else 18
            continue
        if pc==18:  # 21C37: &v0.R = 0xff
            v0.R = 0xff; pc=19; continue
        if pc==19:  # 21C40: &v0.G = 0x32
            v0.G = 0x32; pc=20; continue
        if pc==20:  # 21C48: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21C4D: goto 21CEF
            pc = 39
            continue
        if pc==22:  # 21C58: if (arg0 != 0xff) goto 21C84
            pc = 29 if (arg0 != 0xff) else 23
            continue
        if pc==23:  # 21C60: if (arg1 != 0xba) goto 21C84
            pc = 29 if (arg1 != 0xba) else 24
            continue
        if pc==24:  # 21C63: if (arg2) goto 21C84
            pc = 29 if (arg2) else 25
            continue
        if pc==25:  # 21C6C: &v0.R = 0xff
            v0.R = 0xff; pc=26; continue
        if pc==26:  # 21C75: &v0.G = 0x37
            v0.G = 0x37; pc=27; continue
        if pc==27:  # 21C7D: &v0.B = 0
            v0.B = 0; pc=28; continue
        if pc==28:  # 21C82: goto 21CEF
            pc = 39
            continue
        if pc==29:  # 21C8A: if (arg0 != 0xff) goto 21CB6
            pc = 36 if (arg0 != 0xff) else 30
            continue
        if pc==30:  # 21C92: if (arg1 != 0xff) goto 21CB6
            pc = 36 if (arg1 != 0xff) else 31
            continue
        if pc==31:  # 21C95: if (arg2) goto 21CB6
            pc = 36 if (arg2) else 32
            continue
        if pc==32:  # 21C9E: &v0.R = 0xff
            v0.R = 0xff; pc=33; continue
        if pc==33:  # 21CA7: &v0.G = 0x46
            v0.G = 0x46; pc=34; continue
        if pc==34:  # 21CAF: &v0.B = 0
            v0.B = 0; pc=35; continue
        if pc==35:  # 21CB4: goto 21CEF
            pc = 39
            continue
        if pc==36:  # 21CC6: &v0.R = ((0xff * arg0) / 0xff)
            v0.R = ((0xff * arg0) // 0xff); pc=37; continue
        if pc==37:  # 21CD8: &v0.G = ((0x64 * arg1) / 0xff)
            v0.G = ((0x64 * arg1) // 0xff); pc=38; continue
        if pc==38:  # 21CEA: &v0.B = ((0x64 * arg2) / 0xff)
            v0.B = ((0x64 * arg2) // 0xff); pc=39; continue
        if pc==39:  # 21CF0: return v0
            return v0.t()
        if pc>=40: return v0.t()

def cheatRGB_HIDKeyboard3(arg0, arg1, arg2):
    v0=RGB(); v1=RGB(); v2=RGB(); v3=RGB()
    pc=0
    while True:
        if pc==0:  # 21D02: *&v0 = default
            v0=RGB(); pc=1; continue
        if pc==1:  # 21D0E: if (arg0 != 0xff) goto 21D46
            pc = 8 if (arg0 != 0xff) else 2
            continue
        if pc==2:  # 21D16: if (arg1 != 0xff) goto 21D46
            pc = 8 if (arg1 != 0xff) else 3
            continue
        if pc==3:  # 21D1E: if (arg2 != 0xff) goto 21D46
            pc = 8 if (arg2 != 0xff) else 4
            continue
        if pc==4:  # 21D24: &v0.R = 0x7d
            v0.R = 0x7d; pc=5; continue
        if pc==5:  # 21D30: &v0.G = 0xff
            v0.G = 0xff; pc=6; continue
        if pc==6:  # 21D3C: &v0.B = 0xb9
            v0.B = 0xb9; pc=7; continue
        if pc==7:  # 21D41: goto 21EE7
            pc = 60
            continue
        if pc==8:  # 21D4C: if (arg0 != 0xff) goto 21D75
            pc = 15 if (arg0 != 0xff) else 9
            continue
        if pc==9:  # 21D4F: if (arg1) goto 21D75
            pc = 15 if (arg1) else 10
            continue
        if pc==10:  # 21D52: if (arg2) goto 21D75
            pc = 15 if (arg2) else 11
            continue
        if pc==11:  # 21D5B: &v0.R = 0xff
            v0.R = 0xff; pc=12; continue
        if pc==12:  # 21D63: &v0.G = 0
            v0.G = 0; pc=13; continue
        if pc==13:  # 21D6B: &v0.B = 0
            v0.B = 0; pc=14; continue
        if pc==14:  # 21D70: goto 21EE7
            pc = 60
            continue
        if pc==15:  # 21D7B: if (arg0 != 0xff) goto 21DAA
            pc = 22 if (arg0 != 0xff) else 16
            continue
        if pc==16:  # 21D83: if (arg1 != 0xa5) goto 21DAA
            pc = 22 if (arg1 != 0xa5) else 17
            continue
        if pc==17:  # 21D86: if (arg2) goto 21DAA
            pc = 22 if (arg2) else 18
            continue
        if pc==18:  # 21D8F: &v0.R = 0xff
            v0.R = 0xff; pc=19; continue
        if pc==19:  # 21D98: &v0.G = 0x7d
            v0.G = 0x7d; pc=20; continue
        if pc==20:  # 21DA0: &v0.B = 0
            v0.B = 0; pc=21; continue
        if pc==21:  # 21DA5: goto 21EE7
            pc = 60
            continue
        if pc==22:  # 21DB0: if (arg0 != 0xff) goto 21DE2
            pc = 29 if (arg0 != 0xff) else 23
            continue
        if pc==23:  # 21DB8: if (arg1 != 0xff) goto 21DE2
            pc = 29 if (arg1 != 0xff) else 24
            continue
        if pc==24:  # 21DBB: if (arg2) goto 21DE2
            pc = 29 if (arg2) else 25
            continue
        if pc==25:  # 21DC4: &v0.R = 0xd2
            v0.R = 0xd2; pc=26; continue
        if pc==26:  # 21DD0: &v0.G = 0xff
            v0.G = 0xff; pc=27; continue
        if pc==27:  # 21DD8: &v0.B = 0
            v0.B = 0; pc=28; continue
        if pc==28:  # 21DDD: goto 21EE7
            pc = 60
            continue
        if pc==29:  # 21DE3: if (arg0) goto 21E11
            pc = 36 if (arg0) else 30
            continue
        if pc==30:  # 21DEB: if (arg1 != 0xff) goto 21E11
            pc = 36 if (arg1 != 0xff) else 31
            continue
        if pc==31:  # 21DEE: if (arg2) goto 21E11
            pc = 36 if (arg2) else 32
            continue
        if pc==32:  # 21DF3: &v0.R = 0
            v0.R = 0; pc=33; continue
        if pc==33:  # 21DFF: &v0.G = 0xff
            v0.G = 0xff; pc=34; continue
        if pc==34:  # 21E07: &v0.B = 0
            v0.B = 0; pc=35; continue
        if pc==35:  # 21E0C: goto 21EE7
            pc = 60
            continue
        if pc==36:  # 21E12: if (arg0) goto 21E49
            pc = 43 if (arg0) else 37
            continue
        if pc==37:  # 21E1A: if (arg1 != 0xff) goto 21E49
            pc = 43 if (arg1 != 0xff) else 38
            continue
        if pc==38:  # 21E22: if (arg2 != 0xff) goto 21E49
            pc = 43 if (arg2 != 0xff) else 39
            continue
        if pc==39:  # 21E27: &v0.R = 0
            v0.R = 0; pc=40; continue
        if pc==40:  # 21E33: &v0.G = 0x82
            v0.G = 0x82; pc=41; continue
        if pc==41:  # 21E3F: &v0.B = 0xff
            v0.B = 0xff; pc=42; continue
        if pc==42:  # 21E44: goto 21EE7
            pc = 60
            continue
        if pc==43:  # 21E4A: if (arg0) goto 21E76
            pc = 50 if (arg0) else 44
            continue
        if pc==44:  # 21E4D: if (arg1) goto 21E76
            pc = 50 if (arg1) else 45
            continue
        if pc==45:  # 21E55: if (arg2 != 0xff) goto 21E76
            pc = 50 if (arg2 != 0xff) else 46
            continue
        if pc==46:  # 21E5A: &v0.R = 0
            v0.R = 0; pc=47; continue
        if pc==47:  # 21E63: &v0.G = 0x14
            v0.G = 0x14; pc=48; continue
        if pc==48:  # 21E6F: &v0.B = 0xff
            v0.B = 0xff; pc=49; continue
        if pc==49:  # 21E74: goto 21EE7
            pc = 60
            continue
        if pc==50:  # 21E7C: if (arg0 != 0x8b) goto 21EA8
            pc = 57 if (arg0 != 0x8b) else 51
            continue
        if pc==51:  # 21E7F: if (arg1) goto 21EA8
            pc = 57 if (arg1) else 52
            continue
        if pc==52:  # 21E87: if (arg2 != 0xff) goto 21EA8
            pc = 57 if (arg2 != 0xff) else 53
            continue
        if pc==53:  # 21E8D: &v0.R = 0x6e
            v0.R = 0x6e; pc=54; continue
        if pc==54:  # 21E95: &v0.G = 0
            v0.G = 0; pc=55; continue
        if pc==55:  # 21EA1: &v0.B = 0xff
            v0.B = 0xff; pc=56; continue
        if pc==56:  # 21EA6: goto 21EE7
            pc = 60
            continue
        if pc==57:  # 21EB8: &v0.R = ((0xff * arg0) / 0xff)
            v0.R = ((0xff * arg0) // 0xff); pc=58; continue
        if pc==58:  # 21ECD: &v0.G = ((0xff * arg1) / 0xff)
            v0.G = ((0xff * arg1) // 0xff); pc=59; continue
        if pc==59:  # 21EE2: &v0.B = ((0xff * arg2) / 0xff)
            v0.B = ((0xff * arg2) // 0xff); pc=60; continue
        if pc==60:  # 21EE8: return v0
            return v0.t()
        if pc>=61: return v0.t()

