# uwccctl — command line reference

`uwccctl` (Linux) / `uwccctl.exe` (Windows) controls the `uwccd` service. Everything the window changes is available
here, so the laptop can be managed from scripts, hotkeys, SSH or a system without a desktop.

- Linux: `man uwccctl` (Russian: `man -L ru uwccctl`); bash completion is installed by `install.sh`.
- Both systems: `uwccctl help` and `uwccctl help COMMAND`.
- Access: the token in `/run/uwcc/token` is readable by group `uwcc` (log out and in once after installation) and root;
  on Windows by administrators and the installing user.

```text
uwccctl [--json] COMMAND [ARGS]
```

Commands without arguments show the state; with arguments they change it and show the new state.

## Output for scripts

| | |
|---|---|
| `--json` | anywhere on the line; one JSON document (`monitor --watch` — one object per line, NDJSON) |
| errors | text on stderr; with `--json` — `{"error": "..."}` on stdout |
| exit codes | `0` success, `1` rejected by the service (range, not on this laptop), `2` wrong usage, `3` service not running / no access |
| environment | `UWCC_PORT` (default 47321), `UWCC_TOKEN`, `UWCC_TOKEN_FILE` |

```bash
uwccctl --json monitor | jq .cpu.temp
uwccctl --json monitor --watch 5 >> sensors.ndjson
uwccctl mode turbo || echo "failed: $?"
```

## Overview

| Command | |
|---|---|
| `status` | model, mode, profile, PL, fans, temperatures, battery, liquid cooler, switches |
| `monitor [--watch [SEC]]` | sensors once or every SEC s (default 2) until Ctrl+C |
| `history [csv\|csv-excel\|json] [1m\|5m\|15m\|1h\|24h] [FILE]` | recorded sensor history |

## Performance

| Command | |
|---|---|
| `mode [office\|gaming\|turbo\|custom]` | show / switch the mode |
| `profile [N]` | show the active profile / select slot N (from 0) of the current mode |
| `profile list` | all profiles, the active one marked `*` |
| `profile show [TARGET]` | values of a profile |
| `profile set [TARGET] KEY=VALUE ...` | change a profile (keys below) |
| `profile reset [TARGET]` | factory values and fan curve of the slot |
| `boost [on\|off]` | FanBoost |
| `super [on\|off]` | super performance (Turbo fan table, max cTGP + Dynamic Boost), any mode |
| `ramoc [on\|off]` | RAM overclocking; applies after a reboot |
| `restore --yes` | factory profiles and fan tables of every mode |

`TARGET`: `office`, `custom:2` (mode and slot from 0) or `Mode4_Profile3`; default — the active profile.

| Key | Value |
|---|---|
| `pl1`, `pl2`, `pl4` | W (PL2 is raised to PL1; PL4 ≥ PL2) |
| `tcc` | °C below Tjmax, or `off` |
| `ctgp` | NVIDIA configurable TGP, W, or `off` |
| `db` | Dynamic Boost, W, or `off` |
| `gputemp` | GPU temperature limit, °C, or `off` |
| `fanspeed` | fan switch speed 100..12700 rpm, or `off` |
| `name` | custom slot name, up to 24 characters |

```bash
uwccctl profile set custom:0 pl1=65 pl2=90 tcc=10 ctgp=off name=Quiet
```

## Fan tables

| Command | |
|---|---|
| `fan list` | tables and the profiles using them |
| `fan show [TABLE]` | levels as `UP/DOWN:DUTY` |
| `fan set TABLE cpu\|gpu POINT ...` | replace a curve, up to 16 points |
| `fan set TABLE --file FILE` | load JSON saved with `fan show --json` |
| `fan separate TABLE on\|off` | separate CPU and GPU curves |
| `fan reset TABLE` | factory curve |

`TABLE`: `M1T1` … `M4T5` or `current`. A point `UP/DOWN:DUTY` — the level starts at UP °C, drops back below DOWN °C,
the fan runs at DUTY %. Level 0 starts at 0 °C, temperatures must not decrease, the last level needs ≥ 40 %.

```bash
uwccctl fan set current cpu 0/45:0 55/50:30 70/65:60 85/80:100
```

