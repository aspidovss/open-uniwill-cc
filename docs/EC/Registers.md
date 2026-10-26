# EC registers — MAIBENBEN Tsunami X629 (Uniwill, project 0x10)

**English** · [Русский](Registers.ru.md)

Reference of the embedded controller (EC) registers used by open-uniwill-cc.
The "on the Tsunami" values were read on a real laptop on 2026-10-26: BIOS N.1.23A14, Windows 11, Office mode,
liquid cooler connected. All addresses are 16-bit addresses of the controller RAM (the same space as the firmware
methods `ECRR/ECRW`).

> ⚠ Writing to the EC changes the laptop's behaviour immediately (fans, power, charging). Write only registers marked
> "write", and only with values described here. EC registers are reset when power is removed; the open-uniwill-cc
> service applies its settings again on start and after sleep.

## 1. Platform

| Register | On the Tsunami | Meaning |
|---|---|---|
| | **Model** | MAIBENBEN Tsunami Series (X629), board MAIBENBEN |
| | **BIOS** | N.1.23A14 |
| `0x740` PROJECT_ID | `0x10` | Uniwill project number; selects the platform |
| `0x74C` BIOS_PROJECT_ID | `0xC1` | project number written by the BIOS |
| `0x7CA` | `0x01` | bit0 — 6-bit project number |
| `0x456` SYSTEM_ID | `0xC8` | system ID (bit7) |
| `0x771` / `0x772` ROM_ID | `0xFF` / `0xFF` | EC firmware ID (not filled in) |
| `0x7D2` GPU_MODULE_ID | `0x13` | GPU module ID |
| `0x7D3` MODULE_ID | `0x00` | module ID |
| `0x78E` EC_CAPS | `0xFC` | bit4 RGB light bar, bit6 RamFan 1.5 (fan tables in RAM), bit7 LED vendor |
| `0x742` EC_CAPS | `0x02` | bit5 = 0 → Type-C charging priority **not supported** |
| `0x49F` ADAPTER_CAPS | `0x02` | bit1 — Turbo mode supported; bits3..6 — adapter power code |
| `0x741` AP_EXIST | `0x09` | bit0 — control application running, bit3 — the EC passes key presses to the keyboard (Reactive effects) — **write** |

Other hardware: ITE keyboard `CE00` (four-zone, `0x73C = 0x07`), ITE light bar `7000`, NVIDIA GPU
(150 W limit, 175 W with Dynamic Boost), XMG Oasis-type liquid cooler over Bluetooth.

## 2. Modes and fans

### 2.1 Mode — `0x751` FAN_MODE (write)
| Value | Mode |
|---|---|
| `0x00` | Gaming (and Custom together with `0x726` bit7) |
| `0xA0` | Office (bit7 + bit5) |
| `0x10` | Turbo |
| `+0x40` (bit6) | Fan Boost — both fans at maximum |

On the Tsunami: `0xA0` (Office). The service writes Super performance as `0x10 | FanBoost` and clears `0x726` bit7.

`0x726` — bit3 "power on with AC" (when the BIOS does not keep it itself), bits4..5 protection, bit6 thermal
protection, bit7 Custom mode. On the Tsunami `0x00`.

### 2.2 Fan speed and duty (read only)
| Register | On the Tsunami | Formula |
|---|---|---|
| `0x464` / `0x465` | `0x06` `0xC1` | CPU rpm = `0x464 << 8 | 0x465` → 1729 rpm |
| `0x46B` / `0x46C` | `0x32` `0x00` | GPU rpm = `0x46C << 8 | 0x46B` |
| `0x75B` | `0x3C` | CPU duty × 2 → 30 % |
| `0x75C` | `0x00` | GPU duty × 2 |

### 2.3 Table control
| Register | On the Tsunami | Meaning |
|---|---|---|
| `0x7C6` bit2 | `0x04` | fan table from RAM is active (otherwise the EC uses its own) — **write** |
| `0x7C5` bit7 | `0x80` | separate CPU and GPU curves; bit4 — skip the safety protection — **write** |
| `0x787` | `0x00` | fan switch speed: bit7 on, bits0..6 = rpm / 100 — **write** |
| `0x7A5` | `0x00` | bit3 — fan safety protection triggered |

### 2.4 Fan table `0xF00–0xF5F` (RamFan 1.5)
16 levels for the CPU and 16 for the GPU, 3 arrays each:

| Addresses | CPU | GPU | Contents |
|---|---|---|---|
| UpT | `0xF00–0xF0F` | `0xF30–0xF3F` | `[i]` = start temperature of level `i+1`, `0xFF` — no such level |
| DownT | `0xF10–0xF1F` | `0xF40–0xF4F` | `[i+1]` = temperature to drop back from level `i` |
| Duty | `0xF20–0xF2F` | `0xF50–0xF5F`* | `[i]` = duty of level `i` × 2 (0..200), `0xFF` — no such level |

