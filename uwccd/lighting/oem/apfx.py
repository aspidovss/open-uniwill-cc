# Generated from GCUService LightingModel.LM_ITE_RGB.AP_Effect_Task / MyRgbKeyboard.AlphabetEffect.
# Software keyboard effects: Neon (0x0F), Alphabet (0x17), Impact (0x0D), Stack (0x0C).
# Do not edit by hand — regenerate with tools/apport.py.

class RGB:
    __slots__ = ("R", "G", "B", "ID")

    def __init__(self, R=0, G=0, B=0, ID=0):
        self.R, self.G, self.B, self.ID = R, G, B, ID

    def t(self):
        return (self.R & 255, self.G & 255, self.B & 255)

GLYPHS = {
    '0': [2, 3, 5, 6, 22, 23, 24, 26, 27, 28, 44, 45, 46, 47, 48, 49, 65, 66, 67, 68, 69, 88, 89],
    'A': [3, 24, 25, 45, 47, 66, 67, 68, 87, 90],
    'B': [1, 2, 3, 4, 22, 25, 44, 45, 46, 65, 68, 87, 88, 89, 90],
    'C': [23, 44, 65],
    'D': [1, 2, 3, 22, 25, 44, 47, 65, 67, 87, 88],
    'E': [22, 65],
    'F': [22, 65, 87],
    'G': [23, 44, 65, 68, 91],
    'H': [2, 6, 23, 27, 66, 69, 87, 88, 90, 91],
    'I': [24, 46, 67],
    'J': [24, 46, 65, 67],
    'K': [2, 5, 23, 25, 45, 46, 65, 67, 87, 89, 90],
    'L': [1, 22, 44, 65],
    'M': [1, 5, 22, 23, 25, 26, 44, 46, 48, 65, 69, 87, 91],
    'N': [2, 3, 6, 23, 25, 27, 45, 47, 49, 66, 68, 70, 88, 90, 91, 92],
    'O': [1, 2, 3, 4, 22, 25, 44, 47, 65, 68, 87, 88, 89, 90],
    'P': [1, 2, 3, 4, 22, 25, 44, 45, 46, 65, 87],
    'Q': [1, 2, 3, 4, 22, 25, 44, 47, 65, 67, 68, 87, 88, 89, 90, 91],
    'R': [1, 2, 3, 4, 22, 25, 44, 45, 46, 47, 65, 68, 87, 90],
    'S': [1, 2, 3, 4, 22, 44, 45, 46, 47, 68, 87, 88, 89, 90],
    'T': [1, 2, 3, 4, 23, 45, 66, 88],
    'U': [1, 4, 22, 25, 44, 47, 65, 68, 87, 88, 89, 90],
    'V': [1, 4, 22, 25, 44, 46, 65, 66, 87],
    'W': [1, 3, 5, 22, 24, 26, 44, 46, 48, 87, 88, 89],
    'X': [1, 5, 23, 24, 46, 67, 68, 87, 90],
    'Y': [1, 4, 23, 24, 45, 66, 88],
    'Z': [2, 3, 4, 5, 25, 46, 66, 87, 88, 89, 90],
}



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
        if pc == 0:  # 14F46: if (v2 == this.m_ap_effect_data.save_light) goto 14F56
            pc = 3 if (v2 == ctx.light) else 1; continue
        if pc == 1:  # 14F53: v2 = this.m_ap_effect_data.save_light
            v2 = ctx.light; pc = 2; continue
        if pc == 2:  # 14F55: v3 = 1
            v3 = 1; pc = 3; continue
        if pc == 3:  # 14F63: if (this.m_ap_effect_data.save_effect != 0x19) goto 15172
            pc = 4 if (ctx.effect != 0x19) else 4; continue
        if pc == 4:  # 1517F: if (this.m_ap_effect_data.save_effect != 0x18) goto 15274
            pc = 5 if (ctx.effect != 0x18) else 5; continue
        if pc == 5:  # 15281: if (this.m_ap_effect_data.save_effect != 0xf) goto 1534E
            pc = 17 if (ctx.effect != 0xf) else 6; continue
        if pc == 6:  # 15289: if (v4 != 7) goto 1528E
            pc = 8 if (v4 != 7) else 7; continue
        if pc == 7:  # 1528C: v4 = 0
            v4 = 0; pc = 8; continue
        if pc == 8:  # 152B1: v0[0].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[v4].R
            v0[0].R = CB[v4].R; pc = 9; continue
        if pc == 9:  # 152D9: v0[0].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[v4].G
            v0[0].G = CB[v4].G; pc = 10; continue
        if pc == 10:  # 15301: v0[0].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[v4].B
            v0[0].B = CB[v4].B; pc = 11; continue
        if pc == 11:  # 1531A: this.Set_ITE_Effect_Type_StaticMode(this.m_ap_effect_data.save_light, 0, v0, v3)
            ctx.static_mode(v0[0], v3); pc = 12; continue
        if pc == 12:  # 15329: Thread.Sleep((0x32 * this.m_ap_effect_data.save_speed))
            if not ctx.sleep((0x32 * ctx.speed)): return
            pc = 13; continue
        if pc == 13:  # 15332: v4 = (v4 + 1)
            v4 = (v4 + 1); pc = 14; continue
        if pc == 14:  # 15341: if (this.m_ap_effect_data.save_effect == 0xf) goto 19CF4
            pc = 1400 if (ctx.effect == 0xf) else 15; continue
        if pc == 15:  # 15347: v4 = 0
            v4 = 0; pc = 16; continue
        if pc == 16:  # 15349: goto 19CF4
            pc = 1400; continue
        if pc == 17:  # 1535B: if (this.m_ap_effect_data.save_effect != 0x17) goto 1543B
            pc = 38 if (ctx.effect != 0x17) else 18; continue
        if pc == 18:  # 15369: v30 = (0x13 - this.ColRightShift)
            v30 = (0x13 - 0); pc = 19; continue
        if pc == 19:  # 15372: if (this.AlphabetString) goto 15378
            pc = 20; continue
        if pc == 20:  # 15376: goto 15387
            pc = 21; continue
        if pc == 21:  # 15387: v31 = Enumerable.ToArray(null.Trim().ToUpperInvariant())
            v31 = list((ctx.alphabet or '').strip().upper()); pc = 22; continue
        if pc == 22:  # 1538B: if (!v31) goto 19CF4
            pc = 1400 if (not v31) else 23; continue
        if pc == 23:  # 15396: if (v4 != v30) goto 153A1
            pc = 26 if (v4 != v30) else 24; continue
        if pc == 24:  # 15399: v4 = 0
            v4 = 0; pc = 25; continue
        if pc == 25:  # 1539F: v5 = (v5 + 1)
            v5 = (v5 + 1); pc = 26; continue
        if pc == 26:  # 153AA: if (v5 < Enumerable.Count(v31)) goto 153AF
            pc = 28 if (v5 < len(v31)) else 27; continue
        if pc == 27:  # 153AD: v5 = 0
            v5 = 0; pc = 28; continue
        if pc == 28:  # 153B7: if (Enumerable.Count(v31) <= 0) goto 19CF4
            pc = 1400 if (len(v31) <= 0) else 29; continue
        if pc == 29:  # 153E5: new AlphabetEffect(v31[v5], this.m_ap_effect_data.save_layout_color.ColorBuffer, v4).SetShift(Convert.ToInt32(
            pc = 30; continue
        if pc == 30:  # 153EF: v1 = new AlphabetEffect(v31[v5], this.m_ap_effect_data.save_layout_color.ColorBuffer, v4).GetAlphbetEffect()
            v1 = alphabet_frame(v31[v5], CB, v4, v4 % v30); pc = 31; continue
        if pc == 31:  # 15404: this.Set_ITE_Effect_Type_UserMode(this.m_ap_effect_data.save_light, 0, v1, v3)
            ctx.user_mode(v1, v3); pc = 32; continue
        if pc == 32:  # 15413: Thread.Sleep((0x50 * this.m_ap_effect_data.save_speed))
            if not ctx.sleep((0x50 * ctx.speed)): return
            pc = 33; continue
        if pc == 33:  # 1541C: v4 = (v4 + 1)
            v4 = (v4 + 1); pc = 34; continue
        if pc == 34:  # 1542B: if (this.m_ap_effect_data.save_effect == 0x17) goto 19CF4
            pc = 1400 if (ctx.effect == 0x17) else 35; continue
        if pc == 35:  # 15431: v4 = 0
            v4 = 0; pc = 36; continue
        if pc == 36:  # 15434: v5 = 0
            v5 = 0; pc = 37; continue
        if pc == 37:  # 15436: goto 19CF4
            pc = 1400; continue
        if pc == 38:  # 15448: if (this.m_ap_effect_data.save_effect != 0xd) goto 167F0
            pc = 217 if (ctx.effect != 0xd) else 39; continue
        if pc == 39:  # 1546F: v0[0].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].R
            v0[0].R = CB[0].R; pc = 40; continue
        if pc == 40:  # 15496: v0[0].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].G
            v0[0].G = CB[0].G; pc = 41; continue
        if pc == 41:  # 154BD: v0[0].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].B
            v0[0].B = CB[0].B; pc = 42; continue
        if pc == 42:  # 154E4: v0[1].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].R
            v0[1].R = CB[1].R; pc = 43; continue
        if pc == 43:  # 1550B: v0[1].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].G
            v0[1].G = CB[1].G; pc = 44; continue
        if pc == 44:  # 15532: v0[1].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].B
            v0[1].B = CB[1].B; pc = 45; continue
        if pc == 45:  # 15559: v0[2].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].R
            v0[2].R = CB[2].R; pc = 46; continue
        if pc == 46:  # 15580: v0[2].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].G
            v0[2].G = CB[2].G; pc = 47; continue
        if pc == 47:  # 155A7: v0[2].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].B
            v0[2].B = CB[2].B; pc = 48; continue
        if pc == 48:  # 155AD: v32 = 0
            v32 = 0; pc = 49; continue
        if pc == 49:  # 155B5: if (!this.ColRightShift) goto 155C1
            pc = 51 if (not 0) else 50; continue
        if pc == 50:  # 155BF: v32 = (this.ColRightShift + 3)
            v32 = (0 + 3); pc = 51; continue
        if pc == 51:  # 155C6: v33 = (0x14 - v32)
            v33 = (0x14 - v32); pc = 52; continue
        if pc == 52:  # 155CE: if (v4 != v33) goto 155D3
            pc = 54 if (v4 != v33) else 53; continue
        if pc == 53:  # 155D1: v4 = 0
            v4 = 0; pc = 54; continue
        if pc == 54:  # 155D4: v34 = 0
            v34 = 0; pc = 55; continue
        if pc == 55:  # 155D6: goto 15617
            pc = 61; continue
        if pc == 56:  # 155E2: v1[v34].ID = v34
            v1[v34].ID = v34; pc = 57; continue
        if pc == 57:  # 155F0: v1[v34].R = 0
            v1[v34].R = 0; pc = 58; continue
        if pc == 58:  # 155FE: v1[v34].G = 0
            v1[v34].G = 0; pc = 59; continue
        if pc == 59:  # 1560C: v1[v34].B = 0
            v1[v34].B = 0; pc = 60; continue
        if pc == 60:  # 15615: v34 = (v34 + 1)
            v34 = (v34 + 1); pc = 61; continue
        if pc == 61:  # 1561B: if (v34 < 0x7e) goto 155D8
            pc = 56 if (v34 < 0x7e) else 62; continue
        if pc == 62:  # 15625: if (v4 >= (v33 / 2)) goto 15EDB
            pc = 136 if (v4 >= (v33 // 2)) else 63; continue
        if pc == 63:  # 1563E: v1[v4].R = v0[0].R
            v1[v4].R = v0[0].R; pc = 64; continue
        if pc == 64:  # 15657: v1[v4].G = v0[0].G
            v1[v4].G = v0[0].G; pc = 65; continue
        if pc == 65:  # 15670: v1[v4].B = v0[0].B
            v1[v4].B = v0[0].B; pc = 66; continue
        if pc == 66:  # 1568B: v1[(1 + v4)].R = v0[0].R
            v1[(1 + v4)].R = v0[0].R; pc = 67; continue
        if pc == 67:  # 156A6: v1[(1 + v4)].G = v0[0].G
            v1[(1 + v4)].G = v0[0].G; pc = 68; continue
        if pc == 68:  # 156C1: v1[(1 + v4)].B = v0[0].B
            v1[(1 + v4)].B = v0[0].B; pc = 69; continue
        if pc == 69:  # 156DD: v1[(0x15 + v4)].R = v0[0].R
            v1[(0x15 + v4)].R = v0[0].R; pc = 70; continue
        if pc == 70:  # 156F9: v1[(0x15 + v4)].G = v0[0].G
            v1[(0x15 + v4)].G = v0[0].G; pc = 71; continue
        if pc == 71:  # 15715: v1[(0x15 + v4)].B = v0[0].B
            v1[(0x15 + v4)].B = v0[0].B; pc = 72; continue
        if pc == 72:  # 15731: v1[(0x16 + v4)].R = v0[0].R
            v1[(0x16 + v4)].R = v0[0].R; pc = 73; continue
        if pc == 73:  # 1574D: v1[(0x16 + v4)].G = v0[0].G
            v1[(0x16 + v4)].G = v0[0].G; pc = 74; continue
        if pc == 74:  # 15769: v1[(0x16 + v4)].B = v0[0].B
            v1[(0x16 + v4)].B = v0[0].B; pc = 75; continue
        if pc == 75:  # 15785: v1[(0x2a + v4)].R = v0[0].R
            v1[(0x2a + v4)].R = v0[0].R; pc = 76; continue
        if pc == 76:  # 157A1: v1[(0x2a + v4)].G = v0[0].G
            v1[(0x2a + v4)].G = v0[0].G; pc = 77; continue
        if pc == 77:  # 157BD: v1[(0x2a + v4)].B = v0[0].B
            v1[(0x2a + v4)].B = v0[0].B; pc = 78; continue
        if pc == 78:  # 157D9: v1[(0x2b + v4)].R = v0[0].R
            v1[(0x2b + v4)].R = v0[0].R; pc = 79; continue
        if pc == 79:  # 157F5: v1[(0x2b + v4)].G = v0[0].G
            v1[(0x2b + v4)].G = v0[0].G; pc = 80; continue
        if pc == 80:  # 15811: v1[(0x2b + v4)].B = v0[0].B
            v1[(0x2b + v4)].B = v0[0].B; pc = 81; continue
        if pc == 81:  # 1582D: v1[(0x3f + v4)].R = v0[0].R
            v1[(0x3f + v4)].R = v0[0].R; pc = 82; continue
        if pc == 82:  # 15849: v1[(0x3f + v4)].G = v0[0].G
            v1[(0x3f + v4)].G = v0[0].G; pc = 83; continue
        if pc == 83:  # 15865: v1[(0x3f + v4)].B = v0[0].B
            v1[(0x3f + v4)].B = v0[0].B; pc = 84; continue
        if pc == 84:  # 15881: v1[(0x40 + v4)].R = v0[0].R
            v1[(0x40 + v4)].R = v0[0].R; pc = 85; continue
        if pc == 85:  # 1589D: v1[(0x40 + v4)].G = v0[0].G
            v1[(0x40 + v4)].G = v0[0].G; pc = 86; continue
        if pc == 86:  # 158B9: v1[(0x40 + v4)].B = v0[0].B
            v1[(0x40 + v4)].B = v0[0].B; pc = 87; continue
        if pc == 87:  # 158D5: v1[(0x54 + v4)].R = v0[0].R
            v1[(0x54 + v4)].R = v0[0].R; pc = 88; continue
        if pc == 88:  # 158F1: v1[(0x54 + v4)].G = v0[0].G
            v1[(0x54 + v4)].G = v0[0].G; pc = 89; continue
        if pc == 89:  # 1590D: v1[(0x54 + v4)].B = v0[0].B
            v1[(0x54 + v4)].B = v0[0].B; pc = 90; continue
        if pc == 90:  # 15929: v1[(0x55 + v4)].R = v0[0].R
            v1[(0x55 + v4)].R = v0[0].R; pc = 91; continue
        if pc == 91:  # 15945: v1[(0x55 + v4)].G = v0[0].G
            v1[(0x55 + v4)].G = v0[0].G; pc = 92; continue
        if pc == 92:  # 15961: v1[(0x55 + v4)].B = v0[0].B
            v1[(0x55 + v4)].B = v0[0].B; pc = 93; continue
        if pc == 93:  # 1597D: v1[(0x69 + v4)].R = v0[0].R
            v1[(0x69 + v4)].R = v0[0].R; pc = 94; continue
        if pc == 94:  # 15999: v1[(0x69 + v4)].G = v0[0].G
            v1[(0x69 + v4)].G = v0[0].G; pc = 95; continue
        if pc == 95:  # 159B5: v1[(0x69 + v4)].B = v0[0].B
            v1[(0x69 + v4)].B = v0[0].B; pc = 96; continue
        if pc == 96:  # 159D1: v1[(0x6a + v4)].R = v0[0].R
            v1[(0x6a + v4)].R = v0[0].R; pc = 97; continue
        if pc == 97:  # 159ED: v1[(0x6a + v4)].G = v0[0].G
            v1[(0x6a + v4)].G = v0[0].G; pc = 98; continue
        if pc == 98:  # 15A09: v1[(0x6a + v4)].B = v0[0].B
            v1[(0x6a + v4)].B = v0[0].B; pc = 99; continue
        if pc == 99:  # 15A2B: v1[((0x14 - v32) - v4)].R = v0[1].R
            v1[((0x14 - v32) - v4)].R = v0[1].R; pc = 100; continue
        if pc == 100:  # 15A4D: v1[((0x14 - v32) - v4)].G = v0[1].G
            v1[((0x14 - v32) - v4)].G = v0[1].G; pc = 101; continue
        if pc == 101:  # 15A6F: v1[((0x14 - v32) - v4)].B = v0[1].B
            v1[((0x14 - v32) - v4)].B = v0[1].B; pc = 102; continue
        if pc == 102:  # 15A91: v1[((0x13 - v32) - v4)].R = v0[1].R
            v1[((0x13 - v32) - v4)].R = v0[1].R; pc = 103; continue
        if pc == 103:  # 15AB3: v1[((0x13 - v32) - v4)].G = v0[1].G
            v1[((0x13 - v32) - v4)].G = v0[1].G; pc = 104; continue
        if pc == 104:  # 15AD5: v1[((0x13 - v32) - v4)].B = v0[1].B
            v1[((0x13 - v32) - v4)].B = v0[1].B; pc = 105; continue
        if pc == 105:  # 15AF7: v1[((0x29 - v32) - v4)].R = v0[1].R
            v1[((0x29 - v32) - v4)].R = v0[1].R; pc = 106; continue
        if pc == 106:  # 15B19: v1[((0x29 - v32) - v4)].G = v0[1].G
            v1[((0x29 - v32) - v4)].G = v0[1].G; pc = 107; continue
        if pc == 107:  # 15B3B: v1[((0x29 - v32) - v4)].B = v0[1].B
            v1[((0x29 - v32) - v4)].B = v0[1].B; pc = 108; continue
        if pc == 108:  # 15B5D: v1[((0x28 - v32) - v4)].R = v0[1].R
            v1[((0x28 - v32) - v4)].R = v0[1].R; pc = 109; continue
        if pc == 109:  # 15B7F: v1[((0x28 - v32) - v4)].G = v0[1].G
            v1[((0x28 - v32) - v4)].G = v0[1].G; pc = 110; continue
        if pc == 110:  # 15BA1: v1[((0x28 - v32) - v4)].B = v0[1].B
            v1[((0x28 - v32) - v4)].B = v0[1].B; pc = 111; continue
        if pc == 111:  # 15BC3: v1[((0x3e - v32) - v4)].R = v0[1].R
            v1[((0x3e - v32) - v4)].R = v0[1].R; pc = 112; continue
        if pc == 112:  # 15BE5: v1[((0x3e - v32) - v4)].G = v0[1].G
            v1[((0x3e - v32) - v4)].G = v0[1].G; pc = 113; continue
        if pc == 113:  # 15C07: v1[((0x3e - v32) - v4)].B = v0[1].B
            v1[((0x3e - v32) - v4)].B = v0[1].B; pc = 114; continue
        if pc == 114:  # 15C29: v1[((0x3d - v32) - v4)].R = v0[1].R
            v1[((0x3d - v32) - v4)].R = v0[1].R; pc = 115; continue
        if pc == 115:  # 15C4B: v1[((0x3d - v32) - v4)].G = v0[1].G
            v1[((0x3d - v32) - v4)].G = v0[1].G; pc = 116; continue
        if pc == 116:  # 15C6D: v1[((0x3d - v32) - v4)].B = v0[1].B
            v1[((0x3d - v32) - v4)].B = v0[1].B; pc = 117; continue
        if pc == 117:  # 15C8F: v1[((0x53 - v32) - v4)].R = v0[1].R
            v1[((0x53 - v32) - v4)].R = v0[1].R; pc = 118; continue
        if pc == 118:  # 15CB1: v1[((0x53 - v32) - v4)].G = v0[1].G
            v1[((0x53 - v32) - v4)].G = v0[1].G; pc = 119; continue
        if pc == 119:  # 15CD3: v1[((0x53 - v32) - v4)].B = v0[1].B
            v1[((0x53 - v32) - v4)].B = v0[1].B; pc = 120; continue
        if pc == 120:  # 15CF5: v1[((0x52 - v32) - v4)].R = v0[1].R
            v1[((0x52 - v32) - v4)].R = v0[1].R; pc = 121; continue
        if pc == 121:  # 15D17: v1[((0x52 - v32) - v4)].G = v0[1].G
            v1[((0x52 - v32) - v4)].G = v0[1].G; pc = 122; continue
        if pc == 122:  # 15D39: v1[((0x52 - v32) - v4)].B = v0[1].B
            v1[((0x52 - v32) - v4)].B = v0[1].B; pc = 123; continue
        if pc == 123:  # 15D5B: v1[((0x68 - v32) - v4)].R = v0[1].R
            v1[((0x68 - v32) - v4)].R = v0[1].R; pc = 124; continue
        if pc == 124:  # 15D7D: v1[((0x68 - v32) - v4)].G = v0[1].G
            v1[((0x68 - v32) - v4)].G = v0[1].G; pc = 125; continue
        if pc == 125:  # 15D9F: v1[((0x68 - v32) - v4)].B = v0[1].B
            v1[((0x68 - v32) - v4)].B = v0[1].B; pc = 126; continue
        if pc == 126:  # 15DC1: v1[((0x67 - v32) - v4)].R = v0[1].R
            v1[((0x67 - v32) - v4)].R = v0[1].R; pc = 127; continue
        if pc == 127:  # 15DE3: v1[((0x67 - v32) - v4)].G = v0[1].G
            v1[((0x67 - v32) - v4)].G = v0[1].G; pc = 128; continue
        if pc == 128:  # 15E05: v1[((0x67 - v32) - v4)].B = v0[1].B
            v1[((0x67 - v32) - v4)].B = v0[1].B; pc = 129; continue
        if pc == 129:  # 15E27: v1[((0x7d - v32) - v4)].R = v0[1].R
            v1[((0x7d - v32) - v4)].R = v0[1].R; pc = 130; continue
        if pc == 130:  # 15E49: v1[((0x7d - v32) - v4)].G = v0[1].G
            v1[((0x7d - v32) - v4)].G = v0[1].G; pc = 131; continue
        if pc == 131:  # 15E6B: v1[((0x7d - v32) - v4)].B = v0[1].B
            v1[((0x7d - v32) - v4)].B = v0[1].B; pc = 132; continue
        if pc == 132:  # 15E8D: v1[((0x7c - v32) - v4)].R = v0[1].R
            v1[((0x7c - v32) - v4)].R = v0[1].R; pc = 133; continue
        if pc == 133:  # 15EAF: v1[((0x7c - v32) - v4)].G = v0[1].G
            v1[((0x7c - v32) - v4)].G = v0[1].G; pc = 134; continue
        if pc == 134:  # 15ED1: v1[((0x7c - v32) - v4)].B = v0[1].B
            v1[((0x7c - v32) - v4)].B = v0[1].B; pc = 135; continue
        if pc == 135:  # 15ED6: goto 167A8
            pc = 211; continue
        if pc == 136:  # 15EE0: v35 = (v4 - 0xa)
            v35 = (v4 - 0xa); pc = 137; continue
        if pc == 137:  # 15EE8: if (!this.ColRightShift) goto 15EF0
            pc = 139 if (not 0) else 138; continue
        if pc == 138:  # 15EEE: v35 = (v4 - 4)
            v35 = (v4 - 4); pc = 139; continue
        if pc == 139:  # 15F07: v1[(0xa - v35)].R = v0[2].R
            v1[(0xa - v35)].R = v0[2].R; pc = 140; continue
        if pc == 140:  # 15F23: v1[(0xa - v35)].G = v0[2].G
            v1[(0xa - v35)].G = v0[2].G; pc = 141; continue
        if pc == 141:  # 15F3F: v1[(0xa - v35)].B = v0[2].B
            v1[(0xa - v35)].B = v0[2].B; pc = 142; continue
        if pc == 142:  # 15F5B: v1[(9 - v35)].R = v0[2].R
            v1[(9 - v35)].R = v0[2].R; pc = 143; continue
        if pc == 143:  # 15F77: v1[(9 - v35)].G = v0[2].G
            v1[(9 - v35)].G = v0[2].G; pc = 144; continue
        if pc == 144:  # 15F93: v1[(9 - v35)].B = v0[2].B
            v1[(9 - v35)].B = v0[2].B; pc = 145; continue
        if pc == 145:  # 15FAF: v1[(0x1f - v35)].R = v0[2].R
            v1[(0x1f - v35)].R = v0[2].R; pc = 146; continue
        if pc == 146:  # 15FCB: v1[(0x1f - v35)].G = v0[2].G
            v1[(0x1f - v35)].G = v0[2].G; pc = 147; continue
        if pc == 147:  # 15FE7: v1[(0x1f - v35)].B = v0[2].B
            v1[(0x1f - v35)].B = v0[2].B; pc = 148; continue
        if pc == 148:  # 16003: v1[(0x1e - v35)].R = v0[2].R
            v1[(0x1e - v35)].R = v0[2].R; pc = 149; continue
        if pc == 149:  # 1601F: v1[(0x1e - v35)].G = v0[2].G
            v1[(0x1e - v35)].G = v0[2].G; pc = 150; continue
        if pc == 150:  # 1603B: v1[(0x1e - v35)].B = v0[2].B
            v1[(0x1e - v35)].B = v0[2].B; pc = 151; continue
        if pc == 151:  # 16057: v1[(0x34 - v35)].R = v0[2].R
            v1[(0x34 - v35)].R = v0[2].R; pc = 152; continue
        if pc == 152:  # 16073: v1[(0x34 - v35)].G = v0[2].G
            v1[(0x34 - v35)].G = v0[2].G; pc = 153; continue
        if pc == 153:  # 1608F: v1[(0x34 - v35)].B = v0[2].B
            v1[(0x34 - v35)].B = v0[2].B; pc = 154; continue
        if pc == 154:  # 160AB: v1[(0x33 - v35)].R = v0[2].R
            v1[(0x33 - v35)].R = v0[2].R; pc = 155; continue
        if pc == 155:  # 160C7: v1[(0x33 - v35)].G = v0[2].G
            v1[(0x33 - v35)].G = v0[2].G; pc = 156; continue
        if pc == 156:  # 160E3: v1[(0x33 - v35)].B = v0[2].B
            v1[(0x33 - v35)].B = v0[2].B; pc = 157; continue
        if pc == 157:  # 160FF: v1[(0x49 - v35)].R = v0[2].R
            v1[(0x49 - v35)].R = v0[2].R; pc = 158; continue
        if pc == 158:  # 1611B: v1[(0x49 - v35)].G = v0[2].G
            v1[(0x49 - v35)].G = v0[2].G; pc = 159; continue
        if pc == 159:  # 16137: v1[(0x49 - v35)].B = v0[2].B
            v1[(0x49 - v35)].B = v0[2].B; pc = 160; continue
        if pc == 160:  # 16153: v1[(0x48 - v35)].R = v0[2].R
            v1[(0x48 - v35)].R = v0[2].R; pc = 161; continue
        if pc == 161:  # 1616F: v1[(0x48 - v35)].G = v0[2].G
            v1[(0x48 - v35)].G = v0[2].G; pc = 162; continue
        if pc == 162:  # 1618B: v1[(0x48 - v35)].B = v0[2].B
            v1[(0x48 - v35)].B = v0[2].B; pc = 163; continue
        if pc == 163:  # 161A7: v1[(0x5e - v35)].R = v0[2].R
            v1[(0x5e - v35)].R = v0[2].R; pc = 164; continue
        if pc == 164:  # 161C3: v1[(0x5e - v35)].G = v0[2].G
            v1[(0x5e - v35)].G = v0[2].G; pc = 165; continue
        if pc == 165:  # 161DF: v1[(0x5e - v35)].B = v0[2].B
            v1[(0x5e - v35)].B = v0[2].B; pc = 166; continue
        if pc == 166:  # 161FB: v1[(0x5d - v35)].R = v0[2].R
            v1[(0x5d - v35)].R = v0[2].R; pc = 167; continue
        if pc == 167:  # 16217: v1[(0x5d - v35)].G = v0[2].G
            v1[(0x5d - v35)].G = v0[2].G; pc = 168; continue
        if pc == 168:  # 16233: v1[(0x5d - v35)].B = v0[2].B
            v1[(0x5d - v35)].B = v0[2].B; pc = 169; continue
        if pc == 169:  # 1624F: v1[(0x73 - v35)].R = v0[2].R
            v1[(0x73 - v35)].R = v0[2].R; pc = 170; continue
        if pc == 170:  # 1626B: v1[(0x73 - v35)].G = v0[2].G
            v1[(0x73 - v35)].G = v0[2].G; pc = 171; continue
        if pc == 171:  # 16287: v1[(0x73 - v35)].B = v0[2].B
            v1[(0x73 - v35)].B = v0[2].B; pc = 172; continue
        if pc == 172:  # 162A3: v1[(0x72 - v35)].R = v0[2].R
            v1[(0x72 - v35)].R = v0[2].R; pc = 173; continue
        if pc == 173:  # 162BF: v1[(0x72 - v35)].G = v0[2].G
            v1[(0x72 - v35)].G = v0[2].G; pc = 174; continue
        if pc == 174:  # 162DB: v1[(0x72 - v35)].B = v0[2].B
            v1[(0x72 - v35)].B = v0[2].B; pc = 175; continue
        if pc == 175:  # 162FD: v1[((0xa - v32) + v35)].R = v0[2].R
            v1[((0xa - v32) + v35)].R = v0[2].R; pc = 176; continue
        if pc == 176:  # 1631F: v1[((0xa - v32) + v35)].G = v0[2].G
            v1[((0xa - v32) + v35)].G = v0[2].G; pc = 177; continue
        if pc == 177:  # 16341: v1[((0xa - v32) + v35)].B = v0[2].B
            v1[((0xa - v32) + v35)].B = v0[2].B; pc = 178; continue
        if pc == 178:  # 16363: v1[((9 - v32) + v35)].R = v0[2].R
            v1[((9 - v32) + v35)].R = v0[2].R; pc = 179; continue
        if pc == 179:  # 16385: v1[((9 - v32) + v35)].G = v0[2].G
            v1[((9 - v32) + v35)].G = v0[2].G; pc = 180; continue
        if pc == 180:  # 163A7: v1[((9 - v32) + v35)].B = v0[2].B
            v1[((9 - v32) + v35)].B = v0[2].B; pc = 181; continue
        if pc == 181:  # 163C9: v1[((0x1f - v32) + v35)].R = v0[2].R
            v1[((0x1f - v32) + v35)].R = v0[2].R; pc = 182; continue
        if pc == 182:  # 163EB: v1[((0x1f - v32) + v35)].G = v0[2].G
            v1[((0x1f - v32) + v35)].G = v0[2].G; pc = 183; continue
        if pc == 183:  # 1640D: v1[((0x1f - v32) + v35)].B = v0[2].B
            v1[((0x1f - v32) + v35)].B = v0[2].B; pc = 184; continue
        if pc == 184:  # 1642F: v1[((0x1e - v32) + v35)].R = v0[2].R
            v1[((0x1e - v32) + v35)].R = v0[2].R; pc = 185; continue
        if pc == 185:  # 16451: v1[((0x1e - v32) + v35)].G = v0[2].G
            v1[((0x1e - v32) + v35)].G = v0[2].G; pc = 186; continue
        if pc == 186:  # 16473: v1[((0x1e - v32) + v35)].B = v0[2].B
            v1[((0x1e - v32) + v35)].B = v0[2].B; pc = 187; continue
        if pc == 187:  # 16495: v1[((0x34 - v32) + v35)].R = v0[2].R
            v1[((0x34 - v32) + v35)].R = v0[2].R; pc = 188; continue
        if pc == 188:  # 164B7: v1[((0x34 - v32) + v35)].G = v0[2].G
            v1[((0x34 - v32) + v35)].G = v0[2].G; pc = 189; continue
        if pc == 189:  # 164D9: v1[((0x34 - v32) + v35)].B = v0[2].B
            v1[((0x34 - v32) + v35)].B = v0[2].B; pc = 190; continue
        if pc == 190:  # 164FB: v1[((0x33 - v32) + v35)].R = v0[2].R
            v1[((0x33 - v32) + v35)].R = v0[2].R; pc = 191; continue
        if pc == 191:  # 1651D: v1[((0x33 - v32) + v35)].G = v0[2].G
            v1[((0x33 - v32) + v35)].G = v0[2].G; pc = 192; continue
        if pc == 192:  # 1653F: v1[((0x33 - v32) + v35)].B = v0[2].B
            v1[((0x33 - v32) + v35)].B = v0[2].B; pc = 193; continue
        if pc == 193:  # 16561: v1[((0x49 - v32) + v35)].R = v0[2].R
            v1[((0x49 - v32) + v35)].R = v0[2].R; pc = 194; continue
        if pc == 194:  # 16583: v1[((0x49 - v32) + v35)].G = v0[2].G
            v1[((0x49 - v32) + v35)].G = v0[2].G; pc = 195; continue
        if pc == 195:  # 165A5: v1[((0x49 - v32) + v35)].B = v0[2].B
            v1[((0x49 - v32) + v35)].B = v0[2].B; pc = 196; continue
        if pc == 196:  # 165C7: v1[((0x48 - v32) + v35)].R = v0[2].R
            v1[((0x48 - v32) + v35)].R = v0[2].R; pc = 197; continue
        if pc == 197:  # 165E9: v1[((0x48 - v32) + v35)].G = v0[2].G
            v1[((0x48 - v32) + v35)].G = v0[2].G; pc = 198; continue
        if pc == 198:  # 1660B: v1[((0x48 - v32) + v35)].B = v0[2].B
            v1[((0x48 - v32) + v35)].B = v0[2].B; pc = 199; continue
        if pc == 199:  # 1662D: v1[((0x5e - v32) + v35)].R = v0[2].R
            v1[((0x5e - v32) + v35)].R = v0[2].R; pc = 200; continue
        if pc == 200:  # 1664F: v1[((0x5e - v32) + v35)].G = v0[2].G
            v1[((0x5e - v32) + v35)].G = v0[2].G; pc = 201; continue
        if pc == 201:  # 16671: v1[((0x5e - v32) + v35)].B = v0[2].B
            v1[((0x5e - v32) + v35)].B = v0[2].B; pc = 202; continue
        if pc == 202:  # 16693: v1[((0x5d - v32) + v35)].R = v0[2].R
            v1[((0x5d - v32) + v35)].R = v0[2].R; pc = 203; continue
        if pc == 203:  # 166B5: v1[((0x5d - v32) + v35)].G = v0[2].G
            v1[((0x5d - v32) + v35)].G = v0[2].G; pc = 204; continue
        if pc == 204:  # 166D7: v1[((0x5d - v32) + v35)].B = v0[2].B
            v1[((0x5d - v32) + v35)].B = v0[2].B; pc = 205; continue
        if pc == 205:  # 166F9: v1[((0x73 - v32) + v35)].R = v0[2].R
            v1[((0x73 - v32) + v35)].R = v0[2].R; pc = 206; continue
        if pc == 206:  # 1671B: v1[((0x73 - v32) + v35)].G = v0[2].G
            v1[((0x73 - v32) + v35)].G = v0[2].G; pc = 207; continue
        if pc == 207:  # 1673D: v1[((0x73 - v32) + v35)].B = v0[2].B
            v1[((0x73 - v32) + v35)].B = v0[2].B; pc = 208; continue
        if pc == 208:  # 1675F: v1[((0x72 - v32) + v35)].R = v0[2].R
            v1[((0x72 - v32) + v35)].R = v0[2].R; pc = 209; continue
        if pc == 209:  # 16781: v1[((0x72 - v32) + v35)].G = v0[2].G
            v1[((0x72 - v32) + v35)].G = v0[2].G; pc = 210; continue
        if pc == 210:  # 167A3: v1[((0x72 - v32) + v35)].B = v0[2].B
            v1[((0x72 - v32) + v35)].B = v0[2].B; pc = 211; continue
        if pc == 211:  # 167BC: this.Set_ITE_Effect_Type_UserMode(this.m_ap_effect_data.save_light, 0, v1, v3)
            ctx.user_mode(v1, v3); pc = 212; continue
        if pc == 212:  # 167CB: Thread.Sleep((0x14 * this.m_ap_effect_data.save_speed))
            if not ctx.sleep((0x14 * ctx.speed)): return
            pc = 213; continue
        if pc == 213:  # 167D4: v4 = (v4 + 1)
            v4 = (v4 + 1); pc = 214; continue
        if pc == 214:  # 167E3: if (this.m_ap_effect_data.save_effect == 0xd) goto 19CF4
            pc = 1400 if (ctx.effect == 0xd) else 215; continue
        if pc == 215:  # 167E9: v4 = 0
            v4 = 0; pc = 216; continue
        if pc == 216:  # 167EB: goto 19CF4
            pc = 1400; continue
        if pc == 217:  # 167FD: if (this.m_ap_effect_data.save_effect != 0xc) goto 19CF4
            pc = 1400 if (ctx.effect != 0xc) else 218; continue
        if pc == 218:  # 16824: v0[0].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].R
            v0[0].R = CB[0].R; pc = 219; continue
        if pc == 219:  # 1684B: v0[0].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].G
            v0[0].G = CB[0].G; pc = 220; continue
        if pc == 220:  # 16872: v0[0].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[0].B
            v0[0].B = CB[0].B; pc = 221; continue
        if pc == 221:  # 16899: v0[1].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].R
            v0[1].R = CB[1].R; pc = 222; continue
        if pc == 222:  # 168C0: v0[1].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].G
            v0[1].G = CB[1].G; pc = 223; continue
        if pc == 223:  # 168E7: v0[1].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[1].B
            v0[1].B = CB[1].B; pc = 224; continue
        if pc == 224:  # 1690E: v0[2].R = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].R
            v0[2].R = CB[2].R; pc = 225; continue
        if pc == 225:  # 16935: v0[2].G = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].G
            v0[2].G = CB[2].G; pc = 226; continue
        if pc == 226:  # 1695C: v0[2].B = this.m_ap_effect_data.save_layout_color.ColorBuffer[2].B
            v0[2].B = CB[2].B; pc = 227; continue
        if pc == 227:  # 16962: v42 = 0
            v42 = 0; pc = 228; continue
        if pc == 228:  # 16964: goto 169A5
            pc = 234; continue
        if pc == 229:  # 16970: v1[v42].ID = v42
            v1[v42].ID = v42; pc = 230; continue
        if pc == 230:  # 1697E: v1[v42].R = 0
            v1[v42].R = 0; pc = 231; continue
        if pc == 231:  # 1698C: v1[v42].G = 0
            v1[v42].G = 0; pc = 232; continue
        if pc == 232:  # 1699A: v1[v42].B = 0
            v1[v42].B = 0; pc = 233; continue
        if pc == 233:  # 169A3: v42 = (v42 + 1)
            v42 = (v42 + 1); pc = 234; continue
        if pc == 234:  # 169A9: if (v42 < 0x7e) goto 16966
            pc = 229 if (v42 < 0x7e) else 235; continue
        if pc == 235:  # 169AD: v36 = 0xf
            v36 = 0xf; pc = 236; continue
        if pc == 236:  # 169B5: if (!this.ColRightShift) goto 169D0
            pc = 238 if (not 0) else 237; continue
        if pc == 237:  # 169CE: v36 = (0xf - Convert.ToUInt32((this.ColRightShift + 1)))
            v36 = (0xf - ((0 + 1))); pc = 238; continue
        if pc == 238:  # 169D5: v37 = (v4 % v36)
            v37 = (v4 % v36); pc = 239; continue
        if pc == 239:  # 169DC: v38 = (v4 / 0xf)
            v38 = (v4 // 0xf); pc = 240; continue
        if pc == 240:  # 169EB: v39 = v0[v38].R
            v39 = v0[v38].R; pc = 241; continue
        if pc == 241:  # 169FA: v40 = v0[v38].G
            v40 = v0[v38].G; pc = 242; continue
        if pc == 242:  # 16A09: v41 = v0[v38].B
            v41 = v0[v38].B; pc = 243; continue
        if pc == 243:  # 16A1C: v1[(0x34 - this.ColShift)].R = v39
            v1[(0x34 - 0)].R = v39; pc = 244; continue
        if pc == 244:  # 16A32: v1[(0x34 - this.ColShift)].G = v40
            v1[(0x34 - 0)].G = v40; pc = 245; continue
        if pc == 245:  # 16A48: v1[(0x34 - this.ColShift)].B = v41
            v1[(0x34 - 0)].B = v41; pc = 246; continue
        if pc == 246:  # 16A4F: switch (v37) [92821, 93021, 93521, 94408, 95553, 96827, 98101, 99375, 100649, 101923, 103200, 104273, 105034, 
            _t = [248, 267, 310, 389, 492, 607, 722, 837, 952, 1067, 1182, 1279, 1346, 1377, 1390]; pc = _t[v37] if 0 <= v37 < len(_t) else 247; continue
        if pc == 247:  # 16A90: goto 19CA9
            pc = 1393; continue
        if pc == 248:  # 16AA7: v43 = v39
            v43 = v39; pc = 249; continue
        if pc == 249:  # 16AA9: v1[0x69].R = v39
            v1[0x69].R = v39; pc = 250; continue
        if pc == 250:  # 16AB0: v1[0].R = v43
            v1[0].R = v43; pc = 251; continue
        if pc == 251:  # 16AC7: v43 = v40
            v43 = v40; pc = 252; continue
        if pc == 252:  # 16AC9: v1[0x69].G = v40
            v1[0x69].G = v40; pc = 253; continue
        if pc == 253:  # 16AD0: v1[0].G = v43
            v1[0].G = v43; pc = 254; continue
        if pc == 254:  # 16AE7: v43 = v41
            v43 = v41; pc = 255; continue
        if pc == 255:  # 16AE9: v1[0x69].B = v41
            v1[0x69].B = v41; pc = 256; continue
        if pc == 256:  # 16AF0: v1[0].B = v43
            v1[0].B = v43; pc = 257; continue
        if pc == 257:  # 16B08: v43 = v39
            v43 = v39; pc = 258; continue
        if pc == 258:  # 16B0A: v1[0x7d].R = v39
            v1[0x7d].R = v39; pc = 259; continue
        if pc == 259:  # 16B11: v1[0x14].R = v43
            v1[0x14].R = v43; pc = 260; continue
        if pc == 260:  # 16B29: v43 = v40
            v43 = v40; pc = 261; continue
        if pc == 261:  # 16B2B: v1[0x7d].G = v40
            v1[0x7d].G = v40; pc = 262; continue
        if pc == 262:  # 16B32: v1[0x14].G = v43
            v1[0x14].G = v43; pc = 263; continue
        if pc == 263:  # 16B4A: v43 = v41
            v43 = v41; pc = 264; continue
        if pc == 264:  # 16B4C: v1[0x7d].B = v41
            v1[0x7d].B = v41; pc = 265; continue
        if pc == 265:  # 16B53: v1[0x14].B = v43
            v1[0x14].B = v43; pc = 266; continue
        if pc == 266:  # 16B58: goto 19CA9
            pc = 1393; continue
        if pc == 267:  # 16B7F: v43 = v39
            v43 = v39; pc = 268; continue
        if pc == 268:  # 16B81: v1[0x6a].R = v39
            v1[0x6a].R = v39; pc = 269; continue
        if pc == 269:  # 16B89: v43 = v43
            v43 = v43; pc = 270; continue
        if pc == 270:  # 16B8B: v1[0x54].R = v43
            v1[0x54].R = v43; pc = 271; continue
        if pc == 271:  # 16B93: v43 = v43
            v43 = v43; pc = 272; continue
        if pc == 272:  # 16B95: v1[0x15].R = v43
            v1[0x15].R = v43; pc = 273; continue
        if pc == 273:  # 16B9C: v1[1].R = v43
            v1[1].R = v43; pc = 274; continue
        if pc == 274:  # 16BC3: v43 = v40
            v43 = v40; pc = 275; continue
        if pc == 275:  # 16BC5: v1[0x6a].G = v40
            v1[0x6a].G = v40; pc = 276; continue
        if pc == 276:  # 16BCD: v43 = v43
            v43 = v43; pc = 277; continue
        if pc == 277:  # 16BCF: v1[0x54].G = v43
            v1[0x54].G = v43; pc = 278; continue
        if pc == 278:  # 16BD7: v43 = v43
            v43 = v43; pc = 279; continue
        if pc == 279:  # 16BD9: v1[0x15].G = v43
            v1[0x15].G = v43; pc = 280; continue
        if pc == 280:  # 16BE0: v1[1].G = v43
            v1[1].G = v43; pc = 281; continue
        if pc == 281:  # 16C07: v43 = v41
            v43 = v41; pc = 282; continue
        if pc == 282:  # 16C09: v1[0x6a].B = v41
            v1[0x6a].B = v41; pc = 283; continue
        if pc == 283:  # 16C11: v43 = v43
            v43 = v43; pc = 284; continue
        if pc == 284:  # 16C13: v1[0x54].B = v43
            v1[0x54].B = v43; pc = 285; continue
        if pc == 285:  # 16C1B: v43 = v43
            v43 = v43; pc = 286; continue
        if pc == 286:  # 16C1D: v1[0x15].B = v43
            v1[0x15].B = v43; pc = 287; continue
        if pc == 287:  # 16C24: v1[1].B = v43
            v1[1].B = v43; pc = 288; continue
        if pc == 288:  # 16C68: v43 = v39
            v43 = v39; pc = 289; continue
        if pc == 289:  # 16C6A: v1[(0x7c - this.ColRightShift)].R = v39
            v1[(0x7c - 0)].R = v39; pc = 290; continue
        if pc == 290:  # 16C72: v43 = v43
            v43 = v43; pc = 291; continue
        if pc == 291:  # 16C74: v1[(0x68 - this.ColRightShift)].R = v43
            v1[(0x68 - 0)].R = v43; pc = 292; continue
        if pc == 292:  # 16C7C: v43 = v43
            v43 = v43; pc = 293; continue
        if pc == 293:  # 16C7E: v1[(0x29 - this.ColRightShift)].R = v43
            v1[(0x29 - 0)].R = v43; pc = 294; continue
        if pc == 294:  # 16C85: v1[(0x13 - this.ColRightShift)].R = v43
            v1[(0x13 - 0)].R = v43; pc = 295; continue
        if pc == 295:  # 16CC9: v43 = v40
            v43 = v40; pc = 296; continue
        if pc == 296:  # 16CCB: v1[(0x7c - this.ColRightShift)].G = v40
            v1[(0x7c - 0)].G = v40; pc = 297; continue
        if pc == 297:  # 16CD3: v43 = v43
            v43 = v43; pc = 298; continue
        if pc == 298:  # 16CD5: v1[(0x68 - this.ColRightShift)].G = v43
            v1[(0x68 - 0)].G = v43; pc = 299; continue
        if pc == 299:  # 16CDD: v43 = v43
            v43 = v43; pc = 300; continue
        if pc == 300:  # 16CDF: v1[(0x29 - this.ColRightShift)].G = v43
            v1[(0x29 - 0)].G = v43; pc = 301; continue
        if pc == 301:  # 16CE6: v1[(0x13 - this.ColRightShift)].G = v43
            v1[(0x13 - 0)].G = v43; pc = 302; continue
        if pc == 302:  # 16D2A: v43 = v41
            v43 = v41; pc = 303; continue
        if pc == 303:  # 16D2C: v1[(0x7c - this.ColRightShift)].B = v41
            v1[(0x7c - 0)].B = v41; pc = 304; continue
        if pc == 304:  # 16D34: v43 = v43
            v43 = v43; pc = 305; continue
        if pc == 305:  # 16D36: v1[(0x68 - this.ColRightShift)].B = v43
            v1[(0x68 - 0)].B = v43; pc = 306; continue
        if pc == 306:  # 16D3E: v43 = v43
            v43 = v43; pc = 307; continue
        if pc == 307:  # 16D40: v1[(0x29 - this.ColRightShift)].B = v43
            v1[(0x29 - 0)].B = v43; pc = 308; continue
        if pc == 308:  # 16D47: v1[(0x13 - this.ColRightShift)].B = v43
            v1[(0x13 - 0)].B = v43; pc = 309; continue
        if pc == 309:  # 16D4C: goto 19CA9
            pc = 1393; continue
        if pc == 310:  # 16D8B: v43 = v39
            v43 = v39; pc = 311; continue
        if pc == 311:  # 16D8D: v1[0x6b].R = v39
            v1[0x6b].R = v39; pc = 312; continue
        if pc == 312:  # 16D95: v43 = v43
            v43 = v43; pc = 313; continue
        if pc == 313:  # 16D97: v1[0x55].R = v43
            v1[0x55].R = v43; pc = 314; continue
        if pc == 314:  # 16D9F: v43 = v43
            v43 = v43; pc = 315; continue
        if pc == 315:  # 16DA1: v1[0x54].R = v43
            v1[0x54].R = v43; pc = 316; continue
        if pc == 316:  # 16DA9: v43 = v43
            v43 = v43; pc = 317; continue
        if pc == 317:  # 16DAB: v1[0x3f].R = v43
            v1[0x3f].R = v43; pc = 318; continue
        if pc == 318:  # 16DB3: v43 = v43
            v43 = v43; pc = 319; continue
        if pc == 319:  # 16DB5: v1[0x16].R = v43
            v1[0x16].R = v43; pc = 320; continue
        if pc == 320:  # 16DBD: v43 = v43
            v43 = v43; pc = 321; continue
        if pc == 321:  # 16DBF: v1[0x15].R = v43
            v1[0x15].R = v43; pc = 322; continue
        if pc == 322:  # 16DC6: v1[2].R = v43
            v1[2].R = v43; pc = 323; continue
        if pc == 323:  # 16E05: v43 = v40
            v43 = v40; pc = 324; continue
        if pc == 324:  # 16E07: v1[0x6b].G = v40
            v1[0x6b].G = v40; pc = 325; continue
        if pc == 325:  # 16E0F: v43 = v43
            v43 = v43; pc = 326; continue
        if pc == 326:  # 16E11: v1[0x55].G = v43
            v1[0x55].G = v43; pc = 327; continue
        if pc == 327:  # 16E19: v43 = v43
            v43 = v43; pc = 328; continue
        if pc == 328:  # 16E1B: v1[0x54].G = v43
            v1[0x54].G = v43; pc = 329; continue
        if pc == 329:  # 16E23: v43 = v43
            v43 = v43; pc = 330; continue
        if pc == 330:  # 16E25: v1[0x3f].G = v43
            v1[0x3f].G = v43; pc = 331; continue
        if pc == 331:  # 16E2D: v43 = v43
            v43 = v43; pc = 332; continue
        if pc == 332:  # 16E2F: v1[0x16].G = v43
            v1[0x16].G = v43; pc = 333; continue
        if pc == 333:  # 16E37: v43 = v43
            v43 = v43; pc = 334; continue
        if pc == 334:  # 16E39: v1[0x15].G = v43
            v1[0x15].G = v43; pc = 335; continue
        if pc == 335:  # 16E40: v1[2].G = v43
            v1[2].G = v43; pc = 336; continue
        if pc == 336:  # 16E7F: v43 = v41
            v43 = v41; pc = 337; continue
        if pc == 337:  # 16E81: v1[0x6b].B = v41
            v1[0x6b].B = v41; pc = 338; continue
        if pc == 338:  # 16E89: v43 = v43
            v43 = v43; pc = 339; continue
        if pc == 339:  # 16E8B: v1[0x55].B = v43
            v1[0x55].B = v43; pc = 340; continue
        if pc == 340:  # 16E93: v43 = v43
            v43 = v43; pc = 341; continue
        if pc == 341:  # 16E95: v1[0x54].B = v43
            v1[0x54].B = v43; pc = 342; continue
        if pc == 342:  # 16E9D: v43 = v43
            v43 = v43; pc = 343; continue
        if pc == 343:  # 16E9F: v1[0x3f].B = v43
            v1[0x3f].B = v43; pc = 344; continue
        if pc == 344:  # 16EA7: v43 = v43
            v43 = v43; pc = 345; continue
        if pc == 345:  # 16EA9: v1[0x16].B = v43
            v1[0x16].B = v43; pc = 346; continue
        if pc == 346:  # 16EB1: v43 = v43
            v43 = v43; pc = 347; continue
        if pc == 347:  # 16EB3: v1[0x15].B = v43
            v1[0x15].B = v43; pc = 348; continue
        if pc == 348:  # 16EBA: v1[2].B = v43
            v1[2].B = v43; pc = 349; continue
        if pc == 349:  # 16F2B: v43 = v39
            v43 = v39; pc = 350; continue
        if pc == 350:  # 16F2D: v1[(0x7b - this.ColRightShift)].R = v39
            v1[(0x7b - 0)].R = v39; pc = 351; continue
        if pc == 351:  # 16F35: v43 = v43
            v43 = v43; pc = 352; continue
        if pc == 352:  # 16F37: v1[(0x68 - this.ColRightShift)].R = v43
            v1[(0x68 - 0)].R = v43; pc = 353; continue
        if pc == 353:  # 16F3F: v43 = v43
            v43 = v43; pc = 354; continue
        if pc == 354:  # 16F41: v1[(0x67 - this.ColRightShift)].R = v43
            v1[(0x67 - 0)].R = v43; pc = 355; continue
        if pc == 355:  # 16F49: v43 = v43
            v43 = v43; pc = 356; continue
        if pc == 356:  # 16F4B: v1[(0x53 - this.ColRightShift)].R = v43
            v1[(0x53 - 0)].R = v43; pc = 357; continue
        if pc == 357:  # 16F53: v43 = v43
            v43 = v43; pc = 358; continue
        if pc == 358:  # 16F55: v1[(0x29 - this.ColRightShift)].R = v43
            v1[(0x29 - 0)].R = v43; pc = 359; continue
        if pc == 359:  # 16F5D: v43 = v43
            v43 = v43; pc = 360; continue
        if pc == 360:  # 16F5F: v1[(0x28 - this.ColRightShift)].R = v43
            v1[(0x28 - 0)].R = v43; pc = 361; continue
        if pc == 361:  # 16F66: v1[(0x12 - this.ColRightShift)].R = v43
            v1[(0x12 - 0)].R = v43; pc = 362; continue
        if pc == 362:  # 16FD7: v43 = v40
            v43 = v40; pc = 363; continue
        if pc == 363:  # 16FD9: v1[(0x7b - this.ColRightShift)].G = v40
            v1[(0x7b - 0)].G = v40; pc = 364; continue
        if pc == 364:  # 16FE1: v43 = v43
            v43 = v43; pc = 365; continue
        if pc == 365:  # 16FE3: v1[(0x68 - this.ColRightShift)].G = v43
            v1[(0x68 - 0)].G = v43; pc = 366; continue
        if pc == 366:  # 16FEB: v43 = v43
            v43 = v43; pc = 367; continue
        if pc == 367:  # 16FED: v1[(0x67 - this.ColRightShift)].G = v43
            v1[(0x67 - 0)].G = v43; pc = 368; continue
        if pc == 368:  # 16FF5: v43 = v43
            v43 = v43; pc = 369; continue
        if pc == 369:  # 16FF7: v1[(0x53 - this.ColRightShift)].G = v43
            v1[(0x53 - 0)].G = v43; pc = 370; continue
        if pc == 370:  # 16FFF: v43 = v43
            v43 = v43; pc = 371; continue
        if pc == 371:  # 17001: v1[(0x29 - this.ColRightShift)].G = v43
            v1[(0x29 - 0)].G = v43; pc = 372; continue
        if pc == 372:  # 17009: v43 = v43
            v43 = v43; pc = 373; continue
        if pc == 373:  # 1700B: v1[(0x28 - this.ColRightShift)].G = v43
            v1[(0x28 - 0)].G = v43; pc = 374; continue
        if pc == 374:  # 17012: v1[(0x12 - this.ColRightShift)].G = v43
            v1[(0x12 - 0)].G = v43; pc = 375; continue
        if pc == 375:  # 17083: v43 = v41
            v43 = v41; pc = 376; continue
        if pc == 376:  # 17085: v1[(0x7b - this.ColRightShift)].B = v41
            v1[(0x7b - 0)].B = v41; pc = 377; continue
        if pc == 377:  # 1708D: v43 = v43
            v43 = v43; pc = 378; continue
        if pc == 378:  # 1708F: v1[(0x68 - this.ColRightShift)].B = v43
            v1[(0x68 - 0)].B = v43; pc = 379; continue
        if pc == 379:  # 17097: v43 = v43
            v43 = v43; pc = 380; continue
        if pc == 380:  # 17099: v1[(0x67 - this.ColRightShift)].B = v43
            v1[(0x67 - 0)].B = v43; pc = 381; continue
        if pc == 381:  # 170A1: v43 = v43
            v43 = v43; pc = 382; continue
        if pc == 382:  # 170A3: v1[(0x53 - this.ColRightShift)].B = v43
            v1[(0x53 - 0)].B = v43; pc = 383; continue
        if pc == 383:  # 170AB: v43 = v43
            v43 = v43; pc = 384; continue
        if pc == 384:  # 170AD: v1[(0x29 - this.ColRightShift)].B = v43
            v1[(0x29 - 0)].B = v43; pc = 385; continue
        if pc == 385:  # 170B5: v43 = v43
            v43 = v43; pc = 386; continue
        if pc == 386:  # 170B7: v1[(0x28 - this.ColRightShift)].B = v43
            v1[(0x28 - 0)].B = v43; pc = 387; continue
        if pc == 387:  # 170BE: v1[(0x12 - this.ColRightShift)].B = v43
            v1[(0x12 - 0)].B = v43; pc = 388; continue
        if pc == 388:  # 170C3: goto 19CA9
            pc = 1393; continue
        if pc == 389:  # 17112: v43 = v39
            v43 = v39; pc = 390; continue
        if pc == 390:  # 17114: v1[0x6c].R = v39
            v1[0x6c].R = v39; pc = 391; continue
        if pc == 391:  # 1711C: v43 = v43
            v43 = v43; pc = 392; continue
        if pc == 392:  # 1711E: v1[0x56].R = v43
            v1[0x56].R = v43; pc = 393; continue
        if pc == 393:  # 17126: v43 = v43
            v43 = v43; pc = 394; continue
        if pc == 394:  # 17128: v1[0x55].R = v43
            v1[0x55].R = v43; pc = 395; continue
        if pc == 395:  # 17130: v43 = v43
            v43 = v43; pc = 396; continue
        if pc == 396:  # 17132: v1[0x40].R = v43
            v1[0x40].R = v43; pc = 397; continue
        if pc == 397:  # 1713A: v43 = v43
            v43 = v43; pc = 398; continue
        if pc == 398:  # 1713C: v1[0x3f].R = v43
            v1[0x3f].R = v43; pc = 399; continue
        if pc == 399:  # 17144: v43 = v43
            v43 = v43; pc = 400; continue
        if pc == 400:  # 17146: v1[0x2a].R = v43
            v1[0x2a].R = v43; pc = 401; continue
        if pc == 401:  # 1714E: v43 = v43
            v43 = v43; pc = 402; continue
        if pc == 402:  # 17150: v1[0x17].R = v43
            v1[0x17].R = v43; pc = 403; continue
        if pc == 403:  # 17158: v43 = v43
            v43 = v43; pc = 404; continue
        if pc == 404:  # 1715A: v1[0x16].R = v43
            v1[0x16].R = v43; pc = 405; continue
        if pc == 405:  # 17161: v1[3].R = v43
            v1[3].R = v43; pc = 406; continue
        if pc == 406:  # 171B0: v43 = v40
            v43 = v40; pc = 407; continue
        if pc == 407:  # 171B2: v1[0x6c].G = v40
            v1[0x6c].G = v40; pc = 408; continue
        if pc == 408:  # 171BA: v43 = v43
            v43 = v43; pc = 409; continue
        if pc == 409:  # 171BC: v1[0x56].G = v43
            v1[0x56].G = v43; pc = 410; continue
        if pc == 410:  # 171C4: v43 = v43
            v43 = v43; pc = 411; continue
        if pc == 411:  # 171C6: v1[0x55].G = v43
            v1[0x55].G = v43; pc = 412; continue
        if pc == 412:  # 171CE: v43 = v43
            v43 = v43; pc = 413; continue
        if pc == 413:  # 171D0: v1[0x40].G = v43
            v1[0x40].G = v43; pc = 414; continue
        if pc == 414:  # 171D8: v43 = v43
            v43 = v43; pc = 415; continue
        if pc == 415:  # 171DA: v1[0x3f].G = v43
            v1[0x3f].G = v43; pc = 416; continue
        if pc == 416:  # 171E2: v43 = v43
            v43 = v43; pc = 417; continue
        if pc == 417:  # 171E4: v1[0x2a].G = v43
            v1[0x2a].G = v43; pc = 418; continue
        if pc == 418:  # 171EC: v43 = v43
            v43 = v43; pc = 419; continue
        if pc == 419:  # 171EE: v1[0x17].G = v43
            v1[0x17].G = v43; pc = 420; continue
        if pc == 420:  # 171F6: v43 = v43
            v43 = v43; pc = 421; continue
        if pc == 421:  # 171F8: v1[0x16].G = v43
            v1[0x16].G = v43; pc = 422; continue
        if pc == 422:  # 171FF: v1[3].G = v43
            v1[3].G = v43; pc = 423; continue
        if pc == 423:  # 1724E: v43 = v41
            v43 = v41; pc = 424; continue
        if pc == 424:  # 17250: v1[0x6c].B = v41
            v1[0x6c].B = v41; pc = 425; continue
        if pc == 425:  # 17258: v43 = v43
            v43 = v43; pc = 426; continue
        if pc == 426:  # 1725A: v1[0x56].B = v43
            v1[0x56].B = v43; pc = 427; continue
        if pc == 427:  # 17262: v43 = v43
            v43 = v43; pc = 428; continue
        if pc == 428:  # 17264: v1[0x55].B = v43
            v1[0x55].B = v43; pc = 429; continue
        if pc == 429:  # 1726C: v43 = v43
            v43 = v43; pc = 430; continue
        if pc == 430:  # 1726E: v1[0x40].B = v43
            v1[0x40].B = v43; pc = 431; continue
        if pc == 431:  # 17276: v43 = v43
            v43 = v43; pc = 432; continue
        if pc == 432:  # 17278: v1[0x3f].B = v43
            v1[0x3f].B = v43; pc = 433; continue
        if pc == 433:  # 17280: v43 = v43
            v43 = v43; pc = 434; continue
        if pc == 434:  # 17282: v1[0x2a].B = v43
            v1[0x2a].B = v43; pc = 435; continue
        if pc == 435:  # 1728A: v43 = v43
            v43 = v43; pc = 436; continue
        if pc == 436:  # 1728C: v1[0x17].B = v43
            v1[0x17].B = v43; pc = 437; continue
        if pc == 437:  # 17294: v43 = v43
            v43 = v43; pc = 438; continue
        if pc == 438:  # 17296: v1[0x16].B = v43
            v1[0x16].B = v43; pc = 439; continue
        if pc == 439:  # 1729D: v1[3].B = v43
            v1[3].B = v43; pc = 440; continue
        if pc == 440:  # 1732C: v43 = v39
            v43 = v39; pc = 441; continue
        if pc == 441:  # 1732E: v1[(0x7a - this.ColRightShift)].R = v39
            v1[(0x7a - 0)].R = v39; pc = 442; continue
        if pc == 442:  # 17336: v43 = v43
            v43 = v43; pc = 443; continue
        if pc == 443:  # 17338: v1[(0x67 - this.ColRightShift)].R = v43
            v1[(0x67 - 0)].R = v43; pc = 444; continue
        if pc == 444:  # 17340: v43 = v43
            v43 = v43; pc = 445; continue
        if pc == 445:  # 17342: v1[(0x66 - this.ColRightShift)].R = v43
            v1[(0x66 - 0)].R = v43; pc = 446; continue
        if pc == 446:  # 1734A: v43 = v43
            v43 = v43; pc = 447; continue
        if pc == 447:  # 1734C: v1[(0x53 - this.ColRightShift)].R = v43
            v1[(0x53 - 0)].R = v43; pc = 448; continue
        if pc == 448:  # 17354: v43 = v43
            v43 = v43; pc = 449; continue
        if pc == 449:  # 17356: v1[(0x52 - this.ColRightShift)].R = v43
            v1[(0x52 - 0)].R = v43; pc = 450; continue
        if pc == 450:  # 1735E: v43 = v43
            v43 = v43; pc = 451; continue
        if pc == 451:  # 17360: v1[(0x3e - this.ColRightShift)].R = v43
            v1[(0x3e - 0)].R = v43; pc = 452; continue
        if pc == 452:  # 17368: v43 = v43
            v43 = v43; pc = 453; continue
        if pc == 453:  # 1736A: v1[(0x27 - this.ColRightShift)].R = v43
            v1[(0x27 - 0)].R = v43; pc = 454; continue
        if pc == 454:  # 17372: v43 = v43
            v43 = v43; pc = 455; continue
        if pc == 455:  # 17374: v1[(0x26 - this.ColRightShift)].R = v43
            v1[(0x26 - 0)].R = v43; pc = 456; continue
        if pc == 456:  # 1737B: v1[(0x11 - this.ColRightShift)].R = v43
            v1[(0x11 - 0)].R = v43; pc = 457; continue
        if pc == 457:  # 1740A: v43 = v40
            v43 = v40; pc = 458; continue
        if pc == 458:  # 1740C: v1[(0x7a - this.ColRightShift)].G = v40
            v1[(0x7a - 0)].G = v40; pc = 459; continue
        if pc == 459:  # 17414: v43 = v43
            v43 = v43; pc = 460; continue
        if pc == 460:  # 17416: v1[(0x67 - this.ColRightShift)].G = v43
            v1[(0x67 - 0)].G = v43; pc = 461; continue
        if pc == 461:  # 1741E: v43 = v43
            v43 = v43; pc = 462; continue
        if pc == 462:  # 17420: v1[(0x66 - this.ColRightShift)].G = v43
            v1[(0x66 - 0)].G = v43; pc = 463; continue
        if pc == 463:  # 17428: v43 = v43
            v43 = v43; pc = 464; continue
        if pc == 464:  # 1742A: v1[(0x53 - this.ColRightShift)].G = v43
            v1[(0x53 - 0)].G = v43; pc = 465; continue
        if pc == 465:  # 17432: v43 = v43
            v43 = v43; pc = 466; continue
        if pc == 466:  # 17434: v1[(0x52 - this.ColRightShift)].G = v43
            v1[(0x52 - 0)].G = v43; pc = 467; continue
        if pc == 467:  # 1743C: v43 = v43
            v43 = v43; pc = 468; continue
        if pc == 468:  # 1743E: v1[(0x3e - this.ColRightShift)].G = v43
            v1[(0x3e - 0)].G = v43; pc = 469; continue
        if pc == 469:  # 17446: v43 = v43
            v43 = v43; pc = 470; continue
        if pc == 470:  # 17448: v1[(0x27 - this.ColRightShift)].G = v43
            v1[(0x27 - 0)].G = v43; pc = 471; continue
        if pc == 471:  # 17450: v43 = v43
            v43 = v43; pc = 472; continue
        if pc == 472:  # 17452: v1[(0x26 - this.ColRightShift)].G = v43
            v1[(0x26 - 0)].G = v43; pc = 473; continue
        if pc == 473:  # 17459: v1[(0x11 - this.ColRightShift)].G = v43
            v1[(0x11 - 0)].G = v43; pc = 474; continue
        if pc == 474:  # 174E8: v43 = v41
            v43 = v41; pc = 475; continue
        if pc == 475:  # 174EA: v1[(0x7a - this.ColRightShift)].B = v41
            v1[(0x7a - 0)].B = v41; pc = 476; continue
        if pc == 476:  # 174F2: v43 = v43
            v43 = v43; pc = 477; continue
        if pc == 477:  # 174F4: v1[(0x67 - this.ColRightShift)].B = v43
            v1[(0x67 - 0)].B = v43; pc = 478; continue
        if pc == 478:  # 174FC: v43 = v43
            v43 = v43; pc = 479; continue
        if pc == 479:  # 174FE: v1[(0x66 - this.ColRightShift)].B = v43
            v1[(0x66 - 0)].B = v43; pc = 480; continue
        if pc == 480:  # 17506: v43 = v43
            v43 = v43; pc = 481; continue
        if pc == 481:  # 17508: v1[(0x53 - this.ColRightShift)].B = v43
            v1[(0x53 - 0)].B = v43; pc = 482; continue
        if pc == 482:  # 17510: v43 = v43
            v43 = v43; pc = 483; continue
        if pc == 483:  # 17512: v1[(0x52 - this.ColRightShift)].B = v43
            v1[(0x52 - 0)].B = v43; pc = 484; continue
        if pc == 484:  # 1751A: v43 = v43
            v43 = v43; pc = 485; continue
        if pc == 485:  # 1751C: v1[(0x3e - this.ColRightShift)].B = v43
            v1[(0x3e - 0)].B = v43; pc = 486; continue
        if pc == 486:  # 17524: v43 = v43
            v43 = v43; pc = 487; continue
        if pc == 487:  # 17526: v1[(0x27 - this.ColRightShift)].B = v43
            v1[(0x27 - 0)].B = v43; pc = 488; continue
        if pc == 488:  # 1752E: v43 = v43
            v43 = v43; pc = 489; continue
        if pc == 489:  # 17530: v1[(0x26 - this.ColRightShift)].B = v43
            v1[(0x26 - 0)].B = v43; pc = 490; continue
        if pc == 490:  # 17537: v1[(0x11 - this.ColRightShift)].B = v43
            v1[(0x11 - 0)].B = v43; pc = 491; continue
        if pc == 491:  # 1753C: goto 19CA9
            pc = 1393; continue
        if pc == 492:  # 17593: v43 = v39
            v43 = v39; pc = 493; continue
        if pc == 493:  # 17595: v1[0x6d].R = v39
            v1[0x6d].R = v39; pc = 494; continue
        if pc == 494:  # 1759D: v43 = v43
            v43 = v43; pc = 495; continue
        if pc == 495:  # 1759F: v1[0x57].R = v43
            v1[0x57].R = v43; pc = 496; continue
        if pc == 496:  # 175A7: v43 = v43
            v43 = v43; pc = 497; continue
        if pc == 497:  # 175A9: v1[0x56].R = v43
            v1[0x56].R = v43; pc = 498; continue
        if pc == 498:  # 175B1: v43 = v43
            v43 = v43; pc = 499; continue
        if pc == 499:  # 175B3: v1[0x41].R = v43
            v1[0x41].R = v43; pc = 500; continue
        if pc == 500:  # 175BB: v43 = v43
            v43 = v43; pc = 501; continue
        if pc == 501:  # 175BD: v1[0x40].R = v43
            v1[0x40].R = v43; pc = 502; continue
        if pc == 502:  # 175C5: v43 = v43
            v43 = v43; pc = 503; continue
        if pc == 503:  # 175C7: v1[0x2b].R = v43
            v1[0x2b].R = v43; pc = 504; continue
        if pc == 504:  # 175CF: v43 = v43
            v43 = v43; pc = 505; continue
        if pc == 505:  # 175D1: v1[0x2a].R = v43
            v1[0x2a].R = v43; pc = 506; continue
        if pc == 506:  # 175D9: v43 = v43
            v43 = v43; pc = 507; continue
        if pc == 507:  # 175DB: v1[0x18].R = v43
            v1[0x18].R = v43; pc = 508; continue
        if pc == 508:  # 175E3: v43 = v43
            v43 = v43; pc = 509; continue
        if pc == 509:  # 175E5: v1[0x17].R = v43
            v1[0x17].R = v43; pc = 510; continue
        if pc == 510:  # 175EC: v1[4].R = v43
            v1[4].R = v43; pc = 511; continue
        if pc == 511:  # 17643: v43 = v40
            v43 = v40; pc = 512; continue
        if pc == 512:  # 17645: v1[0x6d].G = v40
            v1[0x6d].G = v40; pc = 513; continue
        if pc == 513:  # 1764D: v43 = v43
            v43 = v43; pc = 514; continue
        if pc == 514:  # 1764F: v1[0x57].G = v43
            v1[0x57].G = v43; pc = 515; continue
        if pc == 515:  # 17657: v43 = v43
            v43 = v43; pc = 516; continue
        if pc == 516:  # 17659: v1[0x56].G = v43
            v1[0x56].G = v43; pc = 517; continue
        if pc == 517:  # 17661: v43 = v43
            v43 = v43; pc = 518; continue
        if pc == 518:  # 17663: v1[0x41].G = v43
            v1[0x41].G = v43; pc = 519; continue
        if pc == 519:  # 1766B: v43 = v43
            v43 = v43; pc = 520; continue
        if pc == 520:  # 1766D: v1[0x40].G = v43
            v1[0x40].G = v43; pc = 521; continue
        if pc == 521:  # 17675: v43 = v43
            v43 = v43; pc = 522; continue
        if pc == 522:  # 17677: v1[0x2b].G = v43
            v1[0x2b].G = v43; pc = 523; continue
        if pc == 523:  # 1767F: v43 = v43
            v43 = v43; pc = 524; continue
        if pc == 524:  # 17681: v1[0x2a].G = v43
            v1[0x2a].G = v43; pc = 525; continue
        if pc == 525:  # 17689: v43 = v43
            v43 = v43; pc = 526; continue
        if pc == 526:  # 1768B: v1[0x18].G = v43
            v1[0x18].G = v43; pc = 527; continue
        if pc == 527:  # 17693: v43 = v43
            v43 = v43; pc = 528; continue
        if pc == 528:  # 17695: v1[0x17].G = v43
            v1[0x17].G = v43; pc = 529; continue
        if pc == 529:  # 1769C: v1[4].G = v43
            v1[4].G = v43; pc = 530; continue
        if pc == 530:  # 176F3: v43 = v41
            v43 = v41; pc = 531; continue
        if pc == 531:  # 176F5: v1[0x6d].B = v41
            v1[0x6d].B = v41; pc = 532; continue
        if pc == 532:  # 176FD: v43 = v43
            v43 = v43; pc = 533; continue
        if pc == 533:  # 176FF: v1[0x57].B = v43
            v1[0x57].B = v43; pc = 534; continue
        if pc == 534:  # 17707: v43 = v43
            v43 = v43; pc = 535; continue
        if pc == 535:  # 17709: v1[0x56].B = v43
            v1[0x56].B = v43; pc = 536; continue
        if pc == 536:  # 17711: v43 = v43
            v43 = v43; pc = 537; continue
        if pc == 537:  # 17713: v1[0x41].B = v43
            v1[0x41].B = v43; pc = 538; continue
        if pc == 538:  # 1771B: v43 = v43
            v43 = v43; pc = 539; continue
        if pc == 539:  # 1771D: v1[0x40].B = v43
            v1[0x40].B = v43; pc = 540; continue
        if pc == 540:  # 17725: v43 = v43
            v43 = v43; pc = 541; continue
        if pc == 541:  # 17727: v1[0x2b].B = v43
            v1[0x2b].B = v43; pc = 542; continue
        if pc == 542:  # 1772F: v43 = v43
            v43 = v43; pc = 543; continue
        if pc == 543:  # 17731: v1[0x2a].B = v43
            v1[0x2a].B = v43; pc = 544; continue
        if pc == 544:  # 17739: v43 = v43
            v43 = v43; pc = 545; continue
        if pc == 545:  # 1773B: v1[0x18].B = v43
            v1[0x18].B = v43; pc = 546; continue
        if pc == 546:  # 17743: v43 = v43
            v43 = v43; pc = 547; continue
        if pc == 547:  # 17745: v1[0x17].B = v43
            v1[0x17].B = v43; pc = 548; continue
        if pc == 548:  # 1774C: v1[4].B = v43
            v1[4].B = v43; pc = 549; continue
        if pc == 549:  # 177EA: v43 = v39
            v43 = v39; pc = 550; continue
        if pc == 550:  # 177EC: v1[(0x79 - this.ColRightShift)].R = v39
            v1[(0x79 - 0)].R = v39; pc = 551; continue
        if pc == 551:  # 177F4: v43 = v43
            v43 = v43; pc = 552; continue
        if pc == 552:  # 177F6: v1[(0x66 - this.ColRightShift)].R = v43
            v1[(0x66 - 0)].R = v43; pc = 553; continue
        if pc == 553:  # 177FE: v43 = v43
            v43 = v43; pc = 554; continue
        if pc == 554:  # 17800: v1[(0x65 - this.ColRightShift)].R = v43
            v1[(0x65 - 0)].R = v43; pc = 555; continue
        if pc == 555:  # 17808: v43 = v43
            v43 = v43; pc = 556; continue
        if pc == 556:  # 1780A: v1[(0x52 - this.ColRightShift)].R = v43
            v1[(0x52 - 0)].R = v43; pc = 557; continue
        if pc == 557:  # 17812: v43 = v43
            v43 = v43; pc = 558; continue
        if pc == 558:  # 17814: v1[(0x51 - this.ColRightShift)].R = v43
            v1[(0x51 - 0)].R = v43; pc = 559; continue
        if pc == 559:  # 1781C: v43 = v43
            v43 = v43; pc = 560; continue
        if pc == 560:  # 1781E: v1[(0x3e - this.ColRightShift)].R = v43
            v1[(0x3e - 0)].R = v43; pc = 561; continue
        if pc == 561:  # 17826: v43 = v43
            v43 = v43; pc = 562; continue
        if pc == 562:  # 17828: v1[(0x3d - this.ColRightShift)].R = v43
            v1[(0x3d - 0)].R = v43; pc = 563; continue
        if pc == 563:  # 17830: v43 = v43
            v43 = v43; pc = 564; continue
        if pc == 564:  # 17832: v1[(0x26 - this.ColRightShift)].R = v43
            v1[(0x26 - 0)].R = v43; pc = 565; continue
        if pc == 565:  # 1783A: v43 = v43
            v43 = v43; pc = 566; continue
        if pc == 566:  # 1783C: v1[(0x25 - this.ColRightShift)].R = v43
            v1[(0x25 - 0)].R = v43; pc = 567; continue
        if pc == 567:  # 17843: v1[(0x10 - this.ColRightShift)].R = v43
            v1[(0x10 - 0)].R = v43; pc = 568; continue
        if pc == 568:  # 178E1: v43 = v40
            v43 = v40; pc = 569; continue
        if pc == 569:  # 178E3: v1[(0x79 - this.ColRightShift)].G = v40
            v1[(0x79 - 0)].G = v40; pc = 570; continue
        if pc == 570:  # 178EB: v43 = v43
            v43 = v43; pc = 571; continue
        if pc == 571:  # 178ED: v1[(0x66 - this.ColRightShift)].G = v43
            v1[(0x66 - 0)].G = v43; pc = 572; continue
        if pc == 572:  # 178F5: v43 = v43
            v43 = v43; pc = 573; continue
        if pc == 573:  # 178F7: v1[(0x65 - this.ColRightShift)].G = v43
            v1[(0x65 - 0)].G = v43; pc = 574; continue
        if pc == 574:  # 178FF: v43 = v43
            v43 = v43; pc = 575; continue
        if pc == 575:  # 17901: v1[(0x52 - this.ColRightShift)].G = v43
            v1[(0x52 - 0)].G = v43; pc = 576; continue
        if pc == 576:  # 17909: v43 = v43
            v43 = v43; pc = 577; continue
        if pc == 577:  # 1790B: v1[(0x51 - this.ColRightShift)].G = v43
            v1[(0x51 - 0)].G = v43; pc = 578; continue
        if pc == 578:  # 17913: v43 = v43
            v43 = v43; pc = 579; continue
        if pc == 579:  # 17915: v1[(0x3e - this.ColRightShift)].G = v43
            v1[(0x3e - 0)].G = v43; pc = 580; continue
        if pc == 580:  # 1791D: v43 = v43
            v43 = v43; pc = 581; continue
        if pc == 581:  # 1791F: v1[(0x3d - this.ColRightShift)].G = v43
            v1[(0x3d - 0)].G = v43; pc = 582; continue
        if pc == 582:  # 17927: v43 = v43
            v43 = v43; pc = 583; continue
        if pc == 583:  # 17929: v1[(0x26 - this.ColRightShift)].G = v43
            v1[(0x26 - 0)].G = v43; pc = 584; continue
        if pc == 584:  # 17931: v43 = v43
            v43 = v43; pc = 585; continue
        if pc == 585:  # 17933: v1[(0x25 - this.ColRightShift)].G = v43
            v1[(0x25 - 0)].G = v43; pc = 586; continue
        if pc == 586:  # 1793A: v1[(0x10 - this.ColRightShift)].G = v43
            v1[(0x10 - 0)].G = v43; pc = 587; continue
        if pc == 587:  # 179D8: v43 = v41
            v43 = v41; pc = 588; continue
        if pc == 588:  # 179DA: v1[(0x79 - this.ColRightShift)].B = v41
            v1[(0x79 - 0)].B = v41; pc = 589; continue
        if pc == 589:  # 179E2: v43 = v43
            v43 = v43; pc = 590; continue
        if pc == 590:  # 179E4: v1[(0x66 - this.ColRightShift)].B = v43
            v1[(0x66 - 0)].B = v43; pc = 591; continue
        if pc == 591:  # 179EC: v43 = v43
            v43 = v43; pc = 592; continue
        if pc == 592:  # 179EE: v1[(0x65 - this.ColRightShift)].B = v43
            v1[(0x65 - 0)].B = v43; pc = 593; continue
        if pc == 593:  # 179F6: v43 = v43
            v43 = v43; pc = 594; continue
        if pc == 594:  # 179F8: v1[(0x52 - this.ColRightShift)].B = v43
            v1[(0x52 - 0)].B = v43; pc = 595; continue
        if pc == 595:  # 17A00: v43 = v43
            v43 = v43; pc = 596; continue
        if pc == 596:  # 17A02: v1[(0x51 - this.ColRightShift)].B = v43
            v1[(0x51 - 0)].B = v43; pc = 597; continue
        if pc == 597:  # 17A0A: v43 = v43
            v43 = v43; pc = 598; continue
        if pc == 598:  # 17A0C: v1[(0x3e - this.ColRightShift)].B = v43
            v1[(0x3e - 0)].B = v43; pc = 599; continue
        if pc == 599:  # 17A14: v43 = v43
            v43 = v43; pc = 600; continue
        if pc == 600:  # 17A16: v1[(0x3d - this.ColRightShift)].B = v43
            v1[(0x3d - 0)].B = v43; pc = 601; continue
        if pc == 601:  # 17A1E: v43 = v43
            v43 = v43; pc = 602; continue
        if pc == 602:  # 17A20: v1[(0x26 - this.ColRightShift)].B = v43
            v1[(0x26 - 0)].B = v43; pc = 603; continue
        if pc == 603:  # 17A28: v43 = v43
            v43 = v43; pc = 604; continue
        if pc == 604:  # 17A2A: v1[(0x25 - this.ColRightShift)].B = v43
            v1[(0x25 - 0)].B = v43; pc = 605; continue
        if pc == 605:  # 17A31: v1[(0x10 - this.ColRightShift)].B = v43
            v1[(0x10 - 0)].B = v43; pc = 606; continue
        if pc == 606:  # 17A36: goto 19CA9
            pc = 1393; continue
        if pc == 607:  # 17A8D: v43 = v39
            v43 = v39; pc = 608; continue
        if pc == 608:  # 17A8F: v1[0x6e].R = v39
            v1[0x6e].R = v39; pc = 609; continue
        if pc == 609:  # 17A97: v43 = v43
            v43 = v43; pc = 610; continue
        if pc == 610:  # 17A99: v1[0x58].R = v43
            v1[0x58].R = v43; pc = 611; continue
        if pc == 611:  # 17AA1: v43 = v43
            v43 = v43; pc = 612; continue
        if pc == 612:  # 17AA3: v1[0x57].R = v43
            v1[0x57].R = v43; pc = 613; continue
        if pc == 613:  # 17AAB: v43 = v43
            v43 = v43; pc = 614; continue
        if pc == 614:  # 17AAD: v1[0x42].R = v43
            v1[0x42].R = v43; pc = 615; continue
        if pc == 615:  # 17AB5: v43 = v43
            v43 = v43; pc = 616; continue
        if pc == 616:  # 17AB7: v1[0x41].R = v43
            v1[0x41].R = v43; pc = 617; continue
        if pc == 617:  # 17ABF: v43 = v43
            v43 = v43; pc = 618; continue
        if pc == 618:  # 17AC1: v1[0x2c].R = v43
            v1[0x2c].R = v43; pc = 619; continue
        if pc == 619:  # 17AC9: v43 = v43
            v43 = v43; pc = 620; continue
        if pc == 620:  # 17ACB: v1[0x2b].R = v43
            v1[0x2b].R = v43; pc = 621; continue
        if pc == 621:  # 17AD3: v43 = v43
            v43 = v43; pc = 622; continue
        if pc == 622:  # 17AD5: v1[0x19].R = v43
            v1[0x19].R = v43; pc = 623; continue
        if pc == 623:  # 17ADD: v43 = v43
            v43 = v43; pc = 624; continue
        if pc == 624:  # 17ADF: v1[0x18].R = v43
            v1[0x18].R = v43; pc = 625; continue
        if pc == 625:  # 17AE6: v1[5].R = v43
            v1[5].R = v43; pc = 626; continue
        if pc == 626:  # 17B3D: v43 = v40
            v43 = v40; pc = 627; continue
        if pc == 627:  # 17B3F: v1[0x6e].G = v40
            v1[0x6e].G = v40; pc = 628; continue
        if pc == 628:  # 17B47: v43 = v43
            v43 = v43; pc = 629; continue
        if pc == 629:  # 17B49: v1[0x58].G = v43
            v1[0x58].G = v43; pc = 630; continue
        if pc == 630:  # 17B51: v43 = v43
            v43 = v43; pc = 631; continue
        if pc == 631:  # 17B53: v1[0x57].G = v43
            v1[0x57].G = v43; pc = 632; continue
        if pc == 632:  # 17B5B: v43 = v43
            v43 = v43; pc = 633; continue
        if pc == 633:  # 17B5D: v1[0x42].G = v43
            v1[0x42].G = v43; pc = 634; continue
        if pc == 634:  # 17B65: v43 = v43
            v43 = v43; pc = 635; continue
        if pc == 635:  # 17B67: v1[0x41].G = v43
            v1[0x41].G = v43; pc = 636; continue
        if pc == 636:  # 17B6F: v43 = v43
            v43 = v43; pc = 637; continue
        if pc == 637:  # 17B71: v1[0x2c].G = v43
            v1[0x2c].G = v43; pc = 638; continue
        if pc == 638:  # 17B79: v43 = v43
            v43 = v43; pc = 639; continue
        if pc == 639:  # 17B7B: v1[0x2b].G = v43
            v1[0x2b].G = v43; pc = 640; continue
        if pc == 640:  # 17B83: v43 = v43
            v43 = v43; pc = 641; continue
        if pc == 641:  # 17B85: v1[0x19].G = v43
            v1[0x19].G = v43; pc = 642; continue
        if pc == 642:  # 17B8D: v43 = v43
            v43 = v43; pc = 643; continue
        if pc == 643:  # 17B8F: v1[0x18].G = v43
            v1[0x18].G = v43; pc = 644; continue
        if pc == 644:  # 17B96: v1[5].G = v43
            v1[5].G = v43; pc = 645; continue
        if pc == 645:  # 17BED: v43 = v41
            v43 = v41; pc = 646; continue
        if pc == 646:  # 17BEF: v1[0x6e].B = v41
            v1[0x6e].B = v41; pc = 647; continue
        if pc == 647:  # 17BF7: v43 = v43
            v43 = v43; pc = 648; continue
        if pc == 648:  # 17BF9: v1[0x58].B = v43
            v1[0x58].B = v43; pc = 649; continue
        if pc == 649:  # 17C01: v43 = v43
            v43 = v43; pc = 650; continue
        if pc == 650:  # 17C03: v1[0x57].B = v43
            v1[0x57].B = v43; pc = 651; continue
        if pc == 651:  # 17C0B: v43 = v43
            v43 = v43; pc = 652; continue
        if pc == 652:  # 17C0D: v1[0x42].B = v43
            v1[0x42].B = v43; pc = 653; continue
        if pc == 653:  # 17C15: v43 = v43
            v43 = v43; pc = 654; continue
        if pc == 654:  # 17C17: v1[0x41].B = v43
            v1[0x41].B = v43; pc = 655; continue
        if pc == 655:  # 17C1F: v43 = v43
            v43 = v43; pc = 656; continue
        if pc == 656:  # 17C21: v1[0x2c].B = v43
            v1[0x2c].B = v43; pc = 657; continue
        if pc == 657:  # 17C29: v43 = v43
            v43 = v43; pc = 658; continue
        if pc == 658:  # 17C2B: v1[0x2b].B = v43
            v1[0x2b].B = v43; pc = 659; continue
        if pc == 659:  # 17C33: v43 = v43
            v43 = v43; pc = 660; continue
        if pc == 660:  # 17C35: v1[0x19].B = v43
            v1[0x19].B = v43; pc = 661; continue
        if pc == 661:  # 17C3D: v43 = v43
            v43 = v43; pc = 662; continue
        if pc == 662:  # 17C3F: v1[0x18].B = v43
            v1[0x18].B = v43; pc = 663; continue
        if pc == 663:  # 17C46: v1[5].B = v43
            v1[5].B = v43; pc = 664; continue
        if pc == 664:  # 17CE4: v43 = v39
            v43 = v39; pc = 665; continue
        if pc == 665:  # 17CE6: v1[(0x78 - this.ColRightShift)].R = v39
            v1[(0x78 - 0)].R = v39; pc = 666; continue
        if pc == 666:  # 17CEE: v43 = v43
            v43 = v43; pc = 667; continue
        if pc == 667:  # 17CF0: v1[(0x65 - this.ColRightShift)].R = v43
            v1[(0x65 - 0)].R = v43; pc = 668; continue
        if pc == 668:  # 17CF8: v43 = v43
            v43 = v43; pc = 669; continue
        if pc == 669:  # 17CFA: v1[(0x64 - this.ColRightShift)].R = v43
            v1[(0x64 - 0)].R = v43; pc = 670; continue
        if pc == 670:  # 17D02: v43 = v43
            v43 = v43; pc = 671; continue
        if pc == 671:  # 17D04: v1[(0x51 - this.ColRightShift)].R = v43
            v1[(0x51 - 0)].R = v43; pc = 672; continue
        if pc == 672:  # 17D0C: v43 = v43
            v43 = v43; pc = 673; continue
        if pc == 673:  # 17D0E: v1[(0x50 - this.ColRightShift)].R = v43
            v1[(0x50 - 0)].R = v43; pc = 674; continue
        if pc == 674:  # 17D16: v43 = v43
            v43 = v43; pc = 675; continue
        if pc == 675:  # 17D18: v1[(0x3d - this.ColRightShift)].R = v43
            v1[(0x3d - 0)].R = v43; pc = 676; continue
        if pc == 676:  # 17D20: v43 = v43
            v43 = v43; pc = 677; continue
        if pc == 677:  # 17D22: v1[(0x3c - this.ColRightShift)].R = v43
            v1[(0x3c - 0)].R = v43; pc = 678; continue
        if pc == 678:  # 17D2A: v43 = v43
            v43 = v43; pc = 679; continue
        if pc == 679:  # 17D2C: v1[(0x25 - this.ColRightShift)].R = v43
            v1[(0x25 - 0)].R = v43; pc = 680; continue
        if pc == 680:  # 17D34: v43 = v43
            v43 = v43; pc = 681; continue
        if pc == 681:  # 17D36: v1[(0x24 - this.ColRightShift)].R = v43
            v1[(0x24 - 0)].R = v43; pc = 682; continue
        if pc == 682:  # 17D3D: v1[(0xf - this.ColRightShift)].R = v43
            v1[(0xf - 0)].R = v43; pc = 683; continue
        if pc == 683:  # 17DDB: v43 = v40
            v43 = v40; pc = 684; continue
        if pc == 684:  # 17DDD: v1[(0x78 - this.ColRightShift)].G = v40
            v1[(0x78 - 0)].G = v40; pc = 685; continue
        if pc == 685:  # 17DE5: v43 = v43
            v43 = v43; pc = 686; continue
        if pc == 686:  # 17DE7: v1[(0x65 - this.ColRightShift)].G = v43
            v1[(0x65 - 0)].G = v43; pc = 687; continue
        if pc == 687:  # 17DEF: v43 = v43
            v43 = v43; pc = 688; continue
        if pc == 688:  # 17DF1: v1[(0x64 - this.ColRightShift)].G = v43
            v1[(0x64 - 0)].G = v43; pc = 689; continue
        if pc == 689:  # 17DF9: v43 = v43
            v43 = v43; pc = 690; continue
        if pc == 690:  # 17DFB: v1[(0x51 - this.ColRightShift)].G = v43
            v1[(0x51 - 0)].G = v43; pc = 691; continue
        if pc == 691:  # 17E03: v43 = v43
            v43 = v43; pc = 692; continue
        if pc == 692:  # 17E05: v1[(0x50 - this.ColRightShift)].G = v43
            v1[(0x50 - 0)].G = v43; pc = 693; continue
        if pc == 693:  # 17E0D: v43 = v43
            v43 = v43; pc = 694; continue
        if pc == 694:  # 17E0F: v1[(0x3d - this.ColRightShift)].G = v43
            v1[(0x3d - 0)].G = v43; pc = 695; continue
        if pc == 695:  # 17E17: v43 = v43
            v43 = v43; pc = 696; continue
        if pc == 696:  # 17E19: v1[(0x3c - this.ColRightShift)].G = v43
            v1[(0x3c - 0)].G = v43; pc = 697; continue
        if pc == 697:  # 17E21: v43 = v43
            v43 = v43; pc = 698; continue
        if pc == 698:  # 17E23: v1[(0x25 - this.ColRightShift)].G = v43
            v1[(0x25 - 0)].G = v43; pc = 699; continue
        if pc == 699:  # 17E2B: v43 = v43
            v43 = v43; pc = 700; continue
        if pc == 700:  # 17E2D: v1[(0x24 - this.ColRightShift)].G = v43
            v1[(0x24 - 0)].G = v43; pc = 701; continue
        if pc == 701:  # 17E34: v1[(0xf - this.ColRightShift)].G = v43
            v1[(0xf - 0)].G = v43; pc = 702; continue
        if pc == 702:  # 17ED2: v43 = v41
            v43 = v41; pc = 703; continue
        if pc == 703:  # 17ED4: v1[(0x78 - this.ColRightShift)].B = v41
            v1[(0x78 - 0)].B = v41; pc = 704; continue
        if pc == 704:  # 17EDC: v43 = v43
            v43 = v43; pc = 705; continue
        if pc == 705:  # 17EDE: v1[(0x65 - this.ColRightShift)].B = v43
            v1[(0x65 - 0)].B = v43; pc = 706; continue
        if pc == 706:  # 17EE6: v43 = v43
            v43 = v43; pc = 707; continue
        if pc == 707:  # 17EE8: v1[(0x64 - this.ColRightShift)].B = v43
            v1[(0x64 - 0)].B = v43; pc = 708; continue
        if pc == 708:  # 17EF0: v43 = v43
            v43 = v43; pc = 709; continue
        if pc == 709:  # 17EF2: v1[(0x51 - this.ColRightShift)].B = v43
            v1[(0x51 - 0)].B = v43; pc = 710; continue
        if pc == 710:  # 17EFA: v43 = v43
            v43 = v43; pc = 711; continue
        if pc == 711:  # 17EFC: v1[(0x50 - this.ColRightShift)].B = v43
            v1[(0x50 - 0)].B = v43; pc = 712; continue
        if pc == 712:  # 17F04: v43 = v43
            v43 = v43; pc = 713; continue
        if pc == 713:  # 17F06: v1[(0x3d - this.ColRightShift)].B = v43
            v1[(0x3d - 0)].B = v43; pc = 714; continue
        if pc == 714:  # 17F0E: v43 = v43
            v43 = v43; pc = 715; continue
        if pc == 715:  # 17F10: v1[(0x3c - this.ColRightShift)].B = v43
            v1[(0x3c - 0)].B = v43; pc = 716; continue
        if pc == 716:  # 17F18: v43 = v43
            v43 = v43; pc = 717; continue
        if pc == 717:  # 17F1A: v1[(0x25 - this.ColRightShift)].B = v43
            v1[(0x25 - 0)].B = v43; pc = 718; continue
        if pc == 718:  # 17F22: v43 = v43
            v43 = v43; pc = 719; continue
        if pc == 719:  # 17F24: v1[(0x24 - this.ColRightShift)].B = v43
            v1[(0x24 - 0)].B = v43; pc = 720; continue
        if pc == 720:  # 17F2B: v1[(0xf - this.ColRightShift)].B = v43
            v1[(0xf - 0)].B = v43; pc = 721; continue
        if pc == 721:  # 17F30: goto 19CA9
            pc = 1393; continue
        if pc == 722:  # 17F87: v43 = v39
            v43 = v39; pc = 723; continue
        if pc == 723:  # 17F89: v1[0x6f].R = v39
            v1[0x6f].R = v39; pc = 724; continue
        if pc == 724:  # 17F91: v43 = v43
            v43 = v43; pc = 725; continue
        if pc == 725:  # 17F93: v1[0x59].R = v43
            v1[0x59].R = v43; pc = 726; continue
        if pc == 726:  # 17F9B: v43 = v43
            v43 = v43; pc = 727; continue
        if pc == 727:  # 17F9D: v1[0x58].R = v43
            v1[0x58].R = v43; pc = 728; continue
        if pc == 728:  # 17FA5: v43 = v43
            v43 = v43; pc = 729; continue
        if pc == 729:  # 17FA7: v1[0x43].R = v43
            v1[0x43].R = v43; pc = 730; continue
        if pc == 730:  # 17FAF: v43 = v43
            v43 = v43; pc = 731; continue
        if pc == 731:  # 17FB1: v1[0x42].R = v43
            v1[0x42].R = v43; pc = 732; continue
        if pc == 732:  # 17FB9: v43 = v43
            v43 = v43; pc = 733; continue
        if pc == 733:  # 17FBB: v1[0x2d].R = v43
            v1[0x2d].R = v43; pc = 734; continue
        if pc == 734:  # 17FC3: v43 = v43
            v43 = v43; pc = 735; continue
        if pc == 735:  # 17FC5: v1[0x2c].R = v43
            v1[0x2c].R = v43; pc = 736; continue
        if pc == 736:  # 17FCD: v43 = v43
            v43 = v43; pc = 737; continue
        if pc == 737:  # 17FCF: v1[0x1a].R = v43
            v1[0x1a].R = v43; pc = 738; continue
        if pc == 738:  # 17FD7: v43 = v43
            v43 = v43; pc = 739; continue
        if pc == 739:  # 17FD9: v1[0x19].R = v43
            v1[0x19].R = v43; pc = 740; continue
        if pc == 740:  # 17FE0: v1[6].R = v43
            v1[6].R = v43; pc = 741; continue
        if pc == 741:  # 18037: v43 = v40
            v43 = v40; pc = 742; continue
        if pc == 742:  # 18039: v1[0x6f].G = v40
            v1[0x6f].G = v40; pc = 743; continue
        if pc == 743:  # 18041: v43 = v43
            v43 = v43; pc = 744; continue
        if pc == 744:  # 18043: v1[0x59].G = v43
            v1[0x59].G = v43; pc = 745; continue
        if pc == 745:  # 1804B: v43 = v43
            v43 = v43; pc = 746; continue
        if pc == 746:  # 1804D: v1[0x58].G = v43
            v1[0x58].G = v43; pc = 747; continue
        if pc == 747:  # 18055: v43 = v43
            v43 = v43; pc = 748; continue
        if pc == 748:  # 18057: v1[0x43].G = v43
            v1[0x43].G = v43; pc = 749; continue
        if pc == 749:  # 1805F: v43 = v43
            v43 = v43; pc = 750; continue
        if pc == 750:  # 18061: v1[0x42].G = v43
            v1[0x42].G = v43; pc = 751; continue
        if pc == 751:  # 18069: v43 = v43
            v43 = v43; pc = 752; continue
        if pc == 752:  # 1806B: v1[0x2d].G = v43
            v1[0x2d].G = v43; pc = 753; continue
        if pc == 753:  # 18073: v43 = v43
            v43 = v43; pc = 754; continue
        if pc == 754:  # 18075: v1[0x2c].G = v43
            v1[0x2c].G = v43; pc = 755; continue
        if pc == 755:  # 1807D: v43 = v43
            v43 = v43; pc = 756; continue
        if pc == 756:  # 1807F: v1[0x1a].G = v43
            v1[0x1a].G = v43; pc = 757; continue
        if pc == 757:  # 18087: v43 = v43
            v43 = v43; pc = 758; continue
        if pc == 758:  # 18089: v1[0x19].G = v43
            v1[0x19].G = v43; pc = 759; continue
        if pc == 759:  # 18090: v1[6].G = v43
            v1[6].G = v43; pc = 760; continue
        if pc == 760:  # 180E7: v43 = v41
            v43 = v41; pc = 761; continue
        if pc == 761:  # 180E9: v1[0x6f].B = v41
            v1[0x6f].B = v41; pc = 762; continue
        if pc == 762:  # 180F1: v43 = v43
            v43 = v43; pc = 763; continue
        if pc == 763:  # 180F3: v1[0x59].B = v43
            v1[0x59].B = v43; pc = 764; continue
        if pc == 764:  # 180FB: v43 = v43
            v43 = v43; pc = 765; continue
        if pc == 765:  # 180FD: v1[0x58].B = v43
            v1[0x58].B = v43; pc = 766; continue
        if pc == 766:  # 18105: v43 = v43
            v43 = v43; pc = 767; continue
        if pc == 767:  # 18107: v1[0x43].B = v43
            v1[0x43].B = v43; pc = 768; continue
        if pc == 768:  # 1810F: v43 = v43
            v43 = v43; pc = 769; continue
        if pc == 769:  # 18111: v1[0x42].B = v43
            v1[0x42].B = v43; pc = 770; continue
        if pc == 770:  # 18119: v43 = v43
            v43 = v43; pc = 771; continue
        if pc == 771:  # 1811B: v1[0x2d].B = v43
            v1[0x2d].B = v43; pc = 772; continue
        if pc == 772:  # 18123: v43 = v43
            v43 = v43; pc = 773; continue
        if pc == 773:  # 18125: v1[0x2c].B = v43
            v1[0x2c].B = v43; pc = 774; continue
        if pc == 774:  # 1812D: v43 = v43
            v43 = v43; pc = 775; continue
        if pc == 775:  # 1812F: v1[0x1a].B = v43
            v1[0x1a].B = v43; pc = 776; continue
        if pc == 776:  # 18137: v43 = v43
            v43 = v43; pc = 777; continue
        if pc == 777:  # 18139: v1[0x19].B = v43
            v1[0x19].B = v43; pc = 778; continue
        if pc == 778:  # 18140: v1[6].B = v43
            v1[6].B = v43; pc = 779; continue
        if pc == 779:  # 181DE: v43 = v39
            v43 = v39; pc = 780; continue
        if pc == 780:  # 181E0: v1[(0x77 - this.ColRightShift)].R = v39
            v1[(0x77 - 0)].R = v39; pc = 781; continue
        if pc == 781:  # 181E8: v43 = v43
            v43 = v43; pc = 782; continue
        if pc == 782:  # 181EA: v1[(0x64 - this.ColRightShift)].R = v43
            v1[(0x64 - 0)].R = v43; pc = 783; continue
        if pc == 783:  # 181F2: v43 = v43
            v43 = v43; pc = 784; continue
        if pc == 784:  # 181F4: v1[(0x63 - this.ColRightShift)].R = v43
            v1[(0x63 - 0)].R = v43; pc = 785; continue
        if pc == 785:  # 181FC: v43 = v43
            v43 = v43; pc = 786; continue
        if pc == 786:  # 181FE: v1[(0x50 - this.ColRightShift)].R = v43
            v1[(0x50 - 0)].R = v43; pc = 787; continue
        if pc == 787:  # 18206: v43 = v43
            v43 = v43; pc = 788; continue
        if pc == 788:  # 18208: v1[(0x4f - this.ColRightShift)].R = v43
            v1[(0x4f - 0)].R = v43; pc = 789; continue
        if pc == 789:  # 18210: v43 = v43
            v43 = v43; pc = 790; continue
        if pc == 790:  # 18212: v1[(0x3c - this.ColRightShift)].R = v43
            v1[(0x3c - 0)].R = v43; pc = 791; continue
        if pc == 791:  # 1821A: v43 = v43
            v43 = v43; pc = 792; continue
        if pc == 792:  # 1821C: v1[(0x3b - this.ColRightShift)].R = v43
            v1[(0x3b - 0)].R = v43; pc = 793; continue
        if pc == 793:  # 18224: v43 = v43
            v43 = v43; pc = 794; continue
        if pc == 794:  # 18226: v1[(0x24 - this.ColRightShift)].R = v43
            v1[(0x24 - 0)].R = v43; pc = 795; continue
        if pc == 795:  # 1822E: v43 = v43
            v43 = v43; pc = 796; continue
        if pc == 796:  # 18230: v1[(0x23 - this.ColRightShift)].R = v43
            v1[(0x23 - 0)].R = v43; pc = 797; continue
        if pc == 797:  # 18237: v1[(0xe - this.ColRightShift)].R = v43
            v1[(0xe - 0)].R = v43; pc = 798; continue
        if pc == 798:  # 182D5: v43 = v40
            v43 = v40; pc = 799; continue
        if pc == 799:  # 182D7: v1[(0x77 - this.ColRightShift)].G = v40
            v1[(0x77 - 0)].G = v40; pc = 800; continue
        if pc == 800:  # 182DF: v43 = v43
            v43 = v43; pc = 801; continue
        if pc == 801:  # 182E1: v1[(0x64 - this.ColRightShift)].G = v43
            v1[(0x64 - 0)].G = v43; pc = 802; continue
        if pc == 802:  # 182E9: v43 = v43
            v43 = v43; pc = 803; continue
        if pc == 803:  # 182EB: v1[(0x63 - this.ColRightShift)].G = v43
            v1[(0x63 - 0)].G = v43; pc = 804; continue
        if pc == 804:  # 182F3: v43 = v43
            v43 = v43; pc = 805; continue
        if pc == 805:  # 182F5: v1[(0x50 - this.ColRightShift)].G = v43
            v1[(0x50 - 0)].G = v43; pc = 806; continue
        if pc == 806:  # 182FD: v43 = v43
            v43 = v43; pc = 807; continue
        if pc == 807:  # 182FF: v1[(0x4f - this.ColRightShift)].G = v43
            v1[(0x4f - 0)].G = v43; pc = 808; continue
        if pc == 808:  # 18307: v43 = v43
            v43 = v43; pc = 809; continue
        if pc == 809:  # 18309: v1[(0x3c - this.ColRightShift)].G = v43
            v1[(0x3c - 0)].G = v43; pc = 810; continue
        if pc == 810:  # 18311: v43 = v43
            v43 = v43; pc = 811; continue
        if pc == 811:  # 18313: v1[(0x3b - this.ColRightShift)].G = v43
            v1[(0x3b - 0)].G = v43; pc = 812; continue
        if pc == 812:  # 1831B: v43 = v43
            v43 = v43; pc = 813; continue
        if pc == 813:  # 1831D: v1[(0x24 - this.ColRightShift)].G = v43
            v1[(0x24 - 0)].G = v43; pc = 814; continue
        if pc == 814:  # 18325: v43 = v43
            v43 = v43; pc = 815; continue
        if pc == 815:  # 18327: v1[(0x23 - this.ColRightShift)].G = v43
            v1[(0x23 - 0)].G = v43; pc = 816; continue
        if pc == 816:  # 1832E: v1[(0xe - this.ColRightShift)].G = v43
            v1[(0xe - 0)].G = v43; pc = 817; continue
        if pc == 817:  # 183CC: v43 = v41
            v43 = v41; pc = 818; continue
        if pc == 818:  # 183CE: v1[(0x77 - this.ColRightShift)].B = v41
            v1[(0x77 - 0)].B = v41; pc = 819; continue
        if pc == 819:  # 183D6: v43 = v43
            v43 = v43; pc = 820; continue
        if pc == 820:  # 183D8: v1[(0x64 - this.ColRightShift)].B = v43
            v1[(0x64 - 0)].B = v43; pc = 821; continue
        if pc == 821:  # 183E0: v43 = v43
            v43 = v43; pc = 822; continue
        if pc == 822:  # 183E2: v1[(0x63 - this.ColRightShift)].B = v43
            v1[(0x63 - 0)].B = v43; pc = 823; continue
        if pc == 823:  # 183EA: v43 = v43
            v43 = v43; pc = 824; continue
        if pc == 824:  # 183EC: v1[(0x50 - this.ColRightShift)].B = v43
            v1[(0x50 - 0)].B = v43; pc = 825; continue
        if pc == 825:  # 183F4: v43 = v43
            v43 = v43; pc = 826; continue
        if pc == 826:  # 183F6: v1[(0x4f - this.ColRightShift)].B = v43
            v1[(0x4f - 0)].B = v43; pc = 827; continue
        if pc == 827:  # 183FE: v43 = v43
            v43 = v43; pc = 828; continue
        if pc == 828:  # 18400: v1[(0x3c - this.ColRightShift)].B = v43
            v1[(0x3c - 0)].B = v43; pc = 829; continue
        if pc == 829:  # 18408: v43 = v43
            v43 = v43; pc = 830; continue
        if pc == 830:  # 1840A: v1[(0x3b - this.ColRightShift)].B = v43
            v1[(0x3b - 0)].B = v43; pc = 831; continue
        if pc == 831:  # 18412: v43 = v43
            v43 = v43; pc = 832; continue
        if pc == 832:  # 18414: v1[(0x24 - this.ColRightShift)].B = v43
            v1[(0x24 - 0)].B = v43; pc = 833; continue
        if pc == 833:  # 1841C: v43 = v43
            v43 = v43; pc = 834; continue
        if pc == 834:  # 1841E: v1[(0x23 - this.ColRightShift)].B = v43
            v1[(0x23 - 0)].B = v43; pc = 835; continue
        if pc == 835:  # 18425: v1[(0xe - this.ColRightShift)].B = v43
            v1[(0xe - 0)].B = v43; pc = 836; continue
        if pc == 836:  # 1842A: goto 19CA9
            pc = 1393; continue
        if pc == 837:  # 18481: v43 = v39
            v43 = v39; pc = 838; continue
        if pc == 838:  # 18483: v1[0x70].R = v39
            v1[0x70].R = v39; pc = 839; continue
        if pc == 839:  # 1848B: v43 = v43
            v43 = v43; pc = 840; continue
        if pc == 840:  # 1848D: v1[0x5a].R = v43
            v1[0x5a].R = v43; pc = 841; continue
        if pc == 841:  # 18495: v43 = v43
            v43 = v43; pc = 842; continue
        if pc == 842:  # 18497: v1[0x59].R = v43
            v1[0x59].R = v43; pc = 843; continue
        if pc == 843:  # 1849F: v43 = v43
            v43 = v43; pc = 844; continue
        if pc == 844:  # 184A1: v1[0x44].R = v43
            v1[0x44].R = v43; pc = 845; continue
        if pc == 845:  # 184A9: v43 = v43
            v43 = v43; pc = 846; continue
        if pc == 846:  # 184AB: v1[0x43].R = v43
            v1[0x43].R = v43; pc = 847; continue
        if pc == 847:  # 184B3: v43 = v43
            v43 = v43; pc = 848; continue
        if pc == 848:  # 184B5: v1[0x2e].R = v43
            v1[0x2e].R = v43; pc = 849; continue
        if pc == 849:  # 184BD: v43 = v43
            v43 = v43; pc = 850; continue
        if pc == 850:  # 184BF: v1[0x2d].R = v43
            v1[0x2d].R = v43; pc = 851; continue
        if pc == 851:  # 184C7: v43 = v43
            v43 = v43; pc = 852; continue
        if pc == 852:  # 184C9: v1[0x1b].R = v43
            v1[0x1b].R = v43; pc = 853; continue
        if pc == 853:  # 184D1: v43 = v43
            v43 = v43; pc = 854; continue
        if pc == 854:  # 184D3: v1[0x1a].R = v43
            v1[0x1a].R = v43; pc = 855; continue
        if pc == 855:  # 184DA: v1[7].R = v43
            v1[7].R = v43; pc = 856; continue
        if pc == 856:  # 18531: v43 = v40
            v43 = v40; pc = 857; continue
        if pc == 857:  # 18533: v1[0x70].G = v40
            v1[0x70].G = v40; pc = 858; continue
        if pc == 858:  # 1853B: v43 = v43
            v43 = v43; pc = 859; continue
        if pc == 859:  # 1853D: v1[0x5a].G = v43
            v1[0x5a].G = v43; pc = 860; continue
        if pc == 860:  # 18545: v43 = v43
            v43 = v43; pc = 861; continue
        if pc == 861:  # 18547: v1[0x59].G = v43
            v1[0x59].G = v43; pc = 862; continue
        if pc == 862:  # 1854F: v43 = v43
            v43 = v43; pc = 863; continue
        if pc == 863:  # 18551: v1[0x44].G = v43
            v1[0x44].G = v43; pc = 864; continue
        if pc == 864:  # 18559: v43 = v43
            v43 = v43; pc = 865; continue
        if pc == 865:  # 1855B: v1[0x43].G = v43
            v1[0x43].G = v43; pc = 866; continue
        if pc == 866:  # 18563: v43 = v43
            v43 = v43; pc = 867; continue
        if pc == 867:  # 18565: v1[0x2e].G = v43
            v1[0x2e].G = v43; pc = 868; continue
        if pc == 868:  # 1856D: v43 = v43
            v43 = v43; pc = 869; continue
        if pc == 869:  # 1856F: v1[0x2d].G = v43
            v1[0x2d].G = v43; pc = 870; continue
        if pc == 870:  # 18577: v43 = v43
            v43 = v43; pc = 871; continue
        if pc == 871:  # 18579: v1[0x1b].G = v43
            v1[0x1b].G = v43; pc = 872; continue
        if pc == 872:  # 18581: v43 = v43
            v43 = v43; pc = 873; continue
        if pc == 873:  # 18583: v1[0x1a].G = v43
            v1[0x1a].G = v43; pc = 874; continue
        if pc == 874:  # 1858A: v1[7].G = v43
            v1[7].G = v43; pc = 875; continue
        if pc == 875:  # 185E1: v43 = v41
            v43 = v41; pc = 876; continue
        if pc == 876:  # 185E3: v1[0x70].B = v41
            v1[0x70].B = v41; pc = 877; continue
        if pc == 877:  # 185EB: v43 = v43
            v43 = v43; pc = 878; continue
        if pc == 878:  # 185ED: v1[0x5a].B = v43
            v1[0x5a].B = v43; pc = 879; continue
        if pc == 879:  # 185F5: v43 = v43
            v43 = v43; pc = 880; continue
        if pc == 880:  # 185F7: v1[0x59].B = v43
            v1[0x59].B = v43; pc = 881; continue
        if pc == 881:  # 185FF: v43 = v43
            v43 = v43; pc = 882; continue
        if pc == 882:  # 18601: v1[0x44].B = v43
            v1[0x44].B = v43; pc = 883; continue
        if pc == 883:  # 18609: v43 = v43
            v43 = v43; pc = 884; continue
        if pc == 884:  # 1860B: v1[0x43].B = v43
            v1[0x43].B = v43; pc = 885; continue
        if pc == 885:  # 18613: v43 = v43
            v43 = v43; pc = 886; continue
        if pc == 886:  # 18615: v1[0x2e].B = v43
            v1[0x2e].B = v43; pc = 887; continue
        if pc == 887:  # 1861D: v43 = v43
            v43 = v43; pc = 888; continue
        if pc == 888:  # 1861F: v1[0x2d].B = v43
            v1[0x2d].B = v43; pc = 889; continue
        if pc == 889:  # 18627: v43 = v43
            v43 = v43; pc = 890; continue
        if pc == 890:  # 18629: v1[0x1b].B = v43
            v1[0x1b].B = v43; pc = 891; continue
        if pc == 891:  # 18631: v43 = v43
            v43 = v43; pc = 892; continue
        if pc == 892:  # 18633: v1[0x1a].B = v43
            v1[0x1a].B = v43; pc = 893; continue
        if pc == 893:  # 1863A: v1[7].B = v43
            v1[7].B = v43; pc = 894; continue
        if pc == 894:  # 186D8: v43 = v39
            v43 = v39; pc = 895; continue
        if pc == 895:  # 186DA: v1[(0x76 - this.ColRightShift)].R = v39
            v1[(0x76 - 0)].R = v39; pc = 896; continue
        if pc == 896:  # 186E2: v43 = v43
            v43 = v43; pc = 897; continue
        if pc == 897:  # 186E4: v1[(0x63 - this.ColRightShift)].R = v43
            v1[(0x63 - 0)].R = v43; pc = 898; continue
        if pc == 898:  # 186EC: v43 = v43
            v43 = v43; pc = 899; continue
        if pc == 899:  # 186EE: v1[(0x62 - this.ColRightShift)].R = v43
            v1[(0x62 - 0)].R = v43; pc = 900; continue
        if pc == 900:  # 186F6: v43 = v43
            v43 = v43; pc = 901; continue
        if pc == 901:  # 186F8: v1[(0x4f - this.ColRightShift)].R = v43
            v1[(0x4f - 0)].R = v43; pc = 902; continue
        if pc == 902:  # 18700: v43 = v43
            v43 = v43; pc = 903; continue
        if pc == 903:  # 18702: v1[(0x4e - this.ColRightShift)].R = v43
            v1[(0x4e - 0)].R = v43; pc = 904; continue
        if pc == 904:  # 1870A: v43 = v43
            v43 = v43; pc = 905; continue
        if pc == 905:  # 1870C: v1[(0x3b - this.ColRightShift)].R = v43
            v1[(0x3b - 0)].R = v43; pc = 906; continue
        if pc == 906:  # 18714: v43 = v43
            v43 = v43; pc = 907; continue
        if pc == 907:  # 18716: v1[(0x3a - this.ColRightShift)].R = v43
            v1[(0x3a - 0)].R = v43; pc = 908; continue
        if pc == 908:  # 1871E: v43 = v43
            v43 = v43; pc = 909; continue
        if pc == 909:  # 18720: v1[(0x23 - this.ColRightShift)].R = v43
            v1[(0x23 - 0)].R = v43; pc = 910; continue
        if pc == 910:  # 18728: v43 = v43
            v43 = v43; pc = 911; continue
        if pc == 911:  # 1872A: v1[(0x22 - this.ColRightShift)].R = v43
            v1[(0x22 - 0)].R = v43; pc = 912; continue
        if pc == 912:  # 18731: v1[(0xd - this.ColRightShift)].R = v43
            v1[(0xd - 0)].R = v43; pc = 913; continue
        if pc == 913:  # 187CF: v43 = v40
            v43 = v40; pc = 914; continue
        if pc == 914:  # 187D1: v1[(0x76 - this.ColRightShift)].G = v40
            v1[(0x76 - 0)].G = v40; pc = 915; continue
        if pc == 915:  # 187D9: v43 = v43
            v43 = v43; pc = 916; continue
        if pc == 916:  # 187DB: v1[(0x63 - this.ColRightShift)].G = v43
            v1[(0x63 - 0)].G = v43; pc = 917; continue
        if pc == 917:  # 187E3: v43 = v43
            v43 = v43; pc = 918; continue
        if pc == 918:  # 187E5: v1[(0x62 - this.ColRightShift)].G = v43
            v1[(0x62 - 0)].G = v43; pc = 919; continue
        if pc == 919:  # 187ED: v43 = v43
            v43 = v43; pc = 920; continue
        if pc == 920:  # 187EF: v1[(0x4f - this.ColRightShift)].G = v43
            v1[(0x4f - 0)].G = v43; pc = 921; continue
        if pc == 921:  # 187F7: v43 = v43
            v43 = v43; pc = 922; continue
        if pc == 922:  # 187F9: v1[(0x4e - this.ColRightShift)].G = v43
            v1[(0x4e - 0)].G = v43; pc = 923; continue
        if pc == 923:  # 18801: v43 = v43
            v43 = v43; pc = 924; continue
        if pc == 924:  # 18803: v1[(0x3b - this.ColRightShift)].G = v43
            v1[(0x3b - 0)].G = v43; pc = 925; continue
        if pc == 925:  # 1880B: v43 = v43
            v43 = v43; pc = 926; continue
        if pc == 926:  # 1880D: v1[(0x3a - this.ColRightShift)].G = v43
            v1[(0x3a - 0)].G = v43; pc = 927; continue
        if pc == 927:  # 18815: v43 = v43
            v43 = v43; pc = 928; continue
        if pc == 928:  # 18817: v1[(0x23 - this.ColRightShift)].G = v43
            v1[(0x23 - 0)].G = v43; pc = 929; continue
        if pc == 929:  # 1881F: v43 = v43
            v43 = v43; pc = 930; continue
        if pc == 930:  # 18821: v1[(0x22 - this.ColRightShift)].G = v43
            v1[(0x22 - 0)].G = v43; pc = 931; continue
        if pc == 931:  # 18828: v1[(0xd - this.ColRightShift)].G = v43
            v1[(0xd - 0)].G = v43; pc = 932; continue
        if pc == 932:  # 188C6: v43 = v41
            v43 = v41; pc = 933; continue
        if pc == 933:  # 188C8: v1[(0x76 - this.ColRightShift)].B = v41
            v1[(0x76 - 0)].B = v41; pc = 934; continue
        if pc == 934:  # 188D0: v43 = v43
            v43 = v43; pc = 935; continue
        if pc == 935:  # 188D2: v1[(0x63 - this.ColRightShift)].B = v43
            v1[(0x63 - 0)].B = v43; pc = 936; continue
        if pc == 936:  # 188DA: v43 = v43
            v43 = v43; pc = 937; continue
        if pc == 937:  # 188DC: v1[(0x62 - this.ColRightShift)].B = v43
            v1[(0x62 - 0)].B = v43; pc = 938; continue
        if pc == 938:  # 188E4: v43 = v43
            v43 = v43; pc = 939; continue
        if pc == 939:  # 188E6: v1[(0x4f - this.ColRightShift)].B = v43
            v1[(0x4f - 0)].B = v43; pc = 940; continue
        if pc == 940:  # 188EE: v43 = v43
            v43 = v43; pc = 941; continue
        if pc == 941:  # 188F0: v1[(0x4e - this.ColRightShift)].B = v43
            v1[(0x4e - 0)].B = v43; pc = 942; continue
        if pc == 942:  # 188F8: v43 = v43
            v43 = v43; pc = 943; continue
        if pc == 943:  # 188FA: v1[(0x3b - this.ColRightShift)].B = v43
            v1[(0x3b - 0)].B = v43; pc = 944; continue
        if pc == 944:  # 18902: v43 = v43
            v43 = v43; pc = 945; continue
        if pc == 945:  # 18904: v1[(0x3a - this.ColRightShift)].B = v43
            v1[(0x3a - 0)].B = v43; pc = 946; continue
        if pc == 946:  # 1890C: v43 = v43
            v43 = v43; pc = 947; continue
        if pc == 947:  # 1890E: v1[(0x23 - this.ColRightShift)].B = v43
            v1[(0x23 - 0)].B = v43; pc = 948; continue
        if pc == 948:  # 18916: v43 = v43
            v43 = v43; pc = 949; continue
        if pc == 949:  # 18918: v1[(0x22 - this.ColRightShift)].B = v43
            v1[(0x22 - 0)].B = v43; pc = 950; continue
        if pc == 950:  # 1891F: v1[(0xd - this.ColRightShift)].B = v43
            v1[(0xd - 0)].B = v43; pc = 951; continue
        if pc == 951:  # 18924: goto 19CA9
            pc = 1393; continue
        if pc == 952:  # 1897B: v43 = v39
            v43 = v39; pc = 953; continue
        if pc == 953:  # 1897D: v1[0x71].R = v39
            v1[0x71].R = v39; pc = 954; continue
        if pc == 954:  # 18985: v43 = v43
            v43 = v43; pc = 955; continue
        if pc == 955:  # 18987: v1[0x5b].R = v43
            v1[0x5b].R = v43; pc = 956; continue
        if pc == 956:  # 1898F: v43 = v43
            v43 = v43; pc = 957; continue
        if pc == 957:  # 18991: v1[0x5a].R = v43
            v1[0x5a].R = v43; pc = 958; continue
        if pc == 958:  # 18999: v43 = v43
            v43 = v43; pc = 959; continue
        if pc == 959:  # 1899B: v1[0x45].R = v43
            v1[0x45].R = v43; pc = 960; continue
        if pc == 960:  # 189A3: v43 = v43
            v43 = v43; pc = 961; continue
        if pc == 961:  # 189A5: v1[0x44].R = v43
            v1[0x44].R = v43; pc = 962; continue
        if pc == 962:  # 189AD: v43 = v43
            v43 = v43; pc = 963; continue
        if pc == 963:  # 189AF: v1[0x2f].R = v43
            v1[0x2f].R = v43; pc = 964; continue
        if pc == 964:  # 189B7: v43 = v43
            v43 = v43; pc = 965; continue
        if pc == 965:  # 189B9: v1[0x2e].R = v43
            v1[0x2e].R = v43; pc = 966; continue
        if pc == 966:  # 189C1: v43 = v43
            v43 = v43; pc = 967; continue
        if pc == 967:  # 189C3: v1[0x1c].R = v43
            v1[0x1c].R = v43; pc = 968; continue
        if pc == 968:  # 189CB: v43 = v43
            v43 = v43; pc = 969; continue
        if pc == 969:  # 189CD: v1[0x1b].R = v43
            v1[0x1b].R = v43; pc = 970; continue
        if pc == 970:  # 189D4: v1[8].R = v43
            v1[8].R = v43; pc = 971; continue
        if pc == 971:  # 18A2B: v43 = v40
            v43 = v40; pc = 972; continue
        if pc == 972:  # 18A2D: v1[0x71].G = v40
            v1[0x71].G = v40; pc = 973; continue
        if pc == 973:  # 18A35: v43 = v43
            v43 = v43; pc = 974; continue
        if pc == 974:  # 18A37: v1[0x5b].G = v43
            v1[0x5b].G = v43; pc = 975; continue
        if pc == 975:  # 18A3F: v43 = v43
            v43 = v43; pc = 976; continue
        if pc == 976:  # 18A41: v1[0x5a].G = v43
            v1[0x5a].G = v43; pc = 977; continue
        if pc == 977:  # 18A49: v43 = v43
            v43 = v43; pc = 978; continue
        if pc == 978:  # 18A4B: v1[0x45].G = v43
            v1[0x45].G = v43; pc = 979; continue
        if pc == 979:  # 18A53: v43 = v43
            v43 = v43; pc = 980; continue
        if pc == 980:  # 18A55: v1[0x44].G = v43
            v1[0x44].G = v43; pc = 981; continue
        if pc == 981:  # 18A5D: v43 = v43
            v43 = v43; pc = 982; continue
        if pc == 982:  # 18A5F: v1[0x2f].G = v43
            v1[0x2f].G = v43; pc = 983; continue
        if pc == 983:  # 18A67: v43 = v43
            v43 = v43; pc = 984; continue
        if pc == 984:  # 18A69: v1[0x2e].G = v43
            v1[0x2e].G = v43; pc = 985; continue
        if pc == 985:  # 18A71: v43 = v43
            v43 = v43; pc = 986; continue
        if pc == 986:  # 18A73: v1[0x1c].G = v43
            v1[0x1c].G = v43; pc = 987; continue
        if pc == 987:  # 18A7B: v43 = v43
            v43 = v43; pc = 988; continue
        if pc == 988:  # 18A7D: v1[0x1b].G = v43
            v1[0x1b].G = v43; pc = 989; continue
        if pc == 989:  # 18A84: v1[8].G = v43
            v1[8].G = v43; pc = 990; continue
        if pc == 990:  # 18ADB: v43 = v41
            v43 = v41; pc = 991; continue
        if pc == 991:  # 18ADD: v1[0x71].B = v41
            v1[0x71].B = v41; pc = 992; continue
        if pc == 992:  # 18AE5: v43 = v43
            v43 = v43; pc = 993; continue
        if pc == 993:  # 18AE7: v1[0x5b].B = v43
            v1[0x5b].B = v43; pc = 994; continue
        if pc == 994:  # 18AEF: v43 = v43
            v43 = v43; pc = 995; continue
        if pc == 995:  # 18AF1: v1[0x5a].B = v43
            v1[0x5a].B = v43; pc = 996; continue
        if pc == 996:  # 18AF9: v43 = v43
            v43 = v43; pc = 997; continue
        if pc == 997:  # 18AFB: v1[0x45].B = v43
            v1[0x45].B = v43; pc = 998; continue
        if pc == 998:  # 18B03: v43 = v43
            v43 = v43; pc = 999; continue
        if pc == 999:  # 18B05: v1[0x44].B = v43
            v1[0x44].B = v43; pc = 1000; continue
        if pc == 1000:  # 18B0D: v43 = v43
            v43 = v43; pc = 1001; continue
        if pc == 1001:  # 18B0F: v1[0x2f].B = v43
            v1[0x2f].B = v43; pc = 1002; continue
        if pc == 1002:  # 18B17: v43 = v43
            v43 = v43; pc = 1003; continue
        if pc == 1003:  # 18B19: v1[0x2e].B = v43
            v1[0x2e].B = v43; pc = 1004; continue
        if pc == 1004:  # 18B21: v43 = v43
            v43 = v43; pc = 1005; continue
        if pc == 1005:  # 18B23: v1[0x1c].B = v43
            v1[0x1c].B = v43; pc = 1006; continue
        if pc == 1006:  # 18B2B: v43 = v43
            v43 = v43; pc = 1007; continue
        if pc == 1007:  # 18B2D: v1[0x1b].B = v43
            v1[0x1b].B = v43; pc = 1008; continue
        if pc == 1008:  # 18B34: v1[8].B = v43
            v1[8].B = v43; pc = 1009; continue
        if pc == 1009:  # 18BD2: v43 = v39
            v43 = v39; pc = 1010; continue
        if pc == 1010:  # 18BD4: v1[(0x75 - this.ColRightShift)].R = v39
            v1[(0x75 - 0)].R = v39; pc = 1011; continue
        if pc == 1011:  # 18BDC: v43 = v43
            v43 = v43; pc = 1012; continue
        if pc == 1012:  # 18BDE: v1[(0x62 - this.ColRightShift)].R = v43
            v1[(0x62 - 0)].R = v43; pc = 1013; continue
        if pc == 1013:  # 18BE6: v43 = v43
            v43 = v43; pc = 1014; continue
        if pc == 1014:  # 18BE8: v1[(0x61 - this.ColRightShift)].R = v43
            v1[(0x61 - 0)].R = v43; pc = 1015; continue
        if pc == 1015:  # 18BF0: v43 = v43
            v43 = v43; pc = 1016; continue
        if pc == 1016:  # 18BF2: v1[(0x4e - this.ColRightShift)].R = v43
            v1[(0x4e - 0)].R = v43; pc = 1017; continue
        if pc == 1017:  # 18BFA: v43 = v43
            v43 = v43; pc = 1018; continue
        if pc == 1018:  # 18BFC: v1[(0x4d - this.ColRightShift)].R = v43
            v1[(0x4d - 0)].R = v43; pc = 1019; continue
        if pc == 1019:  # 18C04: v43 = v43
            v43 = v43; pc = 1020; continue
        if pc == 1020:  # 18C06: v1[(0x3a - this.ColRightShift)].R = v43
            v1[(0x3a - 0)].R = v43; pc = 1021; continue
        if pc == 1021:  # 18C0E: v43 = v43
            v43 = v43; pc = 1022; continue
        if pc == 1022:  # 18C10: v1[(0x39 - this.ColRightShift)].R = v43
            v1[(0x39 - 0)].R = v43; pc = 1023; continue
        if pc == 1023:  # 18C18: v43 = v43
            v43 = v43; pc = 1024; continue
        if pc == 1024:  # 18C1A: v1[(0x22 - this.ColRightShift)].R = v43
            v1[(0x22 - 0)].R = v43; pc = 1025; continue
        if pc == 1025:  # 18C22: v43 = v43
            v43 = v43; pc = 1026; continue
        if pc == 1026:  # 18C24: v1[(0x21 - this.ColRightShift)].R = v43
            v1[(0x21 - 0)].R = v43; pc = 1027; continue
        if pc == 1027:  # 18C2B: v1[(0xc - this.ColRightShift)].R = v43
            v1[(0xc - 0)].R = v43; pc = 1028; continue
        if pc == 1028:  # 18CC9: v43 = v40
            v43 = v40; pc = 1029; continue
        if pc == 1029:  # 18CCB: v1[(0x75 - this.ColRightShift)].G = v40
            v1[(0x75 - 0)].G = v40; pc = 1030; continue
        if pc == 1030:  # 18CD3: v43 = v43
            v43 = v43; pc = 1031; continue
        if pc == 1031:  # 18CD5: v1[(0x62 - this.ColRightShift)].G = v43
            v1[(0x62 - 0)].G = v43; pc = 1032; continue
        if pc == 1032:  # 18CDD: v43 = v43
            v43 = v43; pc = 1033; continue
        if pc == 1033:  # 18CDF: v1[(0x61 - this.ColRightShift)].G = v43
            v1[(0x61 - 0)].G = v43; pc = 1034; continue
        if pc == 1034:  # 18CE7: v43 = v43
            v43 = v43; pc = 1035; continue
        if pc == 1035:  # 18CE9: v1[(0x4e - this.ColRightShift)].G = v43
            v1[(0x4e - 0)].G = v43; pc = 1036; continue
        if pc == 1036:  # 18CF1: v43 = v43
            v43 = v43; pc = 1037; continue
        if pc == 1037:  # 18CF3: v1[(0x4d - this.ColRightShift)].G = v43
            v1[(0x4d - 0)].G = v43; pc = 1038; continue
        if pc == 1038:  # 18CFB: v43 = v43
            v43 = v43; pc = 1039; continue
        if pc == 1039:  # 18CFD: v1[(0x3a - this.ColRightShift)].G = v43
            v1[(0x3a - 0)].G = v43; pc = 1040; continue
        if pc == 1040:  # 18D05: v43 = v43
            v43 = v43; pc = 1041; continue
        if pc == 1041:  # 18D07: v1[(0x39 - this.ColRightShift)].G = v43
            v1[(0x39 - 0)].G = v43; pc = 1042; continue
        if pc == 1042:  # 18D0F: v43 = v43
            v43 = v43; pc = 1043; continue
        if pc == 1043:  # 18D11: v1[(0x22 - this.ColRightShift)].G = v43
            v1[(0x22 - 0)].G = v43; pc = 1044; continue
        if pc == 1044:  # 18D19: v43 = v43
            v43 = v43; pc = 1045; continue
        if pc == 1045:  # 18D1B: v1[(0x21 - this.ColRightShift)].G = v43
            v1[(0x21 - 0)].G = v43; pc = 1046; continue
        if pc == 1046:  # 18D22: v1[(0xc - this.ColRightShift)].G = v43
            v1[(0xc - 0)].G = v43; pc = 1047; continue
        if pc == 1047:  # 18DC0: v43 = v41
            v43 = v41; pc = 1048; continue
        if pc == 1048:  # 18DC2: v1[(0x75 - this.ColRightShift)].B = v41
            v1[(0x75 - 0)].B = v41; pc = 1049; continue
        if pc == 1049:  # 18DCA: v43 = v43
            v43 = v43; pc = 1050; continue
        if pc == 1050:  # 18DCC: v1[(0x62 - this.ColRightShift)].B = v43
            v1[(0x62 - 0)].B = v43; pc = 1051; continue
        if pc == 1051:  # 18DD4: v43 = v43
            v43 = v43; pc = 1052; continue
        if pc == 1052:  # 18DD6: v1[(0x61 - this.ColRightShift)].B = v43
            v1[(0x61 - 0)].B = v43; pc = 1053; continue
        if pc == 1053:  # 18DDE: v43 = v43
            v43 = v43; pc = 1054; continue
        if pc == 1054:  # 18DE0: v1[(0x4e - this.ColRightShift)].B = v43
            v1[(0x4e - 0)].B = v43; pc = 1055; continue
        if pc == 1055:  # 18DE8: v43 = v43
            v43 = v43; pc = 1056; continue
        if pc == 1056:  # 18DEA: v1[(0x4d - this.ColRightShift)].B = v43
            v1[(0x4d - 0)].B = v43; pc = 1057; continue
        if pc == 1057:  # 18DF2: v43 = v43
            v43 = v43; pc = 1058; continue
        if pc == 1058:  # 18DF4: v1[(0x3a - this.ColRightShift)].B = v43
            v1[(0x3a - 0)].B = v43; pc = 1059; continue
        if pc == 1059:  # 18DFC: v43 = v43
            v43 = v43; pc = 1060; continue
        if pc == 1060:  # 18DFE: v1[(0x39 - this.ColRightShift)].B = v43
            v1[(0x39 - 0)].B = v43; pc = 1061; continue
        if pc == 1061:  # 18E06: v43 = v43
            v43 = v43; pc = 1062; continue
        if pc == 1062:  # 18E08: v1[(0x22 - this.ColRightShift)].B = v43
            v1[(0x22 - 0)].B = v43; pc = 1063; continue
        if pc == 1063:  # 18E10: v43 = v43
            v43 = v43; pc = 1064; continue
        if pc == 1064:  # 18E12: v1[(0x21 - this.ColRightShift)].B = v43
            v1[(0x21 - 0)].B = v43; pc = 1065; continue
        if pc == 1065:  # 18E19: v1[(0xc - this.ColRightShift)].B = v43
            v1[(0xc - 0)].B = v43; pc = 1066; continue
        if pc == 1066:  # 18E1E: goto 19CA9
            pc = 1393; continue
        if pc == 1067:  # 18E76: v43 = v39
            v43 = v39; pc = 1068; continue
        if pc == 1068:  # 18E78: v1[0x72].R = v39
            v1[0x72].R = v39; pc = 1069; continue
        if pc == 1069:  # 18E80: v43 = v43
            v43 = v43; pc = 1070; continue
        if pc == 1070:  # 18E82: v1[0x5c].R = v43
            v1[0x5c].R = v43; pc = 1071; continue
        if pc == 1071:  # 18E8A: v43 = v43
            v43 = v43; pc = 1072; continue
        if pc == 1072:  # 18E8C: v1[0x5b].R = v43
            v1[0x5b].R = v43; pc = 1073; continue
        if pc == 1073:  # 18E94: v43 = v43
            v43 = v43; pc = 1074; continue
        if pc == 1074:  # 18E96: v1[0x46].R = v43
            v1[0x46].R = v43; pc = 1075; continue
        if pc == 1075:  # 18E9E: v43 = v43
            v43 = v43; pc = 1076; continue
        if pc == 1076:  # 18EA0: v1[0x45].R = v43
            v1[0x45].R = v43; pc = 1077; continue
        if pc == 1077:  # 18EA8: v43 = v43
            v43 = v43; pc = 1078; continue
        if pc == 1078:  # 18EAA: v1[0x30].R = v43
            v1[0x30].R = v43; pc = 1079; continue
        if pc == 1079:  # 18EB2: v43 = v43
            v43 = v43; pc = 1080; continue
        if pc == 1080:  # 18EB4: v1[0x2f].R = v43
            v1[0x2f].R = v43; pc = 1081; continue
        if pc == 1081:  # 18EBC: v43 = v43
            v43 = v43; pc = 1082; continue
        if pc == 1082:  # 18EBE: v1[0x1d].R = v43
            v1[0x1d].R = v43; pc = 1083; continue
        if pc == 1083:  # 18EC6: v43 = v43
            v43 = v43; pc = 1084; continue
        if pc == 1084:  # 18EC8: v1[0x1c].R = v43
            v1[0x1c].R = v43; pc = 1085; continue
        if pc == 1085:  # 18ECF: v1[9].R = v43
            v1[9].R = v43; pc = 1086; continue
        if pc == 1086:  # 18F27: v43 = v40
            v43 = v40; pc = 1087; continue
        if pc == 1087:  # 18F29: v1[0x72].G = v40
            v1[0x72].G = v40; pc = 1088; continue
        if pc == 1088:  # 18F31: v43 = v43
            v43 = v43; pc = 1089; continue
        if pc == 1089:  # 18F33: v1[0x5c].G = v43
            v1[0x5c].G = v43; pc = 1090; continue
        if pc == 1090:  # 18F3B: v43 = v43
            v43 = v43; pc = 1091; continue
        if pc == 1091:  # 18F3D: v1[0x5b].G = v43
            v1[0x5b].G = v43; pc = 1092; continue
        if pc == 1092:  # 18F45: v43 = v43
            v43 = v43; pc = 1093; continue
        if pc == 1093:  # 18F47: v1[0x46].G = v43
            v1[0x46].G = v43; pc = 1094; continue
        if pc == 1094:  # 18F4F: v43 = v43
            v43 = v43; pc = 1095; continue
        if pc == 1095:  # 18F51: v1[0x45].G = v43
            v1[0x45].G = v43; pc = 1096; continue
        if pc == 1096:  # 18F59: v43 = v43
            v43 = v43; pc = 1097; continue
        if pc == 1097:  # 18F5B: v1[0x30].G = v43
            v1[0x30].G = v43; pc = 1098; continue
        if pc == 1098:  # 18F63: v43 = v43
            v43 = v43; pc = 1099; continue
        if pc == 1099:  # 18F65: v1[0x2f].G = v43
            v1[0x2f].G = v43; pc = 1100; continue
        if pc == 1100:  # 18F6D: v43 = v43
            v43 = v43; pc = 1101; continue
        if pc == 1101:  # 18F6F: v1[0x1d].G = v43
            v1[0x1d].G = v43; pc = 1102; continue
        if pc == 1102:  # 18F77: v43 = v43
            v43 = v43; pc = 1103; continue
        if pc == 1103:  # 18F79: v1[0x1c].G = v43
            v1[0x1c].G = v43; pc = 1104; continue
        if pc == 1104:  # 18F80: v1[9].G = v43
            v1[9].G = v43; pc = 1105; continue
        if pc == 1105:  # 18FD8: v43 = v41
            v43 = v41; pc = 1106; continue
        if pc == 1106:  # 18FDA: v1[0x72].B = v41
            v1[0x72].B = v41; pc = 1107; continue
        if pc == 1107:  # 18FE2: v43 = v43
            v43 = v43; pc = 1108; continue
        if pc == 1108:  # 18FE4: v1[0x5c].B = v43
            v1[0x5c].B = v43; pc = 1109; continue
        if pc == 1109:  # 18FEC: v43 = v43
            v43 = v43; pc = 1110; continue
        if pc == 1110:  # 18FEE: v1[0x5b].B = v43
            v1[0x5b].B = v43; pc = 1111; continue
        if pc == 1111:  # 18FF6: v43 = v43
            v43 = v43; pc = 1112; continue
        if pc == 1112:  # 18FF8: v1[0x46].B = v43
            v1[0x46].B = v43; pc = 1113; continue
        if pc == 1113:  # 19000: v43 = v43
            v43 = v43; pc = 1114; continue
        if pc == 1114:  # 19002: v1[0x45].B = v43
            v1[0x45].B = v43; pc = 1115; continue
        if pc == 1115:  # 1900A: v43 = v43
            v43 = v43; pc = 1116; continue
        if pc == 1116:  # 1900C: v1[0x30].B = v43
            v1[0x30].B = v43; pc = 1117; continue
        if pc == 1117:  # 19014: v43 = v43
            v43 = v43; pc = 1118; continue
        if pc == 1118:  # 19016: v1[0x2f].B = v43
            v1[0x2f].B = v43; pc = 1119; continue
        if pc == 1119:  # 1901E: v43 = v43
            v43 = v43; pc = 1120; continue
        if pc == 1120:  # 19020: v1[0x1d].B = v43
            v1[0x1d].B = v43; pc = 1121; continue
        if pc == 1121:  # 19028: v43 = v43
            v43 = v43; pc = 1122; continue
        if pc == 1122:  # 1902A: v1[0x1c].B = v43
            v1[0x1c].B = v43; pc = 1123; continue
        if pc == 1123:  # 19031: v1[9].B = v43
            v1[9].B = v43; pc = 1124; continue
        if pc == 1124:  # 190CF: v43 = v39
            v43 = v39; pc = 1125; continue
        if pc == 1125:  # 190D1: v1[(0x74 - this.ColRightShift)].R = v39
            v1[(0x74 - 0)].R = v39; pc = 1126; continue
        if pc == 1126:  # 190D9: v43 = v43
            v43 = v43; pc = 1127; continue
        if pc == 1127:  # 190DB: v1[(0x61 - this.ColRightShift)].R = v43
            v1[(0x61 - 0)].R = v43; pc = 1128; continue
        if pc == 1128:  # 190E3: v43 = v43
            v43 = v43; pc = 1129; continue
        if pc == 1129:  # 190E5: v1[(0x60 - this.ColRightShift)].R = v43
            v1[(0x60 - 0)].R = v43; pc = 1130; continue
        if pc == 1130:  # 190ED: v43 = v43
            v43 = v43; pc = 1131; continue
        if pc == 1131:  # 190EF: v1[(0x4d - this.ColRightShift)].R = v43
            v1[(0x4d - 0)].R = v43; pc = 1132; continue
        if pc == 1132:  # 190F7: v43 = v43
            v43 = v43; pc = 1133; continue
        if pc == 1133:  # 190F9: v1[(0x4c - this.ColRightShift)].R = v43
            v1[(0x4c - 0)].R = v43; pc = 1134; continue
        if pc == 1134:  # 19101: v43 = v43
            v43 = v43; pc = 1135; continue
        if pc == 1135:  # 19103: v1[(0x39 - this.ColRightShift)].R = v43
            v1[(0x39 - 0)].R = v43; pc = 1136; continue
        if pc == 1136:  # 1910B: v43 = v43
            v43 = v43; pc = 1137; continue
        if pc == 1137:  # 1910D: v1[(0x38 - this.ColRightShift)].R = v43
            v1[(0x38 - 0)].R = v43; pc = 1138; continue
        if pc == 1138:  # 19115: v43 = v43
            v43 = v43; pc = 1139; continue
        if pc == 1139:  # 19117: v1[(0x21 - this.ColRightShift)].R = v43
            v1[(0x21 - 0)].R = v43; pc = 1140; continue
        if pc == 1140:  # 1911F: v43 = v43
            v43 = v43; pc = 1141; continue
        if pc == 1141:  # 19121: v1[(0x20 - this.ColRightShift)].R = v43
            v1[(0x20 - 0)].R = v43; pc = 1142; continue
        if pc == 1142:  # 19128: v1[(0xb - this.ColRightShift)].R = v43
            v1[(0xb - 0)].R = v43; pc = 1143; continue
        if pc == 1143:  # 191C6: v43 = v40
            v43 = v40; pc = 1144; continue
        if pc == 1144:  # 191C8: v1[(0x74 - this.ColRightShift)].G = v40
            v1[(0x74 - 0)].G = v40; pc = 1145; continue
        if pc == 1145:  # 191D0: v43 = v43
            v43 = v43; pc = 1146; continue
        if pc == 1146:  # 191D2: v1[(0x61 - this.ColRightShift)].G = v43
            v1[(0x61 - 0)].G = v43; pc = 1147; continue
        if pc == 1147:  # 191DA: v43 = v43
            v43 = v43; pc = 1148; continue
        if pc == 1148:  # 191DC: v1[(0x60 - this.ColRightShift)].G = v43
            v1[(0x60 - 0)].G = v43; pc = 1149; continue
        if pc == 1149:  # 191E4: v43 = v43
            v43 = v43; pc = 1150; continue
        if pc == 1150:  # 191E6: v1[(0x4d - this.ColRightShift)].G = v43
            v1[(0x4d - 0)].G = v43; pc = 1151; continue
        if pc == 1151:  # 191EE: v43 = v43
            v43 = v43; pc = 1152; continue
        if pc == 1152:  # 191F0: v1[(0x4c - this.ColRightShift)].G = v43
            v1[(0x4c - 0)].G = v43; pc = 1153; continue
        if pc == 1153:  # 191F8: v43 = v43
            v43 = v43; pc = 1154; continue
        if pc == 1154:  # 191FA: v1[(0x39 - this.ColRightShift)].G = v43
            v1[(0x39 - 0)].G = v43; pc = 1155; continue
        if pc == 1155:  # 19202: v43 = v43
            v43 = v43; pc = 1156; continue
        if pc == 1156:  # 19204: v1[(0x38 - this.ColRightShift)].G = v43
            v1[(0x38 - 0)].G = v43; pc = 1157; continue
        if pc == 1157:  # 1920C: v43 = v43
            v43 = v43; pc = 1158; continue
        if pc == 1158:  # 1920E: v1[(0x21 - this.ColRightShift)].G = v43
            v1[(0x21 - 0)].G = v43; pc = 1159; continue
        if pc == 1159:  # 19216: v43 = v43
            v43 = v43; pc = 1160; continue
        if pc == 1160:  # 19218: v1[(0x20 - this.ColRightShift)].G = v43
            v1[(0x20 - 0)].G = v43; pc = 1161; continue
        if pc == 1161:  # 1921F: v1[(0xb - this.ColRightShift)].G = v43
            v1[(0xb - 0)].G = v43; pc = 1162; continue
        if pc == 1162:  # 192BD: v43 = v41
            v43 = v41; pc = 1163; continue
        if pc == 1163:  # 192BF: v1[(0x74 - this.ColRightShift)].B = v41
            v1[(0x74 - 0)].B = v41; pc = 1164; continue
        if pc == 1164:  # 192C7: v43 = v43
            v43 = v43; pc = 1165; continue
        if pc == 1165:  # 192C9: v1[(0x61 - this.ColRightShift)].B = v43
            v1[(0x61 - 0)].B = v43; pc = 1166; continue
        if pc == 1166:  # 192D1: v43 = v43
            v43 = v43; pc = 1167; continue
        if pc == 1167:  # 192D3: v1[(0x60 - this.ColRightShift)].B = v43
            v1[(0x60 - 0)].B = v43; pc = 1168; continue
        if pc == 1168:  # 192DB: v43 = v43
            v43 = v43; pc = 1169; continue
        if pc == 1169:  # 192DD: v1[(0x4d - this.ColRightShift)].B = v43
            v1[(0x4d - 0)].B = v43; pc = 1170; continue
        if pc == 1170:  # 192E5: v43 = v43
            v43 = v43; pc = 1171; continue
        if pc == 1171:  # 192E7: v1[(0x4c - this.ColRightShift)].B = v43
            v1[(0x4c - 0)].B = v43; pc = 1172; continue
        if pc == 1172:  # 192EF: v43 = v43
            v43 = v43; pc = 1173; continue
        if pc == 1173:  # 192F1: v1[(0x39 - this.ColRightShift)].B = v43
            v1[(0x39 - 0)].B = v43; pc = 1174; continue
        if pc == 1174:  # 192F9: v43 = v43
            v43 = v43; pc = 1175; continue
        if pc == 1175:  # 192FB: v1[(0x38 - this.ColRightShift)].B = v43
            v1[(0x38 - 0)].B = v43; pc = 1176; continue
        if pc == 1176:  # 19303: v43 = v43
            v43 = v43; pc = 1177; continue
        if pc == 1177:  # 19305: v1[(0x21 - this.ColRightShift)].B = v43
            v1[(0x21 - 0)].B = v43; pc = 1178; continue
        if pc == 1178:  # 1930D: v43 = v43
            v43 = v43; pc = 1179; continue
        if pc == 1179:  # 1930F: v1[(0x20 - this.ColRightShift)].B = v43
            v1[(0x20 - 0)].B = v43; pc = 1180; continue
        if pc == 1180:  # 19316: v1[(0xb - this.ColRightShift)].B = v43
            v1[(0xb - 0)].B = v43; pc = 1181; continue
        if pc == 1181:  # 1931B: goto 19CA9
            pc = 1393; continue
        if pc == 1182:  # 1936B: v43 = v39
            v43 = v39; pc = 1183; continue
        if pc == 1183:  # 1936D: v1[0x5d].R = v39
            v1[0x5d].R = v39; pc = 1184; continue
        if pc == 1184:  # 19375: v43 = v43
            v43 = v43; pc = 1185; continue
        if pc == 1185:  # 19377: v1[0x5c].R = v43
            v1[0x5c].R = v43; pc = 1186; continue
        if pc == 1186:  # 1937F: v43 = v43
            v43 = v43; pc = 1187; continue
        if pc == 1187:  # 19381: v1[0x47].R = v43
            v1[0x47].R = v43; pc = 1188; continue
        if pc == 1188:  # 19389: v43 = v43
            v43 = v43; pc = 1189; continue
        if pc == 1189:  # 1938B: v1[0x46].R = v43
            v1[0x46].R = v43; pc = 1190; continue
        if pc == 1190:  # 19393: v43 = v43
            v43 = v43; pc = 1191; continue
        if pc == 1191:  # 19395: v1[0x31].R = v43
            v1[0x31].R = v43; pc = 1192; continue
        if pc == 1192:  # 1939D: v43 = v43
            v43 = v43; pc = 1193; continue
        if pc == 1193:  # 1939F: v1[0x30].R = v43
            v1[0x30].R = v43; pc = 1194; continue
        if pc == 1194:  # 193A7: v43 = v43
            v43 = v43; pc = 1195; continue
        if pc == 1195:  # 193A9: v1[0x1e].R = v43
            v1[0x1e].R = v43; pc = 1196; continue
        if pc == 1196:  # 193B1: v43 = v43
            v43 = v43; pc = 1197; continue
        if pc == 1197:  # 193B3: v1[0x1d].R = v43
            v1[0x1d].R = v43; pc = 1198; continue
        if pc == 1198:  # 193BA: v1[0xa].R = v43
            v1[0xa].R = v43; pc = 1199; continue
        if pc == 1199:  # 1940A: v43 = v40
            v43 = v40; pc = 1200; continue
        if pc == 1200:  # 1940C: v1[0x5d].G = v40
            v1[0x5d].G = v40; pc = 1201; continue
        if pc == 1201:  # 19414: v43 = v43
            v43 = v43; pc = 1202; continue
        if pc == 1202:  # 19416: v1[0x5c].G = v43
            v1[0x5c].G = v43; pc = 1203; continue
        if pc == 1203:  # 1941E: v43 = v43
            v43 = v43; pc = 1204; continue
        if pc == 1204:  # 19420: v1[0x47].G = v43
            v1[0x47].G = v43; pc = 1205; continue
        if pc == 1205:  # 19428: v43 = v43
            v43 = v43; pc = 1206; continue
        if pc == 1206:  # 1942A: v1[0x46].G = v43
            v1[0x46].G = v43; pc = 1207; continue
        if pc == 1207:  # 19432: v43 = v43
            v43 = v43; pc = 1208; continue
        if pc == 1208:  # 19434: v1[0x31].G = v43
            v1[0x31].G = v43; pc = 1209; continue
        if pc == 1209:  # 1943C: v43 = v43
            v43 = v43; pc = 1210; continue
        if pc == 1210:  # 1943E: v1[0x30].G = v43
            v1[0x30].G = v43; pc = 1211; continue
        if pc == 1211:  # 19446: v43 = v43
            v43 = v43; pc = 1212; continue
        if pc == 1212:  # 19448: v1[0x1e].G = v43
            v1[0x1e].G = v43; pc = 1213; continue
        if pc == 1213:  # 19450: v43 = v43
            v43 = v43; pc = 1214; continue
        if pc == 1214:  # 19452: v1[0x1d].G = v43
            v1[0x1d].G = v43; pc = 1215; continue
        if pc == 1215:  # 19459: v1[0xa].G = v43
            v1[0xa].G = v43; pc = 1216; continue
        if pc == 1216:  # 194A9: v43 = v41
            v43 = v41; pc = 1217; continue
        if pc == 1217:  # 194AB: v1[0x5d].B = v41
            v1[0x5d].B = v41; pc = 1218; continue
        if pc == 1218:  # 194B3: v43 = v43
            v43 = v43; pc = 1219; continue
        if pc == 1219:  # 194B5: v1[0x5c].B = v43
            v1[0x5c].B = v43; pc = 1220; continue
        if pc == 1220:  # 194BD: v43 = v43
            v43 = v43; pc = 1221; continue
        if pc == 1221:  # 194BF: v1[0x47].B = v43
            v1[0x47].B = v43; pc = 1222; continue
        if pc == 1222:  # 194C7: v43 = v43
            v43 = v43; pc = 1223; continue
        if pc == 1223:  # 194C9: v1[0x46].B = v43
            v1[0x46].B = v43; pc = 1224; continue
        if pc == 1224:  # 194D1: v43 = v43
            v43 = v43; pc = 1225; continue
        if pc == 1225:  # 194D3: v1[0x31].B = v43
            v1[0x31].B = v43; pc = 1226; continue
        if pc == 1226:  # 194DB: v43 = v43
            v43 = v43; pc = 1227; continue
        if pc == 1227:  # 194DD: v1[0x30].B = v43
            v1[0x30].B = v43; pc = 1228; continue
        if pc == 1228:  # 194E5: v43 = v43
            v43 = v43; pc = 1229; continue
        if pc == 1229:  # 194E7: v1[0x1e].B = v43
            v1[0x1e].B = v43; pc = 1230; continue
        if pc == 1230:  # 194EF: v43 = v43
            v43 = v43; pc = 1231; continue
        if pc == 1231:  # 194F1: v1[0x1d].B = v43
            v1[0x1d].B = v43; pc = 1232; continue
        if pc == 1232:  # 194F8: v1[0xa].B = v43
            v1[0xa].B = v43; pc = 1233; continue
        if pc == 1233:  # 19578: v43 = v39
            v43 = v39; pc = 1234; continue
        if pc == 1234:  # 1957A: v1[(0x60 - this.ColRightShift)].R = v39
            v1[(0x60 - 0)].R = v39; pc = 1235; continue
        if pc == 1235:  # 19582: v43 = v43
            v43 = v43; pc = 1236; continue
        if pc == 1236:  # 19584: v1[(0x5f - this.ColRightShift)].R = v43
            v1[(0x5f - 0)].R = v43; pc = 1237; continue
        if pc == 1237:  # 1958C: v43 = v43
            v43 = v43; pc = 1238; continue
        if pc == 1238:  # 1958E: v1[(0x4c - this.ColRightShift)].R = v43
            v1[(0x4c - 0)].R = v43; pc = 1239; continue
        if pc == 1239:  # 19596: v43 = v43
            v43 = v43; pc = 1240; continue
        if pc == 1240:  # 19598: v1[(0x4b - this.ColRightShift)].R = v43
            v1[(0x4b - 0)].R = v43; pc = 1241; continue
        if pc == 1241:  # 195A0: v43 = v43
            v43 = v43; pc = 1242; continue
        if pc == 1242:  # 195A2: v1[(0x38 - this.ColRightShift)].R = v43
            v1[(0x38 - 0)].R = v43; pc = 1243; continue
        if pc == 1243:  # 195AA: v43 = v43
            v43 = v43; pc = 1244; continue
        if pc == 1244:  # 195AC: v1[(0x37 - this.ColRightShift)].R = v43
            v1[(0x37 - 0)].R = v43; pc = 1245; continue
        if pc == 1245:  # 195B4: v43 = v43
            v43 = v43; pc = 1246; continue
        if pc == 1246:  # 195B6: v1[(0x20 - this.ColRightShift)].R = v43
            v1[(0x20 - 0)].R = v43; pc = 1247; continue
        if pc == 1247:  # 195BD: v1[(0x1f - this.ColRightShift)].R = v43
            v1[(0x1f - 0)].R = v43; pc = 1248; continue
        if pc == 1248:  # 1963D: v43 = v40
            v43 = v40; pc = 1249; continue
        if pc == 1249:  # 1963F: v1[(0x60 - this.ColRightShift)].G = v40
            v1[(0x60 - 0)].G = v40; pc = 1250; continue
        if pc == 1250:  # 19647: v43 = v43
            v43 = v43; pc = 1251; continue
        if pc == 1251:  # 19649: v1[(0x5f - this.ColRightShift)].G = v43
            v1[(0x5f - 0)].G = v43; pc = 1252; continue
        if pc == 1252:  # 19651: v43 = v43
            v43 = v43; pc = 1253; continue
        if pc == 1253:  # 19653: v1[(0x4c - this.ColRightShift)].G = v43
            v1[(0x4c - 0)].G = v43; pc = 1254; continue
        if pc == 1254:  # 1965B: v43 = v43
            v43 = v43; pc = 1255; continue
        if pc == 1255:  # 1965D: v1[(0x4b - this.ColRightShift)].G = v43
            v1[(0x4b - 0)].G = v43; pc = 1256; continue
        if pc == 1256:  # 19665: v43 = v43
            v43 = v43; pc = 1257; continue
        if pc == 1257:  # 19667: v1[(0x38 - this.ColRightShift)].G = v43
            v1[(0x38 - 0)].G = v43; pc = 1258; continue
        if pc == 1258:  # 1966F: v43 = v43
            v43 = v43; pc = 1259; continue
        if pc == 1259:  # 19671: v1[(0x37 - this.ColRightShift)].G = v43
            v1[(0x37 - 0)].G = v43; pc = 1260; continue
        if pc == 1260:  # 19679: v43 = v43
            v43 = v43; pc = 1261; continue
        if pc == 1261:  # 1967B: v1[(0x20 - this.ColRightShift)].G = v43
            v1[(0x20 - 0)].G = v43; pc = 1262; continue
        if pc == 1262:  # 19682: v1[(0x1f - this.ColRightShift)].G = v43
            v1[(0x1f - 0)].G = v43; pc = 1263; continue
        if pc == 1263:  # 19702: v43 = v41
            v43 = v41; pc = 1264; continue
        if pc == 1264:  # 19704: v1[(0x60 - this.ColRightShift)].B = v41
            v1[(0x60 - 0)].B = v41; pc = 1265; continue
        if pc == 1265:  # 1970C: v43 = v43
            v43 = v43; pc = 1266; continue
        if pc == 1266:  # 1970E: v1[(0x5f - this.ColRightShift)].B = v43
            v1[(0x5f - 0)].B = v43; pc = 1267; continue
        if pc == 1267:  # 19716: v43 = v43
            v43 = v43; pc = 1268; continue
        if pc == 1268:  # 19718: v1[(0x4c - this.ColRightShift)].B = v43
            v1[(0x4c - 0)].B = v43; pc = 1269; continue
        if pc == 1269:  # 19720: v43 = v43
            v43 = v43; pc = 1270; continue
        if pc == 1270:  # 19722: v1[(0x4b - this.ColRightShift)].B = v43
            v1[(0x4b - 0)].B = v43; pc = 1271; continue
        if pc == 1271:  # 1972A: v43 = v43
            v43 = v43; pc = 1272; continue
        if pc == 1272:  # 1972C: v1[(0x38 - this.ColRightShift)].B = v43
            v1[(0x38 - 0)].B = v43; pc = 1273; continue
        if pc == 1273:  # 19734: v43 = v43
            v43 = v43; pc = 1274; continue
        if pc == 1274:  # 19736: v1[(0x37 - this.ColRightShift)].B = v43
            v1[(0x37 - 0)].B = v43; pc = 1275; continue
        if pc == 1275:  # 1973E: v43 = v43
            v43 = v43; pc = 1276; continue
        if pc == 1276:  # 19740: v1[(0x20 - this.ColRightShift)].B = v43
            v1[(0x20 - 0)].B = v43; pc = 1277; continue
        if pc == 1277:  # 19747: v1[(0x1f - this.ColRightShift)].B = v43
            v1[(0x1f - 0)].B = v43; pc = 1278; continue
        if pc == 1278:  # 1974C: goto 19CA9
            pc = 1393; continue
        if pc == 1279:  # 19784: v43 = v39
            v43 = v39; pc = 1280; continue
        if pc == 1280:  # 19786: v1[0x5d].R = v39
            v1[0x5d].R = v39; pc = 1281; continue
        if pc == 1281:  # 1978E: v43 = v43
            v43 = v43; pc = 1282; continue
        if pc == 1282:  # 19790: v1[0x48].R = v43
            v1[0x48].R = v43; pc = 1283; continue
        if pc == 1283:  # 19798: v43 = v43
            v43 = v43; pc = 1284; continue
        if pc == 1284:  # 1979A: v1[0x47].R = v43
            v1[0x47].R = v43; pc = 1285; continue
        if pc == 1285:  # 197A2: v43 = v43
            v43 = v43; pc = 1286; continue
        if pc == 1286:  # 197A4: v1[0x32].R = v43
            v1[0x32].R = v43; pc = 1287; continue
        if pc == 1287:  # 197AC: v43 = v43
            v43 = v43; pc = 1288; continue
        if pc == 1288:  # 197AE: v1[0x31].R = v43
            v1[0x31].R = v43; pc = 1289; continue
        if pc == 1289:  # 197B5: v1[0x1e].R = v43
            v1[0x1e].R = v43; pc = 1290; continue
        if pc == 1290:  # 197ED: v43 = v40
            v43 = v40; pc = 1291; continue
        if pc == 1291:  # 197EF: v1[0x5d].G = v40
            v1[0x5d].G = v40; pc = 1292; continue
        if pc == 1292:  # 197F7: v43 = v43
            v43 = v43; pc = 1293; continue
        if pc == 1293:  # 197F9: v1[0x48].G = v43
            v1[0x48].G = v43; pc = 1294; continue
        if pc == 1294:  # 19801: v43 = v43
            v43 = v43; pc = 1295; continue
        if pc == 1295:  # 19803: v1[0x47].G = v43
            v1[0x47].G = v43; pc = 1296; continue
        if pc == 1296:  # 1980B: v43 = v43
            v43 = v43; pc = 1297; continue
        if pc == 1297:  # 1980D: v1[0x32].G = v43
            v1[0x32].G = v43; pc = 1298; continue
        if pc == 1298:  # 19815: v43 = v43
            v43 = v43; pc = 1299; continue
        if pc == 1299:  # 19817: v1[0x31].G = v43
            v1[0x31].G = v43; pc = 1300; continue
        if pc == 1300:  # 1981E: v1[0x1e].G = v43
            v1[0x1e].G = v43; pc = 1301; continue
        if pc == 1301:  # 19856: v43 = v41
            v43 = v41; pc = 1302; continue
        if pc == 1302:  # 19858: v1[0x5d].B = v41
            v1[0x5d].B = v41; pc = 1303; continue
        if pc == 1303:  # 19860: v43 = v43
            v43 = v43; pc = 1304; continue
        if pc == 1304:  # 19862: v1[0x48].B = v43
            v1[0x48].B = v43; pc = 1305; continue
        if pc == 1305:  # 1986A: v43 = v43
            v43 = v43; pc = 1306; continue
        if pc == 1306:  # 1986C: v1[0x47].B = v43
            v1[0x47].B = v43; pc = 1307; continue
        if pc == 1307:  # 19874: v43 = v43
            v43 = v43; pc = 1308; continue
        if pc == 1308:  # 19876: v1[0x32].B = v43
            v1[0x32].B = v43; pc = 1309; continue
        if pc == 1309:  # 1987E: v43 = v43
            v43 = v43; pc = 1310; continue
        if pc == 1310:  # 19880: v1[0x31].B = v43
            v1[0x31].B = v43; pc = 1311; continue
        if pc == 1311:  # 19887: v1[0x1e].B = v43
            v1[0x1e].B = v43; pc = 1312; continue
        if pc == 1312:  # 198E9: v43 = v39
            v43 = v39; pc = 1313; continue
        if pc == 1313:  # 198EB: v1[(0x5e - this.ColRightShift)].R = v39
            v1[(0x5e - 0)].R = v39; pc = 1314; continue
        if pc == 1314:  # 198F3: v43 = v43
            v43 = v43; pc = 1315; continue
        if pc == 1315:  # 198F5: v1[(0x4b - this.ColRightShift)].R = v43
            v1[(0x4b - 0)].R = v43; pc = 1316; continue
        if pc == 1316:  # 198FD: v43 = v43
            v43 = v43; pc = 1317; continue
        if pc == 1317:  # 198FF: v1[(0x4a - this.ColRightShift)].R = v43
            v1[(0x4a - 0)].R = v43; pc = 1318; continue
        if pc == 1318:  # 19907: v43 = v43
            v43 = v43; pc = 1319; continue
        if pc == 1319:  # 19909: v1[(0x37 - this.ColRightShift)].R = v43
            v1[(0x37 - 0)].R = v43; pc = 1320; continue
        if pc == 1320:  # 19911: v43 = v43
            v43 = v43; pc = 1321; continue
        if pc == 1321:  # 19913: v1[(0x36 - this.ColRightShift)].R = v43
            v1[(0x36 - 0)].R = v43; pc = 1322; continue
        if pc == 1322:  # 1991A: v1[(0x1f - this.ColRightShift)].R = v43
            v1[(0x1f - 0)].R = v43; pc = 1323; continue
        if pc == 1323:  # 1997C: v43 = v40
            v43 = v40; pc = 1324; continue
        if pc == 1324:  # 1997E: v1[(0x5e - this.ColRightShift)].G = v40
            v1[(0x5e - 0)].G = v40; pc = 1325; continue
        if pc == 1325:  # 19986: v43 = v43
            v43 = v43; pc = 1326; continue
        if pc == 1326:  # 19988: v1[(0x4b - this.ColRightShift)].G = v43
            v1[(0x4b - 0)].G = v43; pc = 1327; continue
        if pc == 1327:  # 19990: v43 = v43
            v43 = v43; pc = 1328; continue
        if pc == 1328:  # 19992: v1[(0x4a - this.ColRightShift)].G = v43
            v1[(0x4a - 0)].G = v43; pc = 1329; continue
        if pc == 1329:  # 1999A: v43 = v43
            v43 = v43; pc = 1330; continue
        if pc == 1330:  # 1999C: v1[(0x37 - this.ColRightShift)].G = v43
            v1[(0x37 - 0)].G = v43; pc = 1331; continue
        if pc == 1331:  # 199A4: v43 = v43
            v43 = v43; pc = 1332; continue
        if pc == 1332:  # 199A6: v1[(0x36 - this.ColRightShift)].G = v43
            v1[(0x36 - 0)].G = v43; pc = 1333; continue
        if pc == 1333:  # 199AD: v1[(0x1f - this.ColRightShift)].G = v43
            v1[(0x1f - 0)].G = v43; pc = 1334; continue
        if pc == 1334:  # 19A0F: v43 = v41
            v43 = v41; pc = 1335; continue
        if pc == 1335:  # 19A11: v1[(0x5e - this.ColRightShift)].B = v41
            v1[(0x5e - 0)].B = v41; pc = 1336; continue
        if pc == 1336:  # 19A19: v43 = v43
            v43 = v43; pc = 1337; continue
        if pc == 1337:  # 19A1B: v1[(0x4b - this.ColRightShift)].B = v43
            v1[(0x4b - 0)].B = v43; pc = 1338; continue
        if pc == 1338:  # 19A23: v43 = v43
            v43 = v43; pc = 1339; continue
        if pc == 1339:  # 19A25: v1[(0x4a - this.ColRightShift)].B = v43
            v1[(0x4a - 0)].B = v43; pc = 1340; continue
        if pc == 1340:  # 19A2D: v43 = v43
            v43 = v43; pc = 1341; continue
        if pc == 1341:  # 19A2F: v1[(0x37 - this.ColRightShift)].B = v43
            v1[(0x37 - 0)].B = v43; pc = 1342; continue
        if pc == 1342:  # 19A37: v43 = v43
            v43 = v43; pc = 1343; continue
        if pc == 1343:  # 19A39: v1[(0x36 - this.ColRightShift)].B = v43
            v1[(0x36 - 0)].B = v43; pc = 1344; continue
        if pc == 1344:  # 19A40: v1[(0x1f - this.ColRightShift)].B = v43
            v1[(0x1f - 0)].B = v43; pc = 1345; continue
        if pc == 1345:  # 19A45: goto 19CA9
            pc = 1393; continue
        if pc == 1346:  # 19A65: v43 = v39
            v43 = v39; pc = 1347; continue
        if pc == 1347:  # 19A67: v1[0x48].R = v39
            v1[0x48].R = v39; pc = 1348; continue
        if pc == 1348:  # 19A6F: v43 = v43
            v43 = v43; pc = 1349; continue
        if pc == 1349:  # 19A71: v1[0x33].R = v43
            v1[0x33].R = v43; pc = 1350; continue
        if pc == 1350:  # 19A78: v1[0x32].R = v43
            v1[0x32].R = v43; pc = 1351; continue
        if pc == 1351:  # 19A98: v43 = v40
            v43 = v40; pc = 1352; continue
        if pc == 1352:  # 19A9A: v1[0x48].G = v40
            v1[0x48].G = v40; pc = 1353; continue
        if pc == 1353:  # 19AA2: v43 = v43
            v43 = v43; pc = 1354; continue
        if pc == 1354:  # 19AA4: v1[0x33].G = v43
            v1[0x33].G = v43; pc = 1355; continue
        if pc == 1355:  # 19AAB: v1[0x32].G = v43
            v1[0x32].G = v43; pc = 1356; continue
        if pc == 1356:  # 19ACB: v43 = v41
            v43 = v41; pc = 1357; continue
        if pc == 1357:  # 19ACD: v1[0x48].B = v41
            v1[0x48].B = v41; pc = 1358; continue
        if pc == 1358:  # 19AD5: v43 = v43
            v43 = v43; pc = 1359; continue
        if pc == 1359:  # 19AD7: v1[0x33].B = v43
            v1[0x33].B = v43; pc = 1360; continue
        if pc == 1360:  # 19ADE: v1[0x32].B = v43
            v1[0x32].B = v43; pc = 1361; continue
        if pc == 1361:  # 19B13: v43 = v39
            v43 = v39; pc = 1362; continue
        if pc == 1362:  # 19B15: v1[(0x49 - this.ColRightShift)].R = v39
            v1[(0x49 - 0)].R = v39; pc = 1363; continue
        if pc == 1363:  # 19B1D: v43 = v43
            v43 = v43; pc = 1364; continue
        if pc == 1364:  # 19B1F: v1[(0x36 - this.ColRightShift)].R = v43
            v1[(0x36 - 0)].R = v43; pc = 1365; continue
        if pc == 1365:  # 19B26: v1[(0x35 - this.ColRightShift)].R = v43
            v1[(0x35 - 0)].R = v43; pc = 1366; continue
        if pc == 1366:  # 19B5B: v43 = v40
            v43 = v40; pc = 1367; continue
        if pc == 1367:  # 19B5D: v1[(0x49 - this.ColRightShift)].G = v40
            v1[(0x49 - 0)].G = v40; pc = 1368; continue
        if pc == 1368:  # 19B65: v43 = v43
            v43 = v43; pc = 1369; continue
        if pc == 1369:  # 19B67: v1[(0x36 - this.ColRightShift)].G = v43
            v1[(0x36 - 0)].G = v43; pc = 1370; continue
        if pc == 1370:  # 19B6E: v1[(0x35 - this.ColRightShift)].G = v43
            v1[(0x35 - 0)].G = v43; pc = 1371; continue
        if pc == 1371:  # 19BA3: v43 = v41
            v43 = v41; pc = 1372; continue
        if pc == 1372:  # 19BA5: v1[(0x49 - this.ColRightShift)].B = v41
            v1[(0x49 - 0)].B = v41; pc = 1373; continue
        if pc == 1373:  # 19BAD: v43 = v43
            v43 = v43; pc = 1374; continue
        if pc == 1374:  # 19BAF: v1[(0x36 - this.ColRightShift)].B = v43
            v1[(0x36 - 0)].B = v43; pc = 1375; continue
        if pc == 1375:  # 19BB6: v1[(0x35 - this.ColRightShift)].B = v43
            v1[(0x35 - 0)].B = v43; pc = 1376; continue
        if pc == 1376:  # 19BBB: goto 19CA9
            pc = 1393; continue
        if pc == 1377:  # 19BD3: v43 = v39
            v43 = v39; pc = 1378; continue
        if pc == 1378:  # 19BD5: v1[0x34].R = v39
            v1[0x34].R = v39; pc = 1379; continue
        if pc == 1379:  # 19BDC: v1[0x33].R = v43
            v1[0x33].R = v43; pc = 1380; continue
        if pc == 1380:  # 19BF4: v43 = v40
            v43 = v40; pc = 1381; continue
        if pc == 1381:  # 19BF6: v1[0x34].G = v40
            v1[0x34].G = v40; pc = 1382; continue
        if pc == 1382:  # 19BFD: v1[0x33].G = v43
            v1[0x33].G = v43; pc = 1383; continue
        if pc == 1383:  # 19C15: v43 = v41
            v43 = v41; pc = 1384; continue
        if pc == 1384:  # 19C17: v1[0x34].B = v41
            v1[0x34].B = v41; pc = 1385; continue
        if pc == 1385:  # 19C1E: v1[0x33].B = v43
            v1[0x33].B = v43; pc = 1386; continue
        if pc == 1386:  # 19C34: v1[(0x35 - this.ColRightShift)].R = v39
            v1[(0x35 - 0)].R = v39; pc = 1387; continue
        if pc == 1387:  # 19C4A: v1[(0x35 - this.ColRightShift)].G = v40
            v1[(0x35 - 0)].G = v40; pc = 1388; continue
        if pc == 1388:  # 19C60: v1[(0x35 - this.ColRightShift)].B = v41
            v1[(0x35 - 0)].B = v41; pc = 1389; continue
        if pc == 1389:  # 19C65: goto 19CA9
            pc = 1393; continue
        if pc == 1390:  # 19C78: v1[(0x34 - this.ColShift)].R = v39
            v1[(0x34 - 0)].R = v39; pc = 1391; continue
        if pc == 1391:  # 19C8E: v1[(0x34 - this.ColShift)].G = v40
            v1[(0x34 - 0)].G = v40; pc = 1392; continue
        if pc == 1392:  # 19CA4: v1[(0x34 - this.ColShift)].B = v41
            v1[(0x34 - 0)].B = v41; pc = 1393; continue
        if pc == 1393:  # 19CBD: this.Set_ITE_Effect_Type_UserMode(this.m_ap_effect_data.save_light, 0, v1, v3)
            ctx.user_mode(v1, v3); pc = 1394; continue
        if pc == 1394:  # 19CCC: Thread.Sleep((0x14 * this.m_ap_effect_data.save_speed))
            if not ctx.sleep((0x14 * ctx.speed)): return
            pc = 1395; continue
        if pc == 1395:  # 19CD5: v4 = (v4 + 1)
            v4 = (v4 + 1); pc = 1396; continue
        if pc == 1396:  # 19CDD: if (v4 != (v36 * 3)) goto 19CE2
            pc = 1398 if (v4 != (v36 * 3)) else 1397; continue
        if pc == 1397:  # 19CE0: v4 = 0
            v4 = 0; pc = 1398; continue
        if pc == 1398:  # 19CEF: if (this.m_ap_effect_data.save_effect == 0xc) goto 19CF4
            pc = 1400 if (ctx.effect == 0xc) else 1399; continue
        if pc == 1399:  # 19CF2: v4 = 0
            v4 = 0; pc = 1400; continue
        if pc == 1400:  # 19CF5: v3 = 0
            v3 = 0; pc = 1401; continue
        if pc == 1401:  # 19CFD: if (this.m_effect_type != 4) goto 19D0A
            pc = 1403 if ctx.stopped() else 1402; continue
        if pc == 1402:  # 19D05: if (!this.m_ap_effect_task_stop) goto 14F3A
            pc = 0 if not ctx.stopped() else 1403; continue
        if pc == 1403:  # 19D0C: this.m_ap_effect_task = null
            pc = 1404; continue
        if pc == 1404:  # 19D11: return
            return
        if pc >= 1405:
            return
