# Project structure

**English** · [Русский](STRUCTURE.ru.md)

How open-uniwill-cc is put together: which part runs where, what each file does and where to start when changing
something. Building and debugging: [BUILD.md](BUILD.md). Features in detail: [FEATURES.md](FEATURES.md).
EC protocol: [PROTOCOL.md](PROTOCOL.md).

## How it works

```text
            ┌──────────────── user session ────────────────┐
            │  window (web UI)      tray / session agent   │
            │  bin/uwcc             ControlCenter.exe      │
            │  uwccd/web/*          bin/uwcc-agent         │
            └──────────┬───────────────────┬───────────────┘
                       │ HTTP + SSE, 127.0.0.1, token
            ┌──────────▼───────────────────▼───────────────┐
            │  service uwccd (root / LocalSystem)          │
            │  api → service → fan / settings / lighting   │
            │        monitor / automation / watercooler    │
            └──────────┬───────────────────┬───────────────┘
                       │ EC RAM, ACPI      │ USB HID, Bluetooth LE
   Linux: kernel/uwcc.ko (/dev/uwcc)       keyboard ITE 829x,
          or acpi_call                     liquid cooler
   Windows: UWACPIDriver.sys (OEM driver)
```

- **One service, two systems.** `uwccd` is the same Python code on Linux and Windows; only the low-level backends
  differ (`uwccd/ec.py` on Linux, `uwccd/win/` on Windows).
- **The service owns the hardware.** It runs with administrator rights, applies the settings at start and after
  sleep, and keeps the fan curves and the liquid cooler going without a window open.
- **Everything else is a client** of its local HTTP API: the window, the tray app / session agent and `uwccctl`.
  The API listens on `127.0.0.1` only, changes need a token ([SECURITY.md](../SECURITY.md)).
- **Settings** live in `/var/lib/uwcc` (Linux) or `C:\ProgramData\UWCC\data` (Windows); the token in
  `/run/uwcc/token` or `C:\ProgramData\UWCC\run\token`.

## Top level

| Path | What |
|---|---|
| `uwccd/` | the service and the web UI |
| `uwccd/win/` | Windows backends, tray app, service host |
| `uwccd/lighting/` | keyboard lighting; `oem/` — code derived from the OEM program (proprietary) |
| `uwccd/web/` | the interface: `index.html`, `app.js`, `app.css`, `i18n.js` (Russian strings), icons |
| `bin/` | `uwcc` (window), `uwcc-agent` (Linux session agent), `uwccctl` (command line) |
| `docs/CLI.md` | command line reference (`docs/CLI.ru.md` in Russian) |
| `docs/EC/` | EC registers, OEM driver vs WMI, WMI settings, `ec_tool.py` |
| `man/` | `uwccctl.1` man page (English; `man/ru/` Russian), installed by `install.sh` |
| `kernel/` | Linux kernel module `uwcc` — EC access and hot keys (GPL-2.0, DKMS) |
| `packaging/` | Linux: systemd unit, sleep hook, desktop files, polkit rule |
| `windows/` | PyInstaller spec and entry points, Inno Setup script, `install.ps1` / `uninstall.ps1` |
| `proprietary/` | OEM ACPI driver and factory fan tables (not part of the MIT code, optional) |
| `tests/` | tests against the simulated EC (`python3 -m unittest discover -s tests`) |
| `tools/re/` | tools used to study the original program (.NET IL dump and lifting) |
| `docs/` | documentation and screenshots |
| `install.sh`, `uninstall.sh` | Linux install / removal |
| `build.cmd`, `build_windows.ps1` | Windows build |

## The service — `uwccd/`

**Core**

| File | What |
|---|---|
| `__main__.py` | command line of the service (`--mock`, `--backend`, `--port`, `-v`) |
| `__init__.py` | version, contact, build stamp |
| `service.py` | the core: finds the platform, starts all parts and threads, collects the state for the UI, events |
| `api.py` | local HTTP API, the web UI files, server-sent events for the window and the tray |
| `store.py` | JSON files of the settings (atomic writes) |
| `settings.py` | switches (Win key, Fn lock, touchpad, USB power, webcam, MUX…) and battery protection |

**Hardware access**