\* `0xF5D–0xF5F` also serve as a handshake: to make the EC load its own table (for example for the liquid cooler),
write the code to `0xF5F` (Office 7, Gaming 6, Turbo 5), then `0xF5D = 0xFD`, `0xF5E = 0xC9`, and wait until the EC
replaces these values.

Writing your own table (as the original does): `0x7C6` bit2 = 0 → separate curves `0x7C5` bit7 → 96 table bytes →
`0x7C6` bit2 = 1.

At the time of the snapshot the EC liquid-cooling table was loaded (3 levels):

| Level | On, °C | Off, °C | Duty |
|---|---|---|---|
| 0 | — | 48 | 0 % |
| 1 | 55 | 67 | 30 % |
| 2 | 66 | 76 | 40 % |
| 3 | 75 | — | 55 % |

## 3. CPU power

| Register | On the Tsunami | Meaning |
|---|---|---|
| `0x783` PL1 | 45 | applied PL1, W — **write** (0 on battery = EC limits) |
| `0x784` PL2 | 50 | applied PL2, W — **write** |
| `0x785` PL4 | 150 | applied PL4, W — **write** |
| `0x786` TCC | `0x94` | bit7 on, bits0..6 — °C below TjMax (`0x94` = on, 20 °C) — **write** |
| `0x730–0x733` | 75 / 75 / 250 / 1 | factory Gaming: PL1 / PL2 / PL4 / DState |
| `0x734–0x737` | 45 / 45 / 250 / 1 | factory Office |
| `0x7A7–0x7AA` | 160 / 160 / 250 / 1 | factory Turbo |
| `0x738` | 0 | default Tau |
| `0x7D8–0x7DA` | 5 / … | default TCC: Gaming / Office / Turbo |

Observation: the upper PL1/PL2 slider limit (`pl1_max = 160`) equals the factory Turbo PL1 (`0x7A7`).

## 4. GPU

| Register | Office | Turbo + Super | Meaning |
|---|---|---|---|
| `0x743` | `0x03` | `0x05` | bit0 Dynamic Boost function, bit1 DB enabled, bit2 cTGP function — **write** |
| `0x744` | 0 | 0 | cTGP above the base, W — **write** |
| `0x745` | 255 | 0 | Dynamic Boost TPP, W — **write** |
| `0x746` | 25 | 0 | Dynamic Boost max TGP, W — **write** |
| `0x78B` | 0 | 0 | GPU DState |

GPU limit reported by `nvidia-smi`: 150 W normally, 175 W with Dynamic Boost / Super performance (maximum 175 W).
The limit table (`TGP 150`, `DB max 25`, TCC per mode) is not in the EC but in the firmware method `SMRW` (section 8).

## 5. Battery

| Register | On the Tsunami | Meaning |
|---|---|---|
| `0x7B9` | `0x5F` | upper charge limit: bits0..6 % (`0` = 100 %), keep bit7 → 95 % — **write** |
| `0x7D0` | `0x50` | lower charge limit 1..95 % → 80 % — **write** |
| `0x7A6` bits4..5 | `0x28` | protection mode: `00` full capacity, `01` balanced, `10` stationary → stationary — **write** |
| `0x7CC` bit7 | `0x00` | Type-C priority (not supported on the Tsunami, see `0x742`) |
| `0x408` / `0x409` | `0x60` `0x3B` | design voltage = `0x409 << 8 | 0x408` → 15200 mV |
| `0x4A6` / `0x4A7` | `0x4E` `0x00` | charge cycles → 78 |
| `0x434` / `0x435` | | battery current |
| `0x494` | `0x00` | battery alert |

## 6. Switches and lighting

| Register | On the Tsunami | Meaning |
|---|---|---|
| `0x74E` bit4 | `0x01` | Fn Lock — **write** |
| `0x767` | `0x00` | bit0 — Win lock trigger, bit1 — light bar trigger, bit4 — USB charging in sleep — **write** |
| `0x768` | `0x00` | bit0 — Win key locked, bit1 — light bar on |
| `0x7A6` | `0x28` | bit3 — touchpad LED, bit6 — touchpad toggle off — **write** |
| `0x78C` | `0x00` | single-colour backlight: bit1 off, bit4 valid, bits5..7 level (the Tsunami is RGB, unused) |
| `0x766` | `0x90` | bit2 — RGB keyboard through the EC (not on the Tsunami, the keyboard is HID) |
| `0x73C` / `0x73D` | `0x07` / `0x00` | ITE keyboard sub-type / LED vendor |

