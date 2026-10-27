# Platform profiles, self-check and EC Manager

**English** · [Русский](Platforms.ru.md)

Since 1.6.1 everything the program knows about one laptop platform is kept as data — a **platform profile** — and
a **self-check** in EC Manager tells what works on a laptop and what is not clear. This makes it possible to add other
Uniwill / Tongfang platforms without changing the code.

## EC Manager

The page *EC Manager* in the window (Windows), `uwccctl ec …` on the command line:

| Part | What it does |
|---|---|
| EC access path | **OEM driver + WMI** (recommended), OEM driver only, WMI only (beta) — see [WMI-vs-Driver.md](WMI-vs-Driver.md) |
| Platform profile | which profile applies to this laptop, its status, tested versions, notes; export / import / back to the built-in one |
| Self-check | stage 1 (read only), stage 2 (writes with read-back and restore), export for GitHub, apply as profile |
| Monitoring | off for the OEM driver / off for WMI / all off |
| WMI settings | `ec_wmi.json` — [WMI-config.md](WMI-config.md) |
| Check | quick test of the active path, restart of the service |

### Administrator rights

Every local user can open the window, so the risky settings need administrator rights: the EC access path, accepting
the WMI warning, `ec_wmi.json`, platform profiles, self-check stage 2.

- **Windows:** the window asks the tray program; it starts `uwccctl ec unlock` with a UAC prompt. After *Yes* these
  settings are open for 10 minutes (*Lock now* closes them earlier).
- **Linux:** `sudo uwccctl ec unlock [MIN]`.
- `uwccctl` run as administrator / root sends the administrator key itself — no unlock needed.

The key lives in `%ProgramData%\UWCC\run\admin-token` (SYSTEM and Administrators only) or `/run/uwcc/admin-token`
(root, 0600) and changes with every start of the service.

### Hard caps

No profile, import or `ec_wmi.json` can go above these limits:

| PL1 | PL2 | PL4 | TCC offset | Base TGP | cTGP | Dynamic Boost | GPU temperature limit |
|---|---|---|---|---|---|---|---|
| 200 W | 250 W | 300 W | 63 °C | 200 W | 50 W | 50 W | 100 °C |

For a project with a **verified** built-in profile the power limits may only go **down** from the factory values
(PL1 / PL2 160 W, PL4 250 W, base TGP 150 W, Dynamic Boost 25 W on project `0x10`).

## Platform profile

