# Changelog

## 1.6.3

- **BetterRGB keyboard effects** — 16 effects drawn by the service frame by frame, rewritten in Python from
  [BetterRGB ITE8291 Adaptive](https://github.com/ZavierChen/BetterRGB-ITE8291-Adaptive) (MIT, ZavierChen; based on
  Better RGB by TheYamo): Breathing, Wave, Sparkle, Reactive, Colour wheel, Lightning, Flame, Rain, Matrix (four
  styles), Static zones, Reactive ripple, Rainbow, Quicksand, Current, Reactive current and Screen ambient. Each has
  its own parameters (speed, density, width, colours …) in the window (*Keyboard backlight → BetterRGB*) and on the
  command line (`uwccctl kb fx`).
  - Per-key keyboards get the user-mode picture (`08h`, `12h`, 8 rows of 65 bytes — the packets BetterRGB sends);
    four-zone keyboards (MAIBENBEN Tsunami) get the average colour of each zone.
  - **Engine:** frame rate on AC and on battery (10–60, lowered automatically while the keyboard does not keep up),
    transitions (fade, ripples, wipes, twin spirals) when an effect starts and when the backlight goes dark after
    inactivity and comes back, **white calibration** (raw white on the keys → pick the colour you see → per-channel
    gains), **top-row bar** (battery, volume, microphone, CPU, GPU, playback level; a volume change shows the volume
    for 1.8 s).
  - **Input from the user session** only while an effect needs it, nothing stored: key presses (Linux: the service
    reads `/dev/input`; Windows: the tray program), a 64 × 24 picture of the screen (Windows: the tray program;
    Linux: the session agent, X11 only), volume and audio levels (Windows: Core Audio; Linux: volume through `pactl`).
  - API `POST /api/keyboard/fx/config | fx/calibrate | fx/input`, the effect body gets `"fx": {...}`.
  - Help page *BetterRGB keyboard effects* (`docs/LIGHTING.md`); the MIT notice of BetterRGB is in
    `THIRD_PARTY_LICENSES.txt`, credits in `NOTICE.md`. The Linux installer now copies `LICENSE`, `NOTICE.md` and
    `THIRD_PARTY_LICENSES.txt` too.
- **Fix — built-in help, tables:** a table whose separator row has centred columns with one dash (`|---|:-:|:-:|---|`,
  e.g. *What was ported* in `docs/FEATURES.md`) was shown as plain text with `|`. The viewer now accepts one dash like
  GitHub, aligns the columns as the separator row says, and keeps `|` inside `code` and `\|` in a cell.
- README: supported Control Center versions (5.52.x supported, 5.56.x with service 1.2 untested, 3.x not supported)
  and the theoretical list of platforms with their support level.

## 1.6.2

- **Built-in help** (*Help* in the side bar): the documentation inside the program, offline, in English and Russian —
  EC Manager and platform profiles, getting the OEM driver, OEM driver vs WMI, the WMI settings, the EC registers, the
  EC test tool, the features and the command line. **?** next to the EC Manager cards opens the matching section.