## 7. Liquid cooler

| Register | On the Tsunami | Meaning |
|---|---|---|
| `0x7A4` bit7 | `0x80` | the laptop supports liquid cooling |
| `0x7C8` bit5 | `0x20` | the EC publishes cooler targets and has a fan table for it |
| `0x7C7` | `0x12` | bit1 — cooler attached (set by the service), bits2..4 — **power level (chosen by the EC)**: `0x12` → 4, `0x0E` → 3 |
| `0x7E6` | `0xA8` | EC target: cooler fan, bit7 valid → 40 % |
| `0x7E7` | `0x87` | EC target: pump, bit7 valid → 7 V |
| `0x706`, `0x708`, `0x709`, `0x718` | `0x41`, `0x01`, `0x05`, `0x00` | liquid overclocking state (meaning not fully known) |

The EC only publishes the level in `0x7C7`. To take effect it must be passed to the firmware method `PWUP(level)`
(section 8). The level cannot be written to `0x7C7` — the EC restores its own value immediately (verified).

## 8. Firmware methods (not EC registers)

ACPI device `INOU0000`, methods in the DSDT:

| Method | What it does | How to call it |
|---|---|---|
| `ECRR(addr)` | read an EC byte | OEM driver IOCTL `0x9C40A488`; Linux `/dev/uwcc` |
| `ECRW(addr, data)` | write an EC byte | OEM driver IOCTL `0x9C40A48C`; Linux `/dev/uwcc` |
| `SMRW({0xBB, key})` | Smart APC table: PL, TCC, TGP, Dynamic Boost limits | OEM driver IOCTL `0x9C40A500`; Linux `/dev/uwcc` |
| `PWUP(level)` | liquid-cooling power level: GPU power straps, NVIDIA platform baseline (`NPCF`) | OEM driver IOCTL `0x9C40A504` (name `"PUWP"`); Linux `/dev/uwcc` |
| `WMBC` → `OEMG` → `RKBC/WKBC` | EC read/write through WMI (`AcpiTest_MULong.GetSetULong`) | Windows built-in driver `wmiacpi.sys` |

`PWUP` measured on the Tsunami (Turbo + Super performance + FanBoost, full GPU load):

| Level | GPU limit | Clock | Temp. |
|---|---|---|---|
| 0 | 160 W | 1855–1859 MHz | 71 °C |
| 4 | 175 W | 2114–2144 MHz | 79 °C |
| 5 | 175 W | 2101–2193 MHz | 76–80 °C |
| Office, level 4 (for comparison) | 150 W | 2002–2058 MHz | 72 °C |

Level 4 vs 0 gives +15 W of limit and about +13–15 % clock; 5 vs 4 is within run-to-run spread.

## 9. Examples

### Windows: OEM driver (Python + ctypes)
```python
import ctypes, struct
k = ctypes.WinDLL("kernel32")
h = k.CreateFileW(r"\\.\ACPIDriver", 0xC0000000, 3, None, 3, 0, None)
out = ctypes.create_string_buffer(4); n = ctypes.c_ulong()
k.DeviceIoControl(h, 0x9C40A488, struct.pack("<i", 0x740), 4, out, 4, ctypes.byref(n), None)
print(hex(out.raw[0]))          # 0x10
```

### Windows: WMI without a driver
```powershell
$i = Get-CimInstance -Namespace root\WMI -ClassName AcpiTest_MULong | Where-Object InstanceName -like "*1_1"
# read 0x740: Data = (1 << 40) | address
(Invoke-CimMethod -InputObject $i -MethodName GetSetULong -Arguments @{Data=[uint64]((1L -shl 40) -bor 0x740)}).Return -band 0xFF
# write 0x74E = 0x11 (Fn Lock on): Data = (value << 16) | address
Invoke-CimMethod -InputObject $i -MethodName GetSetULong -Arguments @{Data=[uint64]((0x11L -shl 16) -bor 0x74E)}
```

### open-uniwill-cc
```bash
uwccctl ec read 740                  # through the service
sudo uwccctl ec-direct read 783 5    # Linux, without the service
sudo uwccctl ec-direct dump 700
```

### ec_tool.py (this folder)
```powershell
python ec_tool.py info
python ec_tool.py decode power gpu
python ec_tool.py read 0x783-0x787
python ec_tool.py fantable
python ec_tool.py watch 0x464 0x465 0x75B --interval 1 --count 60 --csv fans.csv
python ec_tool.py bit 0x74E 4 on --restore 5
python ec_tool.py --backend wmi compare --with driver
```