## Battery

| Command | |
|---|---|
| `battery` | mode, limits, cycles, Type-C priority |
| `battery mode full\|balanced\|stationary` | protection mode |
| `battery limit UP [DOWN]` | stop at UP % (1..100), resume below DOWN % (1..95) |
| `battery typec on\|off` | charge from Type-C first |

## Keyboard and light bar

| Command | |
|---|---|
| `kb` / `kb on\|off` | state / power |
| `kb effects` | effects with numbers and support on this keyboard |
| `kb effect NAME\|N [options]` | start an effect; options not given keep their values |
| `kb effect NAME --try` | an effect not checked on this keyboard (greyed in the window) |
| `kb feedback NAME yes\|no` | did the untested effect work? (kept for the diagnostic report) |
| `kb level N` | brightness 0..4 |
| `kb fx` | BetterRGB effects (drawn by the service): numbers, parameters, settings |
| `kb fx NAME\|N [--light 0..4] [KEY=VALUE ...]` | start a BetterRGB effect; parameters not given keep their values |
| `kb fx-config KEY=VALUE ...` | `fps_ac`, `fps_battery` (10..60), `transition`, `transition_ms`, `bar`, `bar_direction`, `bar_start`, `bar_end` |
| `kb fx-calibrate start\|cancel\|reset` / `kb fx-calibrate apply RRGGBB` | white calibration (RRGGBB: the colour you see) |
| `lb [hinge\|base\|logo] on\|off` | light bar zone (default `hinge`) |
| `lb [ZONE] color RRGGBB [EFFECT]` | colour |
| `lb [ZONE] effect static\|breathing\|breathing_multi\|wave\|cycle\|rainbow\|colorbreath\|colorwave` | effect |
| `lb [ZONE] light 0..4` | brightness |

Effect options: `--light 0..4`, `--speed 0..4`, `--dir right|left|up|down`, `--color RRGGBB[,RRGGBB...]`,
`--multi` / `--no-multi`, `--text TEXT` (Alphabet).

```bash
uwccctl kb effect wave --speed 3 --multi
uwccctl kb effect single --color 00A0FF --light 2
uwccctl kb fx rain density=4 color_count=2 colors=5080FF,FFFFFF
uwccctl kb fx-config transition=ripple_center bar=battery
```

BetterRGB effects: see [LIGHTING.md](LIGHTING.md).

Control Center 3.0 / Clevo (experimental): `uwccctl clevo …` — see [CLEVO.md](CLEVO.md).

## Switches and automation

`uwccctl get [KEY]`, `uwccctl set KEY VALUE` (booleans: `on` / `off`).

| Keys | Values |
|---|---|
| `winkey_lock` `fn_lock` `usb_charger` `touchpad_toggle` `touchpad_enabled` `ac_recovery` `dgpu_direct` `bluetooth` `wifi` `webcam` `osd` `lc_hwoc` `kb_picture_modes` `tcc_extended` `history_record` `update_check` `debug` `mem_oc` `super_performance` | on / off |
| `kb_timeout` | seconds 0..3600, 0 = never |
| `alerts` `overheat_boost` `kb_off_on_battery` `ppd_sync` `ppd_follow` | on / off |
| `ppd_modes` | the system power profile → the laptop's mode, e.g. `power-saver=office,balanced=keep,performance=turbo` |
| `cpu_alert` `gpu_alert` | 60..105 °C |
| `mode_on_ac` | `keep`, `previous` or a mode |
| `mode_on_battery` | `keep` or a mode |
| `lightbar_trigger` | any value: toggles the light bar like the hotkey |
| `lang` | `en` / `ru` |
| `fan_manager` | `auto` (by project), `cml`, `std`; the service restarts |

App binding: `apps`, `apps add PROCESS MODE`, `apps remove PROCESS`, `apps enable|disable PROCESS`.

Automatic profile switching (power / temperature / load): `rules` (list and state), `rules export FILE`,
`rules import FILE` (JSON, replaces the rules), `rules enable N` / `disable N` / `clear` — see `uwccctl help rules`.

## Liquid cooler