- **OEM driver for the free build** — three ways in EC Manager: *Get the driver from this system* (copies it from the
  Windows driver store when the manufacturer's Control Center is or was installed; `uwccctl ec fetch-driver`),
  *Driver in the repository* (link to `proprietary/driver`) and *How to get the driver* (help page
  `docs/EC/OEM-driver.md`, also with the manual PowerShell / innoextract commands as one-liners).
- **Check of the driver before it is installed** — in EC Manager, the installer, `install.ps1` and the self-check:
  the three files and their sizes, the INF is the `UWACPIDriver` for `ACPI\INOU0000` (amd64), the signatures of the
  catalog and the driver, SHA-256 against the known version (17.53.43.609). An unknown version or a signature problem
  needs *I still want to use this driver and understand the risk* (`--accept-risks`); a package for another device or
  with missing files is never installed. `uwccctl ec check-driver`, `uwccctl driver-verify DIR` (works without the
  service; exit codes 0 / 10 / 11 / 12).
- **Monitoring card** in EC Manager is compact: one drop-down (full / off with the OEM driver / off with WMI / off with
  both / all off), the **sampling interval** (automatic or 1–60 s), and the **history**: size on disk, **maximum size**
  (the oldest minutes are dropped beyond it; the file is written compactly now), **folder** (administrator) and
  **Clear the history**.
- **Self-check stage 2 backs up every value it writes first** — 106 EC values (the switched registers, the fan-table
  handshake and the fan table): to the crash snapshot and a dated copy `selfcheck-backups/ec-backup-*.json` (the last
  ten are kept), both read back before anything is written; no backup — no test writes. The window shows *EC backup
  saved* with the file while the check runs, and at the end how many values read back equal after the restore.
- EC Manager: the self-check buttons go left to right in the order of use; *Stage 2* is available only after a
  stage 1 since the service started (also enforced by the service); every card folds by a click on its title (remembered).
- New screenshots (English and Russian), including EC Manager and the help.

## 1.6.1

- **Mode switches on the WMI path no longer look frozen.** The window covers itself with *Applying…* until the
  mode is set; the mode, power limits and Fan Boost are written first (about 1–2 s), the fan curve follows in the
  background (*Fan curve: writing N %* in the side bar; the mode cards and the fan page wait for it). A curve that is
  already in the EC is not written again (also at start-up). A second click while a mode is applied is refused
  (`409 busy`) instead of queueing.
- **Driver Manager is now EC Manager** (`uwccctl ec …`, `uwccctl driver …` still works). The OEM driver path is marked
  as the recommended one.
- **Administrator rights for EC settings.** Changing the EC access path, accepting the WMI warning, `ec_wmi.json`,
  platform profiles and the self-check with writes need administrator rights: the window asks for them through the
  tray (UAC prompt, then 10 minutes unlocked); `uwccctl ec unlock` as administrator / `sudo`. Before, every local user
  could change them.
- **Hard caps**: no profile or `ec_wmi.json` can set PL1 > 200, PL2 > 250, PL4 > 300 W, base TGP > 200, cTGP or Dynamic
  Boost > 50 W; on a verified platform the limits cannot exceed the factory values.
- **Platform profiles** (`uwccd/platforms/*.json`): identity, tested versions, the WMI call layout, which functions work
  through WMI, limits and notes as data. Built in: MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super / XMG NEO 16
  (E23) — verified — and a generic profile in which every function stays off on the WMI path for unknown laptops.
  Export / import / back to the built-in profile in EC Manager.
- **Self-check** in EC Manager / `uwccctl ec selfcheck`: stage 1 reads only (identity, both access paths compared byte
  by byte, plausibility of known registers, time per access, firmware methods); stage 2 (administrator, AC power)
  switches each function a little and back with read-back — Fn Lock, touchpad flag, mode byte, Fan Boost (do the fans
  react?), PL1, cTGP, charge limit, fan-table handshake — and restores the registers, also after a crash. Result: what
  works, what is not clear, a draft platform profile; *Export for GitHub* and *Apply as platform profile*.
- **Monitoring switches** in EC Manager: off for the OEM driver, off for WMI (temperatures for the liquid cooler and
  alerts only, every 20 s) or all off (nothing is read; the liquid cooler in the automatic mode runs the Medium preset).
- **Restart of the service** (EC path changed, *Restart the service*): the window shows *The service is restarting*
  and reloads by itself when it is back. The service restarts itself cleanly through the service manager instead of
  exiting with an error, so repeated restarts no longer wait for the growing recovery delays.
- WMI notes: the extra graphics power is reached only in the stock Turbo mode (150 W Office / Gaming, 175 W Turbo on the
  Tsunami); Dynamic Boost in the Custom mode adds power only while the processor leaves room.
- Fixed: on the WMI path every liquid-cooler event `0xC2` logged *PWUP is not available through WMI*.
- **Two Windows builds**: non-free `open-uniwill-cc-windows-<ver>-setup.exe` (OEM driver + WMI) and **free**
  `open-uniwill-cc-windows-<ver>-free-setup.exe` (WMI only). The free build does not contain the original OEM driver or
  any other proprietary file and is distributed completely freely; the installer, EC Manager and `install.ps1` say so
  and recommend putting the OEM driver (`UWACPIDriver.inf`, `.sys`, `.cat`) into `C:\ProgramData\UWCC\driver` — it is
  installed from there by the installer or *EC Manager → Install the OEM driver* (`uwccctl ec install-driver`). Each
  build updates itself to its own edition. `build_windows.ps1 -Edition both|full|free`.
- Documentation: `docs/EC/Platforms.md` (English / Russian).

## 1.6.0

- **Open EC access through WMI (Windows, beta).** Besides the manufacturer's driver `UWACPIDriver.sys` the service can
  reach the embedded controller through the WMI interface built into Windows (`root\WMI AcpiTest_MULong`), without
  proprietary files. Three choices — in the installer, in the window and with `uwccctl driver use`:
  - **OEM driver + WMI** (default, recommended): the OEM driver; WMI only when the driver is missing and the warning was
    accepted;
  - **OEM driver only**;
  - **WMI only** — open implementation, not recommended, beta; the installer then does not copy the OEM driver.
- On the WMI path every EC access takes ~125 ms (wait loops in the firmware), so reads are cached, unchanged writes are
  skipped and sensors are sampled every 5 s. Not reachable through WMI: the liquid-cooling power level `PWUP` (the
  *Power boost with liquid cooling* option is greyed out; tests: ~13–15 % lower GPU clock under load without it) and the
  Smart APC limit table `SMRW` (limits come from the WMI settings; values for project 0x10 are built in).
- When the OEM driver is missing the service starts without EC access and the window recommends the OEM driver or
  offers WMI after a warning: why some functions need the driver, what the open implementation is, the risks, a link
  to the documentation and, in red, that it is not recommended on platforms other than MAIBENBEN Tsunami X629 /
  Mechrevo Questyle 16 Super / XMG NEO 16 (E23).
- New **Driver Manager** page: the active path and the OEM driver version, the three choices, the WMI settings
  (`ec_wmi.json`: which functions stay available or are marked slow, polling, timeout, limits, registers) with import,
  export and factory reset, and a test of the EC path. Functions that do not work on the WMI path are greyed out.
  **WMI DRIVER ON** in the side bar while the WMI path is active; an *EC access* block on the Information page.
- `uwccctl driver [use auto|oem|wmi] [--accept-risks]`, `uwccctl driver config export|import|reset`, `uwccctl driver test`.
- Documentation: `docs/EC` — EC registers of the Tsunami X629, OEM driver vs WMI, the WMI settings, `ec_tool.py`
  (English and Russian).

## 1.5.5

- *Fan settings*: the profile tabs fit in one line — the mode name once, then its slots as numbers (the full
  name is in the tooltip, a dot marks the active table).
- **Fan manager switch** in *Settings → Switches* (automatic by project / commercial `_CML` / RamFan 1.5 with the
  Custom mode) and `uwccctl set fan_manager auto|cml|std`; the service restarts by itself. Before, it could only be
  forced by editing `settings.json`.
- **Full control from the command line.** `uwccctl` now changes everything the window does:
  - `profile list|show|set|reset` — PL1/PL2/PL4, TCC offset, cTGP, Dynamic Boost, GPU temperature limit, fan switch
    speed and the name of any profile (`custom:2`, `office`, `Mode4_Profile3`);
  - `fan list|show|set|separate|reset` — fan curves as `UP/DOWN:DUTY` points or from a JSON file;
  - `battery mode|limit|typec`; `super`, `ramoc`; `restore --yes`;
  - `kb effects` and `kb effect NAME [--light --speed --dir --color --multi --text]`, `kb level`;
  - `get` / `set KEY VALUE` for every switch and automation setting; `apps add|remove|enable|disable`;
  - `lc tiers`, `lc set` (temperature source, delays, smoothing, flow guard, boosts), `lc idle`;
  - `monitor [--watch SEC]`;
  - `--json` for every command (errors as `{"error": ...}`), exit codes 0 / 1 rejected / 2 usage / 3 no service;
  - `UWCC_TOKEN`, `UWCC_TOKEN_FILE` and `UWCC_PORT` environment variables.
- **Man page** `uwccctl(1)` in English and Russian (`man uwccctl`, `man -L ru uwccctl`) and **bash completion**,
  installed by `install.sh`; `uwccctl help COMMAND` on both systems; reference in `docs/CLI.md` / `docs/CLI.ru.md`.

## 1.5.4

- **Keyboard type detection fixed** (checked against the IL of `ILM_RGBKB_Init`): an ITE keyboard with usage page
  `FF12` is a **four-zone** keyboard (type 2, type 3 on project 0x11) and `FF02` is type 4 — the two were swapped.
  MAIBENBEN Tsunami (ITE CE00, firmware 11.5) is such a four-zone keyboard. Consequences:
  - single colour goes to every zone (all palette slots, colour argument 8) — before only the first zone (the left
    third) changed;
  - colour correction for four-zone keyboards (`cheatRGB_4Zone`) is used;
  - the firmware effects of the original window for this keyboard type (CCU.WinUI 5.56, `FourZone`): Single,
    Breathing, Wave, Rainbow (a still rainbow, as on every ITE firmware), Flash, Mix — exactly the ones that work on
    MAIBENBEN Tsunami; the others are greyed out;
  - drawn by the service zone by zone (palette slots 1–4 + firmware static effect), with smooth transitions:
    Neon, Stack and Impact (the frames of the original averaged per zone and blended), Colour wave, Wave and Flash
    (fading flashes instead of the hard on/off of the firmware);
  - Wave starts with all palette colours (*Multicolour*) by default, and on these keyboards it is drawn by the
    service as a smooth blend of the palette colours flowing across the zones (the firmware Wave jumped between
    colours);
  - between two effects the backlight is switched off completely (reset + off), otherwise the firmware kept parts of
    the previous effect.
- Reactive, Ripple, Aurora and Spark on per-key keyboards: the EC is told to pass key presses to the keyboard
  (`0x741` bit 3, `Enable_EC_OnkeyPressed`).
- A repeated identical effect request within 0.6 s (double click) is dropped, and effect changes are kept 150 ms apart.
- *Debug logging* switch on the diagnostic report card (it is also in *Settings → Switches*).
- **Monitor:** a *Clocks* tab in the history (CPU and GPU clock, also in the CSV / JSON export and the point details);
  the *Temperature history* card is replaced by a liquid cooler summary (state, mode, pump, fan, coolant flow,
  temperature tier) with a button to its page.
- Windows: the CPU clock is the current one ("Processor Frequency" × "% Processor Performance", as Task Manager shows
  it) — it stayed at the nominal clock (e.g. 2300 MHz) before.

## 1.5.3

- **Performance boost** card (*Mode selection*), independent of the mode — both switches stay on when you change
  modes:
  - **Super performance** (`LoadOverClockingValue` of the original, there a switch of the Custom slots): the EC runs
    the Turbo fan mode with the factory Turbo fan curve and the graphics card gets the maximum power (cTGP + Dynamic
    Boost); the power limits of the current mode stay. GPU clock offsets and the CPU voltage offset of the original are
    not applied.
  - **RAM overclocking**, when the BIOS reports support (`MemoryOverClockSupport` in the UEFI variable
    `UniWillVariable`): the switch is written to `MemoryOverClockSwitch` and the BIOS applies it at the next start (the
    window says *Restart to apply*). Uninstalling switches it off (as the original does).
- The liquid-cooling option of 1.5.0 is now called *Power boost with liquid cooling* (original: CoolingOC), so the two
  are not confused.
- Fixed: switching Dynamic Boost on or off in a profile did not redraw the cTGP range until the page was reloaded.

## 1.5.2

- **User agreement** (English / Russian, `uwccd/web/eula.*.txt`): the Windows installer shows it on a licence page, the
  Linux `install.sh` asks to accept it (`--accept-agreement` for unattended installs), and the window shows it at the
  first start until it is accepted (also for the portable build). Main points: MIT, *as is*; the user is responsible
  for using the program; the bundled OEM components (ACPI driver, factory fan tables, lighting code) were added by hand
  to demonstrate compatibility — you confirm you may use them or replace them yourself. A new edition of the agreement
  asks again.

## 1.5.1

- **Restart the service by hand** when it has not answered for a minute: the tray menu gets *Restart service*
  (Windows asks for administrator rights; a hung process is ended after 15 s), the window shows a banner with
  instructions and *Settings → About* has a *Restart service* button; on Linux the agent offers a notification with a
  *Restart* action (polkit rule for the `uwcc` group, installed by `install.sh`). New command: `uwccctl restart`.
- **Platforms of the newer official service (GCUService 1.2)**, e.g. MECHREVO Kuangshi / Jiguang …B2 (project 0x1A):
  recognised and run with the same RamFan 1.5 control, marked *experimental*. The code of service 1.2 is protected, so
  nothing laptop-specific could be taken over from it — reports from owners decide what to add.
- The Info page shows the support level (*tested* / *known platform* / *experimental*) and the model name for projects
  missing from the original tables (0x10 MAIBENBEN Tsunami — tested); untested laptops get a request for a report.

## 1.5.0

- **Super performance with liquid cooling** (*Liquid cooling → Options*, off by default; laptops whose EC supports
  liquid-cooling fan tables, 0x7C8 bit5): while the cooler runs with normal coolant flow, the EC loads its own
  liquid-cooling fan table for the mode (Office / Gaming / Turbo / Custom) and the program passes the EC's OC power level
  to the firmware method `INOU.PWUP` (also on WMI event 0xC2), as `LiquidHWOC` of the original service does. User fan
  curves are kept but not written meanwhile; everything returns when the cooler disconnects or the flow fails.
  The original's GPU clock offsets in Turbo are not applied.
- Linux kernel module 1.5.0: ioctl for `PWUP` (DKMS version bump; older module versions are removed on install).

## 1.4.3

- **Diagnostic report, more for new laptops:** ACPI tables (DSDT, SSDT… — without MSDM / SLIC, which hold the Windows
  licence); the EC interface devices (ACPI INOU0000 / UNIW / PNP0C14, WMI) and their drivers; on Windows the whole
  `HKLM\SOFTWARE\OEM` registry of the original Control Center with its feature flags decoded (ItemSupport, Support,
  MySetting, SMAPCTable) and its brand (`CustomizeTarget`); its services, packages, scheduled tasks and file versions /
  signatures; its settings files, fan tables, profiles and logs of the last 14 days (text only, redacted) with a list of
  all files; power plans. *Original Control Center folders complete* (programs included, large) is a separate option,
  off by default (`uwccctl report --full`). The summary notes boards known to run the same official service.
- The report is collected in the background with a progress line (up to a minute or two on Windows), then downloaded
  with a button — a second report works too (the window blocked automatic downloads after the first one).

## 1.4.2

- **Updates (Windows):** the tray app downloads the installer to your **Downloads** folder, checks it against
  `SHA256SUMS.txt` and starts it (Windows asks for administrator rights). If the prompt is declined the installer stays
  in Downloads and Explorer shows it. Fixes *Permission denied* of 1.4.1 (the service downloaded into a folder the tray
  could not read). Without the tray app the button opens the release page.
- **Build date and commit** next to the version: *Information → About*, the service log, `uwccctl version`
  (`1.4.2 · build 2026-10-23 · a1b2c3d`).
- **Diagnostic report** (*Information → Diagnostic report*, `uwccctl report`): a zip with the system and BIOS versions,
  platform, EC registers the program uses (read only), UniWillVariable and SmartAPC, keyboard / light bar HID devices
  with report descriptors, NVIDIA limits, sensors, original Control Center files, liquid cooler, log and settings.
  Serial numbers, UUID, MAC addresses, computer / user names and program lists are left out unless ticked.
  Buttons to open a GitHub issue or an e-mail to **OUCC@aspidov.ru** with a prefilled summary.
- Contact e-mail in README, SECURITY.md, *About* and the installer.

## 1.4.1

- **Liquid cooler, calm control** (Automatic and Controller modes): the temperature is averaged over 10 s; a faster
  tier is taken after the temperature holds for 10 s, a slower one after 30 s (both adjustable, 0–300 s); at 95 °C or
  8 °C above the tier's threshold at once. The fan changes by 10 % and the pump by one voltage step per 3 s.
  The same delays apply to the targets the EC publishes in the Controller mode. On by default.
- **Stop the pump when it is cool** (off by default): below 50 °C for 60 s the pump stops, above 55 °C for 10 s it
  starts again, at least 2 minutes of running after each start — all adjustable. Tiers may also use *Off* for the pump.
- Cooler temperature source: the hotter of CPU and GPU, CPU only, or GPU only (the CPU is used while the GPU sleeps).

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
