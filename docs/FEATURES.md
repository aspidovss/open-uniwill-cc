# Features

**English** · details of what open-uniwill-cc does and how (EC registers, ACPI methods, WMI events).
Windows differences: [README.windows.md](../README.windows.md#differences-from-linux). Protocol: [PROTOCOL.md](PROTOCOL.md) (Russian).

## Modes: two kinds of platforms

The original service has two different mode managers and picks one by the project ID from the EC; this port does the same:

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
`uwccctl status` shows which manager runs (`[cml]` / `[std]`). If the choice is wrong for your laptop it can be forced with
`"fan_manager": "cml"` or `"std"` in `settings.json` (Linux `/var/lib/uwcc`, Windows `%ProgramData%\UWCC\data`), then restart the service.
Not ported from the RamFan1p5 manager (Windows APIs): GPU core/memory clock offsets and target temperature (NVAPI),
CPU voltage offset (Intel OC SDK), WhisperMode, memory overclocking.

## Automation (Settings → Automation)

* **Power source:** a mode for "charger plugged in" (keep / the mode before unplugging / a mode) and for "unplugged";
  keyboard backlight off on battery; follow the mode with power-profiles-daemon (Turbo → performance, battery → power saver).
* **Overheating:** a desktop notice when the CPU or GPU stays at the limit (default 95 °C / 87 °C) for 30 s, at most once
  in 10 minutes; optionally Fan Boost is switched on if it is still hot 30 s later.

## Monitoring extras

* **Last hour** chart on the Monitor page: temperatures, load, CPU package power (RAPL) and GPU power, fan speed, cooler.
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
| Modes: Automatic (CPU/GPU temperature tiers with 3 °C hysteresis), Controller (EC targets), Low 25 %/7 V, Medium 50 %/8 V, High 90 %/11 V, Manual, Off | fan `0x1B`, pump `0x1C` |
| Editable temperature tiers (default <55 °C 25 %/7 V, <70 °C 50 %/8 V, <85 °C 75 %/11 V, above 90 %/11 V) | |
| Lighting: static, breathing, rainbow, breathing rainbow; Mk2 also spiral, rotating rainbow, colour wave | `0x1E` / `0x33` |
| Coolant flow check every 15 s with a desktop alert when the pump runs but nothing circulates | `0x32` |
| Coolant filling cycle (8 pump pulses, ~70 s) | `0x19` |
| Fn cooler boost keys (fan ≥ 60 %, pump ≥ 8 V); EC told that a cooler is attached (`0x7C7` bit 1) on laptops that declare support | WMI `0xCD`/`0xCE` |
| **Follow the laptop** mode: Office 40 %, Gaming 60 %, Turbo/Custom 90 %, pump 11 V | |
| **Flow guard:** with no coolant flow the pump goes to 11 V and the fan to ≥ 60 % until the laptop's mode changes or you pick a setting | |

```bash
uwccctl lc scan                      # find coolers
uwccctl lc connect C0:FF:EE:..:..:.. # connect and remember
uwccctl lc mode auto                 # auto | ec | low | medium | high | off
uwccctl lc manual 60 8               # fan 60 %, pump 8 V
uwccctl lc rgb 00ffff breathe        # colour and effect;  uwccctl lc rgb off
uwccctl lc prime                     # filling cycle
```

The automatic tiers start at 8 V: on some units the flow does not hold at 7 V and the cooler switches itself off
(the OEM service never goes below 8 V either). Low (7 V) is still available by hand.

**Cooler firmware.** open-uniwill-cc shows the cooler firmware version but does not flash it: a failed DFU update can
leave the cooler unusable. Use the vendor tool or nRF Connect with the right package if you really need an update.

## What was ported

| Control Center feature | Status | Implementation |
|---|---|---|
| Office / Gaming / Turbo mode, Fn mode key, OSD | ✅ | EC `0x751`, NVRAM `PowerMode`, WMI event `0xB0` |
| Profiles 1–3 for Gaming and Office | ✅ | `Mode1/2_Profile*.json`, tables `M1T1…M2T3` |
| Fan Boost | ✅ | bit 6 of `0x751`, event `0xA7` |
| CPU/GPU fan curves (16 levels), factory reset | ✅ | EC `0xF00–0xF5F`, factory tables from the EC (handshake `0xF5D/F5E/F5F`) |
| PL1/PL2 on AC and battery, factory PL from the EC | ✅ | EC `0x783/0x784`, `0x730–0x737`, `0x7A7–0x7AA` |
| NVIDIA cTGP and Dynamic Boost | ✅ | EC `0x743–0x746` |
| Balanced protection PH6PG0x/3x/7x (thermal profile S2) | ✅ | EC `0x726`, event `0xCB` |
| Monitor: temperatures, load, clocks, fans (%, rpm), memory, network, drives, battery | ✅ | fans — EC `0x75B/0x75C`, `0x464/0x46B`; rest — hwmon, `/proc`, `nvidia-smi` |
| ITE lighting: 17 hardware effects, brightness, speed, direction, colours, multicolour | ✅ | HID feature reports 08h/09h/12h/14h/16h via hidraw |
| User mode (per-key colour) and gaming mode (WASD/arrows) | ✅ | picture 12h / rows 16h |
| Software effects Neon, Stack, Impact, Alphabet | ✅ | frames from `AP_Effect_Task` (`uwccd/lighting/oem`, proprietary) |
| LED colour correction per LED vendor | ✅ | `WKDColor.cheatRGB_*` (`uwccd/lighting/oem`, proprietary) |
| Single-colour backlight (on/off, level) | ✅ | EC `0x78C` |
| Backlight auto-off on inactivity | ✅ | timer on `/dev/input` events |
| Windows key lock, Fn Lock | ✅ | EC `0x767/0x768`, `0x74E`, NVRAM `FnKeyStatus` |
| USB charging in sleep, touchpad toggle, touchpad LED | ✅ | EC `0x767` bit 4, `0x7A6` |
| Power on with AC | ✅ | NVRAM `ACRecoveryStatus` or EC `0x726` bit 3 |
| NVIDIA Optimus / MUX (discrete GPU direct) | ✅ | NVRAM `OemDisplayMode`, after a restart |
| Battery protection modes (full / balanced / stationary) | ✅ | EC `0x7A6` bits 4–5 |
| Custom charge limits | ✅ | EC `0x7B9`, `0x7D0`, NVRAM `Charge*Limit` |
| Type-C charging priority | ✅ | EC `0x7CC` bit 7 |
| Wi-Fi / Bluetooth | ✅ | rfkill |
| App binding | ✅ | process watch |
| Liquid cooling over Bluetooth (BT Cooling) | ✅ | see above; DFU firmware update ❌ |
| Custom mode with 5 slots, PL4, TCC offset, Smart APC limits (RamFan1p5 platforms) | ✅ | EC `0x785/0x786/0x787`, `0x726` bit 7, ACPI `SMRW` |
| Keyboard power-on (welcome) effect | ❌ | stored in a UEFI variable whose layout is not verified yet |
| Music lighting effect | ❌ | needs audio capture (Windows WASAPI in the original) |
| StarHitting / StarSpark | ➖ | light bar only in the original |
| Display colour calibration, display modes (Windows ICC/gamma) | ❌ | use GNOME: Settings → Color |
| Overclocking (Intel OC SDK, NVIDIA offsets), WhisperMode 2.0 | ❌ | no Linux API (for NVIDIA use `nvidia-settings`) |
| Game monitor (FPS overlay), Dynamic Desk, key remapping | ❌ | Windows-specific; MangoHud is an overlay alternative |
| OTA, MQTT | ❌ | not needed on Linux |

