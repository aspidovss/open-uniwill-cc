# EC access: OEM driver vs WMI — MAIBENBEN Tsunami X629

**English** · [Русский](WMI-vs-Driver.ru.md)

Based on tests on a real laptop on 2026-10-26 (BIOS N.1.23A14).

- **OEM driver** — `UWACPIDriver.sys` (device `\\.\ACPIDriver`), the manufacturer's signed driver; calls the firmware
  methods `ECRR`, `ECRW`, `SMRW`, `PWUP` directly.
- **WMI** — the Windows built-in driver `wmiacpi.sys` (`ACPI\PNP0C14`), class `root\WMI\AcpiTest_MULong`, method
  `GetSetULong`. The firmware runs it through `WMBC → OEMG → RKBC/WKBC`, the old "keyboard controller" protocol with
  `Sleep(50)` / `Sleep(10)` waits.

## Features

| What | OEM driver | WMI | Verified |
|---|---|---|---|
| Read any EC register | ✅ | ✅ | 78 registers + 96 fan-table bytes — all equal |
| Write to the EC | ✅ | ✅ | Fn Lock, USB in sleep, touchpad LED, charge limits, PL1, TCC, Fan Boost — 8/8 |
| Office / Gaming / Turbo / Custom modes, Fan Boost | ✅ | ✅ | `0x751`, `0x726` |
| PL1 / PL2 / PL4, TCC | ✅ | ✅ | match the profile, writes work |
| cTGP, Dynamic Boost (EC registers) | ✅ | ✅ | `0x743–0x746` |
| Factory PL of the modes | ✅ | ✅ | `0x730–0x737`, `0x7A7–0x7AA` |
| Fan table | ✅ ~1 s | ✅ but ~14 s for 96 bytes | rewritten with the same values, table unchanged |
| Battery limits and protection mode | ✅ | ✅ | `0x7B9`, `0x7D0`, `0x7A6` |
| Fn Lock, Win lock, USB in sleep, touchpad | ✅ | ✅ | |
| Fan speed, duty, EC sensors | ✅ | ✅ (slow) | |
| EC targets for the cooler, EC liquid fan table | ✅ | ✅ | handshake `0xF5D–0xF5F` is an ordinary EC write |
| Hotkey events (`AcpiTest_EventULong`) | ✅ | ✅ | WMI event, no driver needed |
| **Smart APC table (`SMRW`)**: PL/TCC/TGP/DB limits for the sliders | ✅ | ❌ | `OEMG` does not call it |
| **Liquid-cooling power level (`PWUP`)** | ✅ | ❌ | the EC restores `0x7C7` at once; limit and clock unchanged |
| Keyboard and light bar lighting (HID) | — | — | not through the EC, no driver needed |
| UEFI variables (BIOS Fn Lock, MUX, RAM overclocking) | — | — | not through the EC, no driver needed |

## Speed

| | OEM driver | WMI |
|---|---|---|
| One read | ~10 ms (10 ms delay, as in the original) | **~124 ms** |
| One write | ~10 ms | **~147 ms** |
| Poll of 14 registers (the service, every 2 s) | ~0.15 s | ~1.7 s |
| Fan table write (96 bytes) | ~1 s | ~14 s |

The WMI delay is built into the firmware (wait loops with `Sleep(50)` inside `RKBC/WKBC`) and cannot be reduced.

## What you lose without the OEM driver

| Situation | Loss without the driver |
|---|---|
| No liquid cooler | nothing significant in the measurements; slower polling and table writes |
| Liquid cooler connected | no `PWUP`: GPU limit 150 W instead of 175 W, clock ~1860 instead of ~2120 MHz (**−13…15 %**) in Turbo + Super performance |
| PL / TCC / DB sliders | without `SMRW` the limits come from the factory PL in the EC (`pl1_max` = Turbo PL1) and defaults (TCC, DB 25 W) |

`PWUP` measurement (Turbo + Super performance + FanBoost + Dynamic Boost, full GPU load):

| Phase | Limit | Clock |
|---|---|---|
| Office, EC level 4 | 150 W | 2002 MHz |
| `PWUP(0)` via the driver | 150 W | 1859 MHz |
| "level 5" via WMI after `PWUP(0)` | 150 W | 1868 MHz — no effect |
| `PWUP(0)` via the driver again | 150 W | 1855 MHz |
| `PWUP(4)` via the driver | 175 W | 2114–2144 MHz |
| `PWUP(5)` via the driver | 175 W | 2101–2193 MHz |

## WMI call format

```
class     root\WMI\AcpiTest_MULong, instance ACPI\PNP0C14\1_1 (10 instances, any works)
method    GetSetULong(UInt64 Data) -> UInt32 Return
read      Data = (1 << 40) | address         byte = Return & 0xFF
write     Data = (value << 16) | address
other     Data = 0x3_0000_0000_0x — iGPU-only commands (echoed on the Tsunami)
rights    administrator (otherwise WBEM_E_ACCESS_DENIED 0x80041003)
```

## Conclusion for open-uniwill-cc

1. The OEM driver is the main path: fast, and the only way to `SMRW` and `PWUP`.
2. WMI is a fallback without proprietary files: all control works, slower; no extra GPU power with the liquid cooler and
   default limits instead of `SMRW`.
3. The service picks the path automatically and shows in the window which one is used and what it lacks.
