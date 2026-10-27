# EC — MAIBENBEN Tsunami X629

**English** · [Русский](README.ru.md)

Documentation and a test tool for the embedded controller (EC) of the MAIBENBEN Tsunami X629 laptop
(Uniwill, project `0x10`).

| File | Contents |
|---|---|
| [Registers.md](Registers.md) | EC register reference: addresses, bits, values read on the Tsunami, fan table, liquid cooler, firmware methods, examples |
| [WMI-vs-Driver.md](WMI-vs-Driver.md) | EC access through the OEM driver vs Windows WMI: what works, speed, what is lost without the driver |
| [WMI-config.md](WMI-config.md) | WMI path settings (`ec_wmi.json`): every key, functions, setting it up for another laptop |
| [Platforms.md](Platforms.md) | platform profiles, the self-check, EC Manager, administrator rights, hard caps, monitoring switches |
| `ec_tool.py` | test tool |
| `ec_tool.json` | default settings of the tool |

## ec_tool.py

Requires Python 3 and, for WMI, `pywin32` (`python -m pip install pywin32`). Run as administrator.

```
python ec_tool.py COMMAND [ARGS] [--backend driver|wmi|service|auto] [options]
```

| Command | What it does |
|---|---|
| `info` | summary: project, capabilities, mode, power, fans, battery, liquid cooler |
| `read ADDR …` | read registers; ranges like `0x783-0x787` |
| `dump START [LEN]` | hex dump |
| `decode [GROUP …]` | every known register, decoded; groups — see `groups` |
| `fantable` | the fan table `0xF00–0xF5F` by level |
| `watch ADDR …` | values every `--interval` s, `--count`, `--csv FILE` |
| `write ADDR VALUE` / `bit ADDR BIT on\|off` | write (only registers marked writable; `--force` at your own risk; `--restore SEC` puts the old value back after SEC s) |
| `compare [ADDR …] --with BACKEND` | compare two access paths |
| `bench [N]` | read speed |
| `pwup LEVEL` | call `PWUP(level)` (OEM driver only) |

Backends: `driver` — OEM driver; `wmi` — built-in Windows WMI; `service` — the open-uniwill-cc service (read only);
`auto` — the driver if present, otherwise WMI.

### Settings `ec_tool.json`
| Key | Default | Meaning |
|---|---|---|
| `backend` | `auto` | default backend |
| `compare_with` | `driver` | second backend for `compare` |
| `wmi_instance` | `1_1` | `AcpiTest_MULong` instance |
| `service_port` | `47321` | service port |
| `interval`, `count` | `2.0`, `0` | for `watch` (`0` — until Ctrl+C) |
| `watch` | fan speeds, duty, mode, cooler | registers for `watch` without arguments |
| `writable_extra` | `[]` | additionally allow writing these registers |
| `writable_deny` | `0x7C7`, `0xF5D–0xF5F` | never write these, even if marked writable |
| `names` | | your own labels for unknown registers |

### Examples
```powershell
python ec_tool.py info
python ec_tool.py --backend wmi decode power fans
python ec_tool.py read 0x783-0x787 --json
python ec_tool.py fantable
python ec_tool.py watch --interval 1 --count 60 --csv ec.csv
python ec_tool.py bit 0x74E 4 on --restore 5        # Fn Lock on for 5 seconds
python ec_tool.py --backend wmi compare --with driver
python ec_tool.py --backend wmi bench 20
```
