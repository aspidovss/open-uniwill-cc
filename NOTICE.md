# Notice and credits

**open-uniwill-cc** is an independent, unofficial project. It is not affiliated with, endorsed or supported by
Uniwill Technology Inc., Tongfang, MAIBENBEN, XMG/Schenker or any other laptop or cooler manufacturer.
"Control Center", "Uniwill", "XMG", "Oasis" and other names are trademarks of their respective owners and are used
here only to describe what the software works with.

## Licenses in this repository

| Path | License |
|---|---|
| everything not listed below | [MIT](LICENSE), Copyright (c) 2026 Sergei Aspidov |
| [`kernel/`](kernel/) (Linux kernel module `uwcc`) | [GPL-2.0](kernel/LICENSE) — required for Linux kernel modules |
| [`proprietary/`](proprietary/) (OEM ACPI driver, factory fan tables) | [proprietary, all rights reserved by their owners](proprietary/LICENSE) |
| [`uwccd/lighting/oem/`](uwccd/lighting/oem/) (LED colour correction, software keyboard effects) | [proprietary, all rights reserved by their owners](uwccd/lighting/oem/LICENSE) |
| [`uwccd/lighting/fx.py`](uwccd/lighting/fx.py) (BetterRGB keyboard effects) | MIT — derived from BetterRGB ITE8291 Adaptive / Better RGB, Copyright (c) 2026 TheYamo, Copyright (c) 2026 ZavierChen and BetterRGB Adaptive contributors ([notice](THIRD_PARTY_LICENSES.txt)) |

Third-party libraries bundled with the Windows build: [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

## Original software (interoperability)

| Software | License | Relationship |
|---|---|---|
| Uniwill / OEM **Control Center 5.52.49.6 (MBB)** — `GCUService.exe`, `UWACPIDriver.sys`, `UEFI_Firmware.dll`, UWP UI | proprietary | The hardware protocol (EC registers, ACPI methods, WMI events, UEFI variable layout) was analysed for interoperability and re-implemented ([docs/PROTOCOL.md](docs/PROTOCOL.md)). OEM files and OEM-derived code are kept apart in `proprietary/` and `uwccd/lighting/oem/`. |
| **ControlCenterX V5.0.0** | proprietary | Feature ideas only (Custom mode editor, automation). No code or files used. |
| Clevo **Control Center 3.x** and its driver library `InsydeDCHU.dll` | proprietary | The driver interface (device interface GUID, IOCTL, request layout) was analysed for interoperability and re-implemented in `uwccd/clevo/`. No vendor code or files are used or shipped. |

## Projects that helped

| Project | License | What we took |
|---|---|---|
| [tomups/watercooler-manager](https://github.com/tomups/watercooler-manager) | GPL-3.0 | The Bluetooth protocol of the XMG Oasis / LCT21001 / LCT22002 liquid coolers was cross-checked against it. **No code was copied** — `uwccd/watercooler.py` is an independent implementation, so it stays MIT. |
| [anvme/watercooler-xmg-neo-linux](https://github.com/anvme/watercooler-xmg-neo-linux) | not specified | Ideas: a laptop-following cooler mode, pump voltage tiers. No code copied. |
| [TUXEDO Computers tuxedo-drivers](https://github.com/tuxedocomputers/tuxedo-drivers) (`clevo_acpi`, `clevo_wmi`) | GPL-2.0 | The Clevo DCHU interface (`_DSM` UUID, WMI GUID, command numbers) was cross-checked against it. No code copied; `kernel/uwcc.c` is GPL-2.0 anyway. |
| [omerboran63/CustomClevoController](https://github.com/omerboran63/CustomClevoController) | not specified | Looked at as a list of Control Center 3 features. Nothing taken (no licence; it contains decompiled vendor code). |
| [faintonce/open-revo](https://github.com/faintonce/open-revo) | MIT | Ideas: custom performance mode, monitoring history, automation rules. No code copied. |
| [ZavierChen/BetterRGB-ITE8291-Adaptive](https://github.com/ZavierChen/BetterRGB-ITE8291-Adaptive) (from [EpicYamo/Better-RGB-for-Tongfang-ITE8291](https://github.com/EpicYamo/Better-RGB-for-Tongfang-ITE8291)) | MIT | The BetterRGB keyboard effects, transitions, white calibration, top-row bar and frame pacing — rewritten in Python in `uwccd/lighting/fx.py`. Copyright (c) 2026 TheYamo, (c) 2026 ZavierChen and contributors; their MIT notice is kept in [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt). |

Thank you to all of them.

## Reverse-engineering note

The analysis was done on legally obtained software, only to the extent needed to make open-uniwill-cc work with the
hardware (see e.g. Art. 6 of Directive 2009/24/EC).
The analysis tools in [`tools/re/`](tools/re/) are our own (MIT) and contain no OEM code.
