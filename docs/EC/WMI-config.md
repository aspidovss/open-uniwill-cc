# WMI settings (`ec_wmi.json`) — open EC implementation (beta, Windows)

**English** · [Русский](WMI-config.ru.md)

open-uniwill-cc can reach the embedded controller (EC) on Windows in two ways:

| Path | What it uses | Setting `ec_backend` |
|---|---|---|
| **OEM driver + WMI** (default, recommended) | the manufacturer's `UWACPIDriver.sys`; WMI only when the driver is missing and you accepted the warning | `auto` |
| **OEM driver only** | `UWACPIDriver.sys`; without it there is no EC access | `oem` |
| **WMI only** (not recommended, beta) | the Windows built-in WMI driver, no proprietary files | `wmi` |

The path is chosen in the installer, in **EC Manager** in the window, or with `uwccctl driver use auto|oem|wmi`.
The WMI path is used only after the warning in the window was accepted.

> ⚠ **We do not recommend the WMI path on platforms other than MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super /
> XMG NEO 16 (E23)** (Uniwill project `0x10`). On another model the same WMI call may mean something else.

What the WMI path can and cannot do, and the measurements behind it: [WMI-vs-Driver.md](WMI-vs-Driver.md).
Register reference: [Registers.md](Registers.md).

## Where the settings live

- Factory settings come from the platform profile of the laptop ([Platforms.md](Platforms.md)); a laptop without its
  own profile gets the generic one, where every function is off on the WMI path until the self-check confirms it.
- Your changes: `%ProgramData%\UWCC\data\ec_wmi.json` — only the keys you changed; they override the factory ones.
- Changing them needs administrator rights (UAC prompt / `sudo uwccctl ec unlock`); limits cannot exceed the hard
  caps, and on a verified platform not the factory values.
- Edit them in **EC Manager → WMI settings** (Save / Import / Export / Factory settings) or with
  `uwccctl driver config export FILE`, `uwccctl driver config import FILE`, `uwccctl driver config reset`.
- `features` apply at once; `poll`, `timeout_s`, `instance`, `limits`, `always_write`, `no_cache` after the service
  restarts (EC Manager → Restart the service).

## Keys

```json
{
  "instance": "1_1",
  "timeout_s": 5,
  "poll": { "cache_ms": 4000, "monitor_s": 5, "status_s": 15 },
  "always_write": ["0x767", "0xF5D-0xF5F", "0x7C7"],
  "no_cache": ["0xF5D-0xF5F"],
  "features": { "modes": "on", "fan_tables": "slow", "power_boost_lc": "off" },
  "limits": {
    "0x10": { "PL1": 160, "PL2": 160, "PL4": 250, "TccOffset": 5, "ConfigurableTGP": 0, "DynamicBoost": 25,
              "TargetTemperature": 87, "DefaultTGP": 150, "DynamicBoostCpuTdp": 0 }
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `instance` | `1_1` | which `AcpiTest_MULong` instance to call (`ACPI\PNP0C14\1_<n>`); any works on the Tsunami |
| `timeout_s` | `5` | one WMI call may take this long (1–30 s) before it is treated as failed |
| `poll.cache_ms` | `4000` | a register read stays valid this long; repeated reads come from the cache (0–60000) |
| `poll.monitor_s` | `5` | how often the monitor and history sample the sensors (1–60 s; 2 s with the OEM driver) |
| `poll.status_s` | `15` | reserved for slower status reads (2–300 s) |
| `always_write` | `0x767`, `0xF5D–0xF5F`, `0x7C7` | written even when the value did not change: triggers, the fan-table handshake, the cooler flag |
| `no_cache` | `0xF5D–0xF5F` | always read fresh (the EC answers the handshake there) |
| `features.<name>` | see below | `on` — works, `slow` — works and the window marks it "slow with WMI", `off` — greyed out |
| `limits.<project>` | project `0x10` | the Smart APC table (SMRW) cannot be read through WMI; these values are used instead. Without an entry for your project the limits come from the factory PL in the EC |

Addresses are hex strings; ranges like `"0xF5D-0xF5F"` are allowed.

### Functions (`features`)

| Name | Window | WMI default |
|---|---|---|
| `modes` | mode cards, profile slots, "Restore default settings" | on |
| `fan_boost` | Fan Boost | on |
| `power_limits` | profile editor: PL1 / PL2 / PL4, TCC | on |
| `gpu_power` | profile editor: cTGP, Dynamic Boost | on |
| `super_performance` | Super performance | on |
| `fan_tables` | Fan settings (writing a curve takes ~15 s) | slow |
| `fan_monitor` | fan speed readings | slow |
| `battery` | battery protection mode, charge limits, Type-C priority | on |
| `switches` | Fn Lock, Win key, USB in sleep, touchpad, power on with AC | on |
| `lightbar_ec` | light bar through the EC trigger | on |
| `lc_ec` | liquid cooler: EC targets, "cooler attached" flag | on |
| `power_boost_lc` | Power boost with liquid cooling — **always off**, needs `PWUP` (OEM driver) | off (locked) |

## Setting it up for another laptop

1. Read [WMI-vs-Driver.md](WMI-vs-Driver.md) and the warning above. Keep the OEM driver if you have it.
2. Check that the WMI interface exists and answers: in an administrator PowerShell
   ```powershell
   python docs\EC\ec_tool.py --backend wmi info
   python docs\EC\ec_tool.py --backend wmi compare --with driver     # if the OEM driver is installed
   ```
   `info` must show your project ID and sensible values; `compare` must report all registers equal.
3. If you have the OEM driver, read the real limits once and put them under `limits.<your project id>`:
   `uwccctl status --json` (field `state.power.limits` while the OEM path is active) or `ec_tool.py read`.
4. Turn off in `features` everything your laptop does not have or that does not behave.
5. Export the file and keep it; send it with a diagnostic report if you want your model added.

## Examples

```powershell
uwccctl driver                          # path, OEM driver, features, EC access counters
uwccctl driver use wmi                  # select WMI; accept the warning in the window (or add --accept-risks)
uwccctl driver config export ec_wmi.json
uwccctl driver config import ec_wmi.json
uwccctl driver test                     # project ID, a few registers, ms per read
uwccctl driver use auto                 # back to the OEM driver
```
