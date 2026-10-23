# Changelog

## 1.3.2

- Fan curves: levels after the first unused one are ignored; ECs that pad unused levels with zeros no longer
  cause "level temperatures must increase" when saving a table (seen on project 0x10).

## 1.3.1 — 2026-10-23 — first public release

- Windows: fixed monitoring with `--mock`, "Operating system" and "WMI" on the Information page,
  SSD/HDD detection (MSFT_PhysicalDisk), console messages of `uwccctl.exe`.
- Debug logging switch (Settings → Switches, `uwccctl debug on|off`, `UWCC_DEBUG=1`).
- OEM files and OEM-derived code moved to `proprietary/` and `uwccd/lighting/oem/` with their own license;
  the program works without them. `build_windows.ps1 -Public` builds a package without them.
- Project renamed to **open-uniwill-cc**; README in English and Russian, NOTICE, BUILD guide.

## 1.3.0

- Windows version: `uwccd` service (UWACPIDriver, WMI hot keys), tray application hidden in the tray and started
  with Windows, `uwccctl.exe`; `build_windows.ps1`, Inno Setup installer, portable `install.ps1`.

## 1.2.0

- Custom mode with 5 slots, PL4, TCC offset and Smart APC limits on RamFan1p5 platforms.
- Automation: mode per power source, overheating alerts, power-profiles-daemon sync. One-hour history chart.
- Liquid cooler: follow-the-laptop mode, flow guard; webcam switch; discrete GPU card.

## 1.1.0

- XMG Oasis liquid cooler over Bluetooth; English / Russian interface (English by default).

## 1.0.0

- Linux port of Control Center 5.52.49.6: modes, profiles, fan curves, power limits, keyboard lighting,
  battery, switches, monitoring, app binding.
