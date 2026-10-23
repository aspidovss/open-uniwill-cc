"""EC RAM register map (16-bit addresses) used by GCUService for the RamFan1p5_CML platform."""

# --- identification -------------------------------------------------------
BAT_DESIGN_VOLT_L = 0x408   # +0x409 high
BAT_CURRENT_L = 0x434       # +0x435 high
SYSTEM_ID = 0x456           # & 0x80
CPU_FAN_RPM_H = 0x464       # +0x465 low
GPU_FAN_RPM_L = 0x46B       # +0x46C high
BAT_ALERT = 0x494
ADAPTER_CAPS = 0x49F        # bit1 turbo support, bits3..6 adapter watt
BAT_CYCLE_L = 0x4A6         # +0x4A7 high

CUSTOM_MODE = 0x706
HWOC_708 = 0x708
HWOC_709 = 0x709
HWOC_718 = 0x718
BALANCED_PROTECT = 0x726    # bit3 AC-recovery (no-BIOS path), bits4..5 protect mode, bit6 thermal protected
PL_DEF_GAMING = 0x730       # PL1, PL2, PL4, DState (4 bytes)
PL_DEF_OFFICE = 0x734       # PL1, PL2, PL4, DState
TAU_DEF = 0x738
KB_ID = 0x73C               # ITE keyboard sub-type
LED_VENDOR_2 = 0x73D
PROJECT_ID = 0x740
AP_EXIST = 0x741            # bit0: control application present
EC_CAPS_742 = 0x742         # bit2/3/6/7 LED vendor, bit5 Type-C adaptor priority support
GPU_FEAT_CTRL = 0x743       # bit0 DB fun-ctrl, bit1 DB enable, bit2 cTGP fun-ctrl
GPU_CTGP_TARGET = 0x744
GPU_DB_TPP_TARGET = 0x745
GPU_DB_MAX_TGP = 0x746
FN_LOCK = 0x74E             # bit4
BIOS_PROJECT_ID = 0x74C
FAN_MODE = 0x751            # bit4 turbo, bit7 office(+bit5), bit6 FanBoost
CPU_FAN_DUTY = 0x75B        # /2 -> percent
GPU_FAN_DUTY = 0x75C
EC_CAPS_766 = 0x766         # bit2 EC RGB keyboard
TRIGGER_767 = 0x767         # bit0 WinKey trigger, bit1 LightBar trigger, bit4 USB charging
STATUS_768 = 0x768          # bit0 WinKey locked, bit1 LightBar on
ROM_ID = 0x771
ROM_ID2 = 0x772
DEFAULT_MODE = 0x782        # bit4 default gaming, bit1 Q-key define
PL1 = 0x783
PL2 = 0x784
PL4 = 0x785
TCC_OFFSET = 0x786          # bit7 enable
FAN_SWITCH_SPEED = 0x787    # bit7 enable
GPU_DSTATE = 0x78B
KB_SINGLE = 0x78C           # bit1 off, bit4 valid, bits5..7 level
EC_CAPS_78E = 0x78E         # bit4 RGB lightbar, bit6 RamFan1p5, bit7 LED vendor
TOUCHPAD = 0x7A6            # bit3 LED, bit4/5 battery health mode, bit6 touchpad toggle OFF
PL_DEF_TURBO = 0x7A7        # PL1, PL2, PL4, DState
FAN_SAFETY = 0x7A5          # bit7 power status
CHARGE_LIMIT_UP = 0x7B9     # bits0..6 (0 = 100%), bit7 kept
FAN_CTRL_7C5 = 0x7C5        # bit4 skip safety abnormal protection, bit7 fan control respective
FAN_CTRL_7C6 = 0x7C6        # bit2 custom fan table active
EC_CAPS_7C8 = 0x7C8
EC_CAPS_7CA = 0x7CA         # bit0 6-bit BIOS project id
TYPEC_PRIO = 0x7CC          # bit7
CHARGE_LIMIT_DOWN = 0x7D0   # 1..95
GPU_MODULE_ID = 0x7D2
MODULE_ID = 0x7D3
TCC_DEF = 0x7D8

# --- fan tables (RamFan 1.5) ---------------------------------------------
FT_CPU_UP = 0xF00     # [i] = UpT of level i+1 (0xFF = unused)
FT_CPU_DOWN = 0xF10   # [i+1] = DownT of level i
FT_CPU_DUTY = 0xF20   # duty*2 (0..200)
FT_GPU_UP = 0xF30
FT_GPU_DOWN = 0xF40
FT_GPU_DUTY = 0xF50
FT_HS_A = 0xF5D       # handshake: write 0xFD/0xC9, EC clears when ready
FT_HS_B = 0xF5E
FT_HS_MODE = 0xF5F    # 1 turbo, 2 gaming, 3 office

# --- operating modes -------------------------------------------------------
MODE_OFFICE = 0
MODE_GAMING = 1
MODE_TURBO = 2

# value written to FAN_MODE for each mode (before the FanBoost bit)
MODE_BYTE = {MODE_GAMING: 0x00, MODE_OFFICE: 0xA0, MODE_TURBO: 0x10}

# WMI event codes (AcpiTest_EventULong)
EV_WINKEY_LOCK = 0x40
EV_WINKEY_UNLOCK = 0x41
EV_KB_BACKLIGHT = (0x3B, 0x3C, 0x3D, 0x3E, 0x3F)
EV_LIGHTBAR_ON = 0x39
EV_LIGHTBAR_OFF = 0x3A
EV_AIRPLANE = 0xA4
EV_FAN_BOOST = 0xA7
EV_FAN_BOOST_OFF = 0xAA
EV_MODE_SWITCH = 0xB0
EV_SINGLE_KB_LEVEL = 0xB3
EV_SINGLE_KB_POWER = 0xB4
EV_MIC_MUTE = 0xB7
EV_FNLOCK = 0xB8
EV_LAUNCH_APP = 0xBA
EV_SAFETY = 0xBB
EV_PROTECT = 0xCB

# Liquid cooler (GCUService.MyFan.BTCooling.LiquidCooling)
LC_SUPPORT = 0x7A4         # bit7: IsSupportLiquidCooling
LC_CONNECTED = 0x7C7       # bit1: SetECSupport — the service tells the EC a cooler is attached
LC_TABLE_SUPPORT = 0x7C8   # bit5: IsSupportLCFanTable — EC publishes cooler targets below
LC_EC_FAN = 0x7E6          # bit7 valid, bits0-6 fan duty %
LC_EC_PUMP = 0x7E7         # bit7 valid, bits0-6 pump voltage (0/7/8/11/12)
EV_LC_FAN_BOOST = 0xCD     # Fn key: cooler fan boost toggle
EV_LC_PUMP_BOOST = 0xCE    # Fn key: cooler pump boost toggle
EV_HWOC = 0xC2             # EC changed the liquid-cooling OC power level (0x7C7 bits 2..4)
