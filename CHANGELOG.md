# Changelog

## 1.4.0

- **CPU temperature limit** in each mode / profile, set in °C (the original's *CPU limit*; stored as the TCC offset
  Tjmax − limit, EC 0x786). Default range down to 85 °C; *Settings → Switches → Extended CPU temperature limit range*
  allows down to 60 °C, as the original Control Center did.
- **GPU temperature limit** (NVIDIA target temperature) per profile: Windows through NVAPI client thermal policies,
  Linux through `nvidia-smi -gtt`. Range comes from the driver; *off* returns the driver default.
- **Export / import**: fan curves (this table or all) with a preview in the editor; full backup of profiles, curves and
  all settings (lighting, battery, automation, cooler…); import from the original Control Center's `UserFanTables` /
  `UserPofiles`. Files from another project are refused unless confirmed. `uwccctl export` / `uwccctl import`.
- **Dynamic Boost** hint: when `nvidia-powerd` (Linux) or *NVIDIA Platform Controllers and Framework* (Windows) is
  missing or stopped, the profile editor says so; on Linux it can start the service.
- Per-key (UserMode) and gaming lighting modes are hidden on ITE keyboard firmware 0x11, which ignores them;
  a switch brings them back.
- **About** card on the Information page: version, repository, license, issues link.
- **Update check** against the GitHub releases, once a day (on by default, *Settings → Switches* to turn off; only
  the public releases API is requested). Windows: *Download and install* in the window or the tray downloads
  the setup, checks it against `SHA256SUMS.txt` and starts it. Linux: link and install commands. `uwccctl update`.
- Linux window: external links open in the default browser.
- **History** on the Monitor page: periods 1 min / 5 min / 15 min / 1 hour / 24 hours (2 s samples for up to
  15 min, 5 s for the hour, per-minute averages with peaks for 24 h, kept on disk across restarts). Hover shows the
  values at that moment; a click pins the point (the chart stops) and lists all sensors of that moment; Esc resumes.
  *Record sensor history* switch; export as a compact menu; `uwccctl history … 24h`.
- Buttons show their result in place (*Working…* → *✓ Profile applied*, or the error next to the button until a value
  changes); the other notifications appear at the top right instead of the bottom.
- Profile editor: Apply works again; PL2 follows PL1 (and PL4 follows PL2) and cannot be set below it.
- The EC *Light bar* switch is hidden when the light bar device is controlled on its own page.

## 1.3.2

- **Chassis light bar** (ITE 048D:7000, HIDLightbar4): zones rear/hinge, base, logo as the device reports them;
  static colour, breathing, wave, colour cycle, rainbow, colour breathing / wave; brightness, speed, on/off per zone.
  Own menu item *Lighting → Laptop light bar*, `uwccctl lb`.
- Keyboard *Single colour* now works on ITE firmware 0x11 (it ignores the 12h picture GCUService sends there).
- Monitor → Last hour: separate **CPU power** and **GPU power** charts with now / average / max; CPU package power on
  Windows from the Energy Meter counters (Linux: RAPL). Dashed marks for the current limits: PL1 / PL2 (PL4 on Custom-mode
  platforms) and the NVIDIA power limit.
- **Total power** chart: CPU + GPU, power drawn from the battery when unplugged, the adapter rating as a mark.
- **Export** of the last hour: CSV, CSV for Excel (`;` and decimal comma), JSON, PNG of the chart;
  `uwccctl history [csv|csv-excel|json] [FILE]`. The Linux window saves downloads to ~/Downloads.
- Lighting diagnostics: `uwccctl lighting` (all ITE HID devices, keyboard type, firmware); HID traffic in the debug log.
- Fan curves: two levels may start at the same temperature — factory tables do that (e.g. 55/55 °C on project
  0x10), which made saving fail with "level temperatures must increase". Decreasing temperatures are still refused.
- Fan curves: levels after the first unused one are ignored; ECs that pad unused levels with zeros are handled.
- Fan curve editor: dragging points works on Windows (no text selection; the drag no longer stops after the first move).

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