| File | What |
|---|---|
| `ec.py` | EC backends: kernel module, `acpi_call`, simulation (`--mock`), no-access stub, read cache for slow paths |
| `ecaccess.py` | Windows EC path choice (OEM driver / WMI beta), the WMI warning, `ec_wmi.json` |
| `admin.py` | administrator key and the 10-minute unlock of the EC Manager settings |
| `busy.py` | long operations the window waits for ("Applying…", fan curve in the background) |
| `platformdb.py` | platform profiles (`platforms/*.json`), hard caps, validation |
| `selfcheck.py` | EC self-check: stage 1 read only, stage 2 writes with read-back and restore, draft profile |
| `platforms/` | built-in platform profiles (`uniwill-0x10.json`, `generic-uniwill.json`) |
| `regs.py` | map of EC registers used by the original service |
| `hw.py` | platform identification: project id, capabilities, model names, support level |
| `nvram.py` | UEFI variable `UniWillVariable` (settings the firmware keeps) |
| `events.py` | hot keys (WMI / module / EC polling), idle timer, app → mode binding |

**Modes, fans, power**

| File | What |
|---|---|
| `fan.py` | modes, profiles and fan tables (commercial projects), table storage |
| `fan_std.py` | modes Office / Gaming / Turbo / Custom of the other projects, power limits PL1 / PL2 / PL4, cTGP |
| `gputemp.py` | NVIDIA GPU target temperature |
| `nvpowerd.py` | checks the NVIDIA service that runs Dynamic Boost |
| `hwoc.py` | “super performance” with the liquid cooler (EC table + firmware OC level) |

**Lighting, cooler, monitoring, extras**

| File | What |
|---|---|
| `lighting/keyboard.py` | keyboard backlight manager (ITE RGB or single-colour EC) |
| `lighting/ite.py` | ITE 829x per-key RGB controller over USB HID |
| `lighting/oem/` | hardware and software effects ported from the OEM program |
| `watercooler.py` | liquid cooler over Bluetooth LE: XMG Oasis Mk1 / Mk2 and twins, tiers, flow guard |
| `monitor.py` | temperatures, load, clocks, fans, power, drives, battery |
| `automation.py` | mode per power source, overheating alerts, history (1 min … 24 h) |
| `backup.py` | export / import of settings |
| `updates.py` | update check and verified download from GitHub releases |
| `report.py`, `report_oem.py` | diagnostic report (zip) for bug reports and new laptops |
| `agentcore.py` | notification texts shared by the Linux agent and the Windows tray |

## Windows — `uwccd/win/`

| File | What |
|---|---|
| `winservice.py` | the Windows service host (the installer sets restart on failure) |
| `acpidrv.py` | EC access through the OEM driver `UWACPIDriver.sys` |
| `wmiec.py` | EC access through the Windows built-in WMI (`AcpiTest_MULong`), open implementation, beta |
| `wmievents.py` | hot keys from WMI `AcpiTest_EventULong` |
| `hid.py` | HID access for the keyboard (SetupAPI + hid.dll) |
| `sysinfo.py`, `pdhpower.py` | monitor data on Windows, CPU power from the Energy Meter counters |
| `winplat.py`, `winapi.py` | small Windows helpers (DMI, processes, WMI), ctypes layer |
| `tray.py` | `ControlCenter.exe`: tray icon, OSD, notifications, updates, service restart |

## Linux packaging

| File | What |
|---|---|
| `kernel/uwcc.c` | kernel module: `/dev/uwcc` ioctls for EC read / write, SMRW, PWUP; WMI hot keys |
| `packaging/uwccd.service` | systemd unit of the service (restarts on failure) |
| `packaging/system-sleep-uwcc` | puts the liquid cooler to sleep before suspend, re-applies the settings after |
| `packaging/50-uwcc.rules` | polkit: group `uwcc` may restart the service |
| `packaging/*.desktop` | menu entry of the window and autostart of the agent |
| `packaging/uwccctl.bash-completion` | bash completion of `uwccctl` commands |

## Where to start

- **A new laptop** — run `uwccctl report` on it; project ids and capabilities are in `hw.py`, registers in `regs.py`,
  modes in `fan_std.py`. The report shows what the original program of that laptop does differently.
- **A new setting / switch** — `settings.py` (service), `api.py` (setting key), `web/app.js` + `index.html` (UI),
  `web/i18n.js` (Russian text), a test in `tests/test_mock.py`.
- **UI work without the laptop** — `python3 -m uwccd --mock --token test`, open `http://127.0.0.1:47321/#token=test`.