Built-in profiles: `uwccd/platforms/*.json`. Your own (imported or made by the self-check):
`%ProgramData%\UWCC\data\platforms\` / `/var/lib/uwcc/platforms/`; it replaces the built-in one of the same project
and is shown as *your profile*.

| Status | Meaning |
|---|---|
| `verified` | tested by the authors (only built-in profiles) |
| `community` | sent by users (an imported `verified` becomes `community`) |
| `draft` | made by your own self-check |
| `unknown` | generic profile for a project without its own: **every function stays off on the WMI path** |

The OEM driver path is not limited by the profile: with the manufacturer's driver everything works as before.

```json
{
  "schema": 1,
  "id": "uniwill-0x10",
  "name": "MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super / XMG NEO 16 (E23)",
  "status": "verified",
  "match": {"project": ["0x10"]},
  "tested": {"ec": ["1.13"], "bios": ["N.1.23A14"], "date": "2026-10", "by": "aspidovss"},
  "access": {
    "oem": {"driver": "UWACPIDriver", "smrw": true, "pwup": true},
    "wmi": {"namespace": "root\\WMI", "class": "AcpiTest_MULong", "method": "GetSetULong", "instance": "1_1",
            "encoding": {"read_flag_bit": 40, "value_shift": 16, "read_mask": 255}, "smrw": false, "pwup": false}
  },
  "wmi": {"poll": {...}, "always_write": [...], "no_cache": [...], "features": {"modes": "on", "fan_tables": "slow", ...}},
  "limits": {"PL1": 160, "PL2": 160, "PL4": 250, "TccOffset": 5, "DefaultTGP": 150, "ConfigurableTGP": 0,
             "DynamicBoost": 25, "TargetTemperature": 87, "DynamicBoostCpuTdp": 0},
  "notes": {"en": ["..."], "ru": ["..."]}
}
```

| Key | Meaning |
|---|---|
| `match.project` | Uniwill project IDs (EC `0x740`) the profile applies to |
| `access.wmi.encoding` | bit layout of the WMI call: read `Data = (1 << read_flag_bit) \| addr`, write `Data = (value << value_shift) \| addr` |
| `wmi.features` | `on` / `slow` / `off` per function — the defaults of [WMI-config.md](WMI-config.md) |
| `limits` | used instead of the firmware table `SMRW`, which WMI cannot reach |
| `evidence` | (draft) what the self-check saw for every check |

> On the Tsunami (project `0x10`) the graphics card gets 150 W in Office and Gaming and 175 W in Turbo (the firmware's
> own Turbo writes Dynamic Boost as cTGP). **Through WMI the extra graphics power is reached only in the stock Turbo
> mode**; Dynamic Boost in the Custom mode adds power only while the processor leaves room.

## Self-check

**Stage 1 — read only.** Identity (project, BIOS project, EC / BIOS versions, matching profile, tested versions);
access paths (when both the OEM driver and WMI are present — the same 34 registers compared byte by byte);
plausibility (RamFan 1.5, mode byte, factory PL, fans, battery, control flag, cooler support, limit table);
time per access; firmware methods in the ACPI tables (`WMBC`, `RKBC`, `WKBC`, `SMRW`, `PWUP` …) and the WMI class.

**Stage 2 — writes** (administrator, AC power). Each function is changed a little and back, with read-back:

| Check | Register | Change |
|---|---|---|
| Fn Lock | `0x74E` bit 4 | toggled |
| Touchpad toggle flag | `0x7A6` bit 6 | toggled |
| Mode byte | `0x751` | Gaming ↔ Office |
| Fan Boost | `0x751` bit 6 | on for up to 8 s — do the fans speed up? |
| PL1 | `0x783` | lowered (25 W or −5 W) |
| cTGP target | `0x744` | −5 W (or 5 W from 0) |
| Charge limit | `0x7B9` | 95 % (or 100 %) |
| Fan-table handshake | `0xF5D–0xF5F` | the EC copies its factory table; then the profile's table is written again |

Before stage 2 **every value it writes is backed up** — the registers above, the fan-table handshake `0xF5D–0xF5F`
and the fan table `0xF00–0xF5C` (106 values): to `selfcheck-snapshot.json` (restored on the next start if the service
stops in the middle) and to a dated copy `selfcheck-backups/ec-backup-YYYYMMDD-HHMMSS.json` in the data folder (the last
ten are kept). The files are read back first; if the backup cannot be saved, nothing is written. The window shows that
the backup was made while the check runs. At the end the values are written back, read back and compared — the
window shows how many match — and the current mode profile is applied again.

**Result:** every check with ✓ / ! / ✕ / – and its evidence, the list **Not clear**, the functions for a draft
profile. *Export for GitHub* writes `uwcc-selfcheck.json` (no serial numbers): attach it to an issue to have your
model added. *Apply as platform profile* (administrator) saves the draft as this laptop's profile; on the WMI path it
then decides which functions are available (restart the service).

```powershell
uwccctl ec selfcheck            # stage 1
uwccctl ec selfcheck 2 --export uwcc-selfcheck.json     # as administrator
uwccctl ec platform apply-draft
uwccctl ec platform export my-laptop.json
```

## Monitoring

| Switch | Effect |
|---|---|
| Off for the OEM driver / for WMI | no sensor polling through that path: the Monitor page and the history stop; the temperatures for the liquid cooler and the overheat alerts are read every 20 s |
| All off | nothing is read: no Monitor page, history or alerts; the liquid cooler in the automatic mode runs the fixed *Medium* preset |

In the window it is one drop-down: full / off with the OEM driver / off with WMI / off with both / all off;
`uwccctl ec monitor oem|wmi|all on|off`.

The same card sets the **sampling interval** (automatic: 2 s with the OEM driver, 5 s with WMI; or 1–60 s) and the
**history** of the last 24 hours: its size on disk, the **maximum size** (default 2 MB; beyond it the oldest minutes are
dropped), the **folder** (`history-24h.json`, default in the data folder; moving it needs administrator rights) and
**Clear the history**.

## Slow path: "Applying…"

On the WMI path a mode switch writes the mode, power limits and Fan Boost first (about 1–2 s; the window is covered
with *Applying…*), then the fan curve in the background (~15 s, *Fan curve: writing N %* in the side bar; the mode
cards and the fan page wait). A curve that is the same as the one in the EC is not written again. Mode changes sent
while a mode is being applied are refused with `409 busy`.
