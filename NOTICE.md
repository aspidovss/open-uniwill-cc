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

Third-party libraries bundled with the Windows build: [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

## Original software (interoperability)

| Software | License | Relationship |
|---|---|---|
| Uniwill / OEM **Control Center 5.52.49.6 (MBB)** — `GCUService.exe`, `UWACPIDriver.sys`, `UEFI_Firmware.dll`, UWP UI | proprietary | The hardware protocol (EC registers, ACPI methods, WMI events, UEFI variable layout) was analysed for interoperability and re-implemented ([docs/PROTOCOL.md](docs/PROTOCOL.md)). OEM files and OEM-derived code are kept apart in `proprietary/` and `uwccd/lighting/oem/`. |
| **ControlCenterX V5.0.0** | proprietary | Feature ideas only (Custom mode editor, automation). No code or files used. |

## Projects that helped

| Project | License | What we took |
|---|---|---|
| [tomups/watercooler-manager](https://github.com/tomups/watercooler-manager) | GPL-3.0 | The Bluetooth protocol of the XMG Oasis / LCT21001 / LCT22002 liquid coolers was cross-checked against it. **No code was copied** — `uwccd/watercooler.py` is an independent implementation, so it stays MIT. |
| [anvme/watercooler-xmg-neo-linux](https://github.com/anvme/watercooler-xmg-neo-linux) | not specified | Ideas: a laptop-following cooler mode, pump voltage tiers. No code copied. |
| [faintonce/open-revo](https://github.com/faintonce/open-revo) | MIT | Ideas: custom performance mode, monitoring history, automation rules. No code copied. |

Thank you to all of them.

## Reverse-engineering note

The analysis was done on legally obtained software, only to the extent needed to make open-uniwill-cc work with the
hardware (see e.g. Art. 6 of Directive 2009/24/EC and Art. 1280 of the Civil Code of the Russian Federation).
The analysis tools in [`tools/re/`](tools/re/) are our own (MIT) and contain no OEM code.