| Command | |
|---|---|
| `lc [status]` / `lc scan` | state / find coolers |
| `lc connect ADDR` / `lc disconnect [--forget]` | connect and remember / disconnect |
| `lc mode auto\|laptop\|ec\|manual\|high\|medium\|low\|off` | mode |
| `lc manual FAN PUMP` | fan 0..100 %, pump 7/8/11/12 V (0 = off) |
| `lc curve [KEY]` | show the curves; KEY `common` (Automatic, and Follow the laptop by default) or `office` `gaming` `turbo` `custom` |
| `lc curve KEY fan T:D ... [pump T:V ...]` | set a curve: fan 2..17 points (°C:%), pump 1..4 steps (from °C:V, 7/8/11 V: e.g. `pump 0:7 50:8 70:11`); the pump is stopped by `lc idle` (the Off point) |
| `lc curve KEY flat FAN [PUMP]` / `lc curve MODE off` | a flat curve / the mode uses the common curve |
| `lc profile [list\|apply ID\|save ID\|copy NAME\|remove ID\|rename ID NAME]` | cooler profiles (built-in: default, quiet, balanced, performance) |
| `lc profile export ID [FILE]` / `lc profile import FILE [NAME]` | a cooler profile as a JSON file (`{"name", "curves"}`); an import is added as an own profile |
| `lc tiers BELOW:FAN:PUMP ...` | old tier form (1.6.7), becomes the common curve |
| `lc pump-limits 7,8,11,12 --accept-risks` / `lc pump-limits off` | own pump voltages (of 7/8/11/12 V) / back to 7–11 V |
| `lc set KEY VALUE` | `temp_source max\|cpu\|gpu`, `delay_up`/`delay_down` 0..300 s, `smooth` `notify_flow` `flow_guard` `boost_fan` `boost_pump` on/off |
| `lc idle on\|off [off_below= off_after= on_above= on_after= min_run=]` | stop the pump when cool |
| `lc rgb RRGGBB [MODE]` / `lc rgb off` | static, breathe, rainbow, breathe_rainbow, spiral, rotating_rainbow, color_wave |
| `lc prime [stop]` / `lc suspend` | filling cycle (~68 s) / sleep |

## Service

| Command | |
|---|---|
| `export fans\|all [FILE]` / `import FILE [fans,profiles,settings] [--force]` | backup / restore |
| `report [FILE] [--private serial,uuid,mac,names,apps] [--sections LIST] [--full]` | diagnostic zip |
| `lang en\|ru` / `debug [on\|off]` | language / verbose log |
| `version` / `update [check\|install]` | version / new release (install: Windows) |
| `restart` / `resume` | restart the service / re-apply settings |
| `lighting` / `nvram` / `ec read ADDR` | diagnostics |
| `driver` | EC access path, OEM driver, WMI functions (Windows) |
| `driver use auto\|oem\|wmi [--accept-risks]` | OEM driver + WMI (default) / OEM only / WMI only (open, not recommended, beta) |
| `driver config export\|import FILE` / `driver config reset` / `driver test` | WMI settings `ec_wmi.json` ([EC/WMI-config.md](EC/WMI-config.md)), quick test |
| `driver unlock [MIN]` / `driver lock` | open the EC Manager settings for the window (administrator / sudo) |
| `driver monitor oem\|wmi\|all on\|off` | monitoring through an EC path / all monitoring |
| `driver platform [export\|import FILE\|reset\|apply-draft]` | platform profile ([EC/Platforms.md](EC/Platforms.md)) |
| `driver selfcheck [1\|2] [--export FILE]` | self-check: read only / with writes (administrator, AC power) |
| `ec …` | same as `driver …` (EC Manager); `ec read ADDR` reads one register |
| `ec fetch-driver` / `ec check-driver` / `ec install-driver [--accept-risks]` | OEM driver: copy from the Windows driver store, check, install ([EC/OEM-driver.md](EC/OEM-driver.md)) |
| `driver-verify DIR [--json]` | check any driver package without the service (exit 0 / 10 / 11 / 12) |
| `ec-direct read ADDR [N]` / `ec-direct dump BASE` | EC without the service (root) |
| `release` | give fan control back to the EC (root, uninstall) |
