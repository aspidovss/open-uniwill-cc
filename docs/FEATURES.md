# Features

**English** · details of what open-uniwill-cc does and how (EC registers, ACPI methods, WMI events).
Windows differences: [README.windows.md](../README.windows.md#differences-from-linux). Protocol: [PROTOCOL.md](PROTOCOL.md) (Russian).

## EC access without third-party drivers

The key difference from the original Control Center: on **Windows** the free build reaches the EC through the firmware's
own WMI method (`root\WMI AcpiTest_MULong.GetSetULong` → DSDT `WMBC` → `RKBC` / `WKBC`) and the WMI driver built into
Windows — no OEM driver and no other third-party driver; on **Linux** through the open kernel module `uwcc`. The OEM
driver stays an option for speed and for `PWUP` / `SMRW`. Comparison and measurements:
[EC/WMI-vs-Driver.md](EC/WMI-vs-Driver.md); EC Manager, platform profiles and the self-check:
[EC/Platforms.md](EC/Platforms.md).

## Modes: two kinds of platforms

The original service has two different mode managers and picks one by the project ID from the EC; this port does the same:

> **RamFan 1.5** is not a separate project: it is the name the original Uniwill service (GCUService,
> `MyFanManager_RamFan1p5`) gives to the fan control of the EC firmware. The fan curve (16 levels "temperature → speed"
> for CPU and GPU) lives in the EC RAM at `0xF00–0xF5C` and is handed over with `0xF5D–0xF5F`; with it come the Custom
> mode, PL1 / PL2 / PL4 / TCC and the Smart APC limit table. The EC reports it in `0x78E` bit 6 (*Information →
> RamFan 1.5*). Without it the program does not control the fans. ("RAM fan table, version 1.5" is our reading of the
> name; there is no public description.)

| | Commercial projects (PH4/PH6 list, `_CML` manager) | All other projects (RamFan1p5 manager) |
|---|---|---|
| Modes | Office, Gaming, Turbo | Office, Gaming, Turbo, **Custom** |
| Profiles | 3 per Office/Gaming | 2 per Office/Gaming/Turbo, **5 Custom slots** with your own names |
| Per profile | PL1/PL2 (AC and battery), cTGP, Dynamic Boost, fan curve | **PL1/PL2/PL4, TCC offset**, cTGP, Dynamic Boost, fan curve |
| Limits | from the factory fan tables | from the firmware **Smart APC table** (ACPI `SMRW`) |

In Custom mode the Fn mode key steps through the five slots. Each slot can be reset to the factory values (its curve too).

**Super performance** (a switch of its own, works in any mode; `LoadOverClockingValue` of the original): fan mode byte
`0x751 = 0x10` (Turbo) with the Custom flag `0x726` bit 7 cleared, the factory `DefaultFanTable_Turbo`, cTGP = maximum +
Dynamic Boost with Dynamic Boost off; the PL limits of the current mode stay. **RAM overclocking** (also its own
switch) when `UniWillVariable.MemoryOverClockSupport = 1`: written to `UniWillVariable.MemoryOverClockSwitch`, which the
BIOS applies at the next boot; set to 0 by `uwccctl release` on uninstall.
`uwccctl status` shows which manager runs (`[cml]` / `[std]`). If the choice is wrong for your laptop, pick the other one in
*Settings → Switches → Fan manager* (or `uwccctl set fan_manager cml|std|auto`); the service restarts by itself.
Not ported from the RamFan1p5 manager: GPU core/memory clock offsets (NVAPI), CPU voltage offset (Intel OC SDK),
WhisperMode.

## Automation (Settings → Automation)

* **Power source:** a mode for "charger plugged in" (keep / the mode before unplugging / a mode) and for "unplugged";
  keyboard backlight off on battery; follow the mode with power-profiles-daemon (Turbo → performance, battery → power saver).
* **Overheating:** a desktop notice when the CPU or GPU stays at the limit (default 95 °C / 87 °C) for 30 s, at most once
  in 10 minutes; optionally Fan Boost is switched on if it is still hot 30 s later.

## Monitoring extras

* **History** on the Monitor page (1 min … 24 h, a point can be pinned for details, a period can be zoomed by dragging
  across the chart, CSV / JSON export): temperatures,
  load, clocks, CPU package power and power limits, GPU power, CPU + GPU and battery power, fans, cooler.
* **What the CPU values mean** (compared with OCCT, HWiNFO …): *power draw* is the RAPL **package** domain (Linux
  powercap `package-0`, Windows Energy Meter `rapl_package0_pkg`); the *clock* is the clock of the busy cores, as
  *Speed* in Task Manager (nominal × `% Processor Performance` on Windows, `scaling_cur_freq` on Linux) — not the
  "effective" clock of OCCT / HWiNFO, which averages in the time the cores sleep and is much lower at light load;
  the *temperature* is the EC sensor, the values are sampled every 2 s.
* **Discrete GPU** card on the Information page: whether the NVIDIA GPU sleeps and which programs keep it awake.
  The monitor no longer calls `nvidia-smi` while the GPU is in runtime suspend (that used to wake it every 2 s and drain the battery).
* **Fan curve presets** (Factory / Quiet = factory × 0.8, the OEM rule for its quiet table / Maximum) — loaded into the editor, saved with *Save*.
* **Webcam** switch (Settings → Switches): the camera is de-authorized on the USB bus, so no program can open it.

## Liquid cooling

Page **Performance → Liquid cooling** (or `uwccctl lc …`). Power the cooler on, press *Search*, then *Connect*.
The address is remembered and the service reconnects by itself, also after sleep. When the service stops and before
the system sleeps the cooler is put to sleep. Needs `python3-bleak` (installed by `install.sh`).

| Feature | How |
|---|---|
| Modes, first row: **Automatic** (curves by CPU/GPU temperature), **Follow the laptop** (curve of the laptop's mode), **Controller** (EC targets), **Manual**; second row: High 90 %/11 V, Medium 50 %/8 V, Low 25 %/7 V, Off | fan `0x1B`, pump `0x1C` |
| **Curves** (1.6.8): a fan curve (2..17 points, linear between them) and pump steps (7 / 8 / 11 V, down only 3 °C below a step), edited by dragging; the current temperature and value are shown as a crosshair. One **common** curve (Automatic, and Follow the laptop for modes without their own); in Follow the laptop each mode — Office, Gaming, Turbo, Custom — can have **its own curve**; a change of the laptop's mode switches the curve at once (the fan still ramps) | |
| **Cooler profiles**: Quiet, Balanced, Performance and your own (Apply / Save / Copy / Remove) — a profile holds the common and the per-mode curves | |
| Lighting: static, breathing, rainbow, breathing rainbow; Mk2 also spiral, rotating rainbow, colour wave | `0x1E` / `0x33` |
| Coolant flow check every 15 s with a desktop alert when the pump runs but nothing circulates | `0x32` |
| Coolant filling cycle (8 pump pulses, ~70 s) | `0x19` |
| Fn cooler boost keys (fan ≥ 60 %, pump ≥ 8 V); EC told that a cooler is attached (`0x7C7` bit 1) on laptops that declare support | WMI `0xCD`/`0xCE` |
| **Flow guard:** with no coolant flow the pump goes to 11 V and the fan to ≥ 60 % until the laptop's mode changes or you pick a setting | |

```bash
uwccctl lc scan                      # find coolers
uwccctl lc connect C0:FF:EE:..:..:.. # connect and remember
uwccctl lc mode auto                 # auto | laptop | ec | manual | high | medium | low | off
uwccctl lc manual 60 8               # fan 60 %, pump 8 V
uwccctl lc curve common fan 40:25 60:45 80:80 95:100 pump 0:8 70:11
uwccctl lc curve turbo flat 90       # Follow the laptop: Turbo at 90 %;  uwccctl lc curve turbo off
uwccctl lc profile apply quiet       # cooler profiles: list | apply | save | copy NAME | remove | rename
uwccctl lc rgb 00ffff breathe        # colour and effect;  uwccctl lc rgb off
uwccctl lc prime                     # filling cycle
```

The built-in curves start at 8 V: on some units the flow does not hold at 7 V and the cooler switches itself off
(the OEM service never goes below 8 V either). 7 V is still available on a curve and by hand. A curve never stops the
pump and has no 12 V: the pump stops only with *Stop the pump when it is cool* (with its minimum run time).

**Update from 1.6.7 or older:** the temperature tiers become the common curve with the same behaviour, and the old
fixed duties of *Follow the laptop* (Office 40 %, Gaming 60 %, Turbo / Custom 90 %, pump 11 V) become flat curves of
those modes. A new install starts with the Balanced profile and no per-mode curves.

**Cooler firmware.** open-uniwill-cc shows the cooler firmware version but does not flash it: a failed DFU update can
leave the cooler unusable. Use the vendor tool or nRF Connect with the right package if you really need an update.

## Control Center 3.0 / Clevo (experimental, separate module)

Laptops with Control Center 3.x have no Uniwill EC; the module `uwccd/clevo/` drives them with Clevo DCHU commands
(ACPI `_DSM` of `CLV0001`): power modes, fan modes / offset / custom curve / anti-dust, fan monitoring, keyboard
colour / brightness / effects / sleep timer / boot effect. Windows: the Control Center 3 driver; Linux: the `uwcc`
module. Not tested on a Clevo laptop yet; commands are off until allowed — [CLEVO.md](CLEVO.md).

## What was ported

✅ works · ❌ not available · ➖ not needed / not applicable. Linux and Windows run the same service code; only the access
to the hardware differs (see the last section).

| Control Center feature | Linux | Windows | Implementation |
|---|:-:|:-:|---|
| Office / Gaming / Turbo mode, Fn mode key, OSD | ✅ | ✅ | EC `0x751`, NVRAM `PowerMode`, event `0xB0` |
| Profiles 1–3 for Gaming and Office | ✅ | ✅ | `Mode1/2_Profile*.json`, tables `M1T1…M2T3` |
| Custom mode with 5 slots, PL4, TCC offset, Smart APC limits (RamFan1p5 platforms) | ✅ | ✅ | EC `0x785/0x786/0x787`, `0x726` bit 7, ACPI `SMRW` |
| Fan Boost | ✅ | ✅ | bit 6 of `0x751`, event `0xA7` |
| CPU/GPU fan curves (16 levels), presets, factory reset | ✅ | ✅ | EC `0xF00–0xF5F`, factory tables from the EC (handshake `0xF5D/F5E/F5F`) |
| PL1/PL2 on AC and battery, factory PL from the EC | ✅ | ✅ | EC `0x783/0x784`, `0x730–0x737`, `0x7A7–0x7AA` |
| CPU temperature limit (TCC offset) | ✅ | ✅ | EC `0x786` |
| NVIDIA cTGP and Dynamic Boost | ✅ | ✅ | EC `0x743–0x746`; Dynamic Boost needs `nvidia-powerd` (Linux) / the NVIDIA service (Windows) |
| NVIDIA GPU temperature limit | ✅ | ✅ | `nvidia-smi -gtt` (Linux), NVAPI client thermal policies (Windows) |
| Balanced protection PH6PG0x/3x/7x (thermal profile S2) | ✅ | ✅ | EC `0x726`, event `0xCB` |
| Super performance (any mode) | ✅ | ✅ | `0x751 = 0x10`, factory Turbo table, cTGP maximum + Dynamic Boost |
| RAM overclocking | ✅ | ✅ | NVRAM `MemoryOverClockSwitch` (applied by the BIOS at the next start) |
| Power boost with the liquid cooler (CoolingOC / LiquidHWOC) | ✅ | ✅ | EC LC fan table `0xF5F`, firmware `INOU.PWUP` (kernel module ioctl / `UWACPIDriver`) |
| Monitor: temperatures, load, clocks, fans (%, rpm), power, memory, network, drives, battery | ✅ | ✅ | fans — EC `0x75B/0x75C`, `0x464/0x46B`; Linux: hwmon, RAPL, `/proc`, `nvidia-smi`; Windows: ACPI thermal zone, Energy Meter / processor counters, `nvidia-smi` |
| History 1 min … 24 h, export CSV / JSON | ✅ | ✅ | service-side recording, 24 h kept on disk |
| "Who keeps the discrete GPU awake" | ✅ | ❌ | runtime PM + process scan |
| ITE keyboard lighting: hardware effects, brightness, speed, direction, colours, multicolour | ✅ | ✅ | HID feature reports 08h/09h/14h (hidraw / hid.dll) |
| Four-zone ITE keyboards (usage page FF12, e.g. MAIBENBEN Tsunami) | ✅ | ✅ | Single, Breathing, Wave, Rainbow, Flash, Mix; smooth Wave, Colour wave, Flash, Neon, Stack, Impact drawn zone by zone |
| User mode (per-key colour) and gaming mode (WASD/arrows) — per-key keyboards | ✅ | ✅ | picture 12h / rows 16h |
| Software effects Neon, Stack, Impact, Alphabet | ✅ | ✅ | frames from `AP_Effect_Task` (`uwccd/lighting/oem`, proprietary) |
| Reactive effects (Reactive, Ripple, Aurora, Spark) light pressed keys | ✅ | ✅ | EC `0x741` bit 3 |
| *Not in the original:* untested effects — the greyed effects (not offered for this keyboard type by the original window, light-bar effects on a keyboard) can be tried: *Unlock untested effects*, a question before the first try, then *Does it work? Yes / No* (kept per keyboard, part of the diagnostic report). Music mode stays off | ✅ | ✅ | the same `08h` effect command; nothing is stored in the controller; `uwccctl kb effect NAME --try`, `uwccctl kb feedback NAME yes\|no` |
| *Not in the original:* 16 BetterRGB effects (Wave, Sparkle, Lightning, Flame, Rain, Matrix, Quicksand, Current, Screen ambient …) | ✅ | ✅ | frames from `uwccd/lighting/fx.py` (from BetterRGB, MIT): picture 12h on per-key keyboards, zone colours on four-zone ones — [LIGHTING.md](LIGHTING.md) |
| *Not in the original:* transitions, white calibration, top-row bar, frame rate on AC / battery | ✅ | ✅ | `uwccd/lighting/fx.py`; key presses: Linux `/dev/input`, Windows the tray app; screen: Windows tray app, Linux agent (X11) |
| LED colour correction per keyboard type / LED vendor | ✅ | ✅ | `WKDColor.cheatRGB_*` (`uwccd/lighting/oem`, proprietary) |
| Chassis light bar (hinge / base / logo) | ✅ | ✅ | HIDLightbar4, HID 0x7000 |
| Single-colour backlight (on/off, level) | ✅ | ✅ | EC `0x78C` |
| Backlight auto-off on inactivity | ✅ | ✅ | Linux: `/dev/input` events; Windows: idle time of the tray app |
| Windows key lock, Fn Lock | ✅ | ✅ | EC `0x767/0x768`, `0x74E`, NVRAM `FnKeyStatus` |
| USB charging in sleep, touchpad toggle, touchpad LED | ✅ | ✅ | EC `0x767` bit 4, `0x7A6`; touchpad on Windows: Win+Ctrl+F24 |
| Power on with AC | ✅ | ✅ | NVRAM `ACRecoveryStatus` or EC `0x726` bit 3 |
| NVIDIA Optimus / MUX (discrete GPU direct) | ✅ | ✅ | NVRAM `OemDisplayMode`, after a restart |
| Webcam switch | ✅ | ✅ | Linux: USB de-authorisation; Windows: `Disable-PnpDevice` |
| Wi-Fi / Bluetooth switches | ✅ | ❌ | rfkill |
| Battery protection modes (full / balanced / stationary) | ✅ | ✅ | EC `0x7A6` bits 4–5 |
| Custom charge limits | ✅ | ✅ | EC `0x7B9`, `0x7D0`, NVRAM `Charge*Limit` |
| Type-C charging priority | ✅ | ✅ | EC `0x7CC` bit 7 |
| Automation: mode per power source, overheating alerts, follow the power profile | ✅ | ✅ | power-profiles-daemon (Linux) / Windows power mode |
| App binding | ✅ | ✅ | process watch |
| Liquid cooling over Bluetooth (BT Cooling) | ✅ | ✅ | `bleak` (BlueZ / WinRT); see above |
| Liquid cooler firmware update (DFU) | ❌ | ❌ | not done on purpose: a failed update can leave the cooler unusable |
| Updates of this program | ✅ check | ✅ download + install | GitHub releases, checked against `SHA256SUMS.txt` |
| Diagnostic report for new laptops / bug reports | ✅ | ✅ | `uwccctl report`, *Information → Diagnostic report* |
| Platform profiles, EC self-check, administrator unlock of EC settings | ✅ `uwccctl ec` | ✅ EC Manager | [EC/Platforms.md](EC/Platforms.md) |
| EC access without the OEM driver: Windows WMI (open, beta) | ➖ | ✅ beta | `root\WMI AcpiTest_MULong`; no `PWUP` / `SMRW`, ~125 ms per access — see [EC/WMI-vs-Driver.md](EC/WMI-vs-Driver.md) |
| Full control from the command line (`uwccctl`, JSON output) | ✅ `man uwccctl`, bash completion | ✅ `uwccctl help` | everything the window changes; see [CLI.md](CLI.md) |
| Restart of a hung service | ✅ | ✅ | Linux: agent notice + polkit; Windows: tray with UAC |
| Keyboard power-on (welcome) effect | ❌ | ❌ | stored in a UEFI variable whose layout is not verified yet |
| Music lighting effect | ❌ | ❌ | needs audio capture (WASAPI in the original) |
| StarHitting / StarSpark | ➖ | ➖ | light bar only in the original |
| Display colour calibration, display modes (ICC / gamma) | ❌ | ❌ | Linux: GNOME Settings → Color; Windows: the system colour settings |
| Overclocking (Intel OC SDK, NVIDIA clock offsets), WhisperMode 2.0 | ❌ | ❌ | not ported (for NVIDIA on Linux: `nvidia-settings`) |
| Game monitor (FPS overlay), Dynamic Desk, key remapping | ❌ | ❌ | Windows-specific in the original; MangoHud is an overlay alternative on Linux |
| OTA — BIOS / EC / Control Center updates from the vendor server | ❌ | ❌ | firmware is not flashed by this program: use the vendor tools |
| MQTT — internal message bus between the original service, window and tray | ➖ | ➖ | replaced by the local HTTP API + server-sent events with a token |

### Hardware access: Linux and Windows

| | Linux | Windows |
|---|---|---|
| EC | kernel module `uwcc` (`/dev/uwcc`, DKMS), fallback `acpi_call` | OEM driver `UWACPIDriver.sys` (`\\.\ACPIDriver`) |
| Hot keys | WMI events through the module, fallback EC polling | WMI `AcpiTest_EventULong` |
| UEFI variable `UniWillVariable` | `/sys/firmware/efi/efivars` | `GetFirmwareEnvironmentVariable` |
| Keyboard / light bar | hidraw | SetupAPI + hid.dll |
| Desktop part | session agent `uwcc-agent` (notifications, OSD) | tray app `ControlCenter.exe` |
| Service | systemd `uwccd.service` | Windows service `uwccd` |
