# Leishen / Thunderobot (experimental)

**English** · [Русский](LEISHEN.ru.md)

Some Thunderobot laptops (for example the **R16**, board NLY, BIOS TP162) are built by Quanta and come with
**Leishen ControlCenter 3.x**. They have neither the Uniwill embedded-controller interface of the rest of this program
nor the Clevo DCHU interface (`CLV0001`), so the Uniwill functions do not work on them. The separate module `uwccd/leishen`
talks to their firmware instead. It is **experimental**: it was written from the firmware's ACPI tables and from how
Leishen ControlCenter 3.0.0.18 uses them (interoperability analysis, no vendor code or files). Since 1.7.0 it works on
the **usual pages** of the window — *Mode selection* (power mode and the module's switches), *Fan settings*,
*Keyboard backlight*, *Switches* (Windows key, touchpad), *Information* — and with the tray menu, the automation rules
and `uwccctl mode` (0 Office, 1 Gaming, 2 High performance); the badge *LEISHEN · EXPERIMENTAL* marks it like the WMI
driver.

**Checked on a Thunderobot R16 (1.6.11_Leishen_dev):** sensors, power modes, own fan speeds, keyboard light,
Windows key, touchpad and the mode key work.

## How it works

The firmware has one 32-byte WMI data block, GUID `644C5791-B7B0-4123-A90B-E93876E0DAAD` (WMI class `RW_GMWMI` in
`root\WMI`, device `GWMI`). Writing the block runs a command in the ACPI method `WSAA`, reading it back (`WQAA`) gives the
answer in the same layout:

| Bytes | Field | |
|---|---|---|
| 0–1 | `a0` | `0xFA00` read, `0xFB00` write; answer `0x1000` = command not known |
| 2–3 | `a1` | function |
| 4–23 | `a2`…`a6` | values (32 bit each) |

| Function | Read (`0xFA00`) | Write (`0xFB00`) |
|---|---|---|
| `0x200` | `a2` CPU °C, `a3` GPU °C, `a4` / `a5` fan 1 / 2 rpm, `a6` keyboard light level | `a2` 0: `a6` 1 = Windows key locked |
| `0x201` | `a2` `0x34` RGB keyboard, `0x35` single colour | — |
| `0x202` | hardware flags | `a2` 0 / 1 touchpad off / on |
| `0x205` | `a2` factory fan table (4 = NLY) | `a2` / `a3` / `a4` fan 1 / 2 / 3 speed, %; `0xFF` = that fan automatic |
| `0x206` | `a2` "control program present" bit | the same bit (the firmware writes `a2`, then `a3`) |
| `0x207` | `a2` GPU °C, `a3` fan 3 rpm | — |
| `0x300` | `a2` power mode: 0 High performance, 1 Gaming, 2 Office | the same; the firmware also sets the NVIDIA power limits |
| `0x100` | — | keyboard light: `a2` zone, `a3` = effect << 28, level << 24, RRGGBB |

Every read of `0x200` also sets the "control program present" bit in the controller — Leishen ControlCenter reads it
every few seconds too. So *automatic* fans are `0x206` = 0 **and** `0x205` = `0xFF` for every fan: the bit alone comes
back with the next read and the last speeds stay.

- **Windows:** the WMI driver built into Windows; no extra driver.
- **Linux:** `acpi_call` on the device's `WSAA` / `WQAA` (`sudo modprobe acpi_call`).

## What the module does

| | |
|---|---|
| **Monitor** | CPU and GPU temperature and the speed of 2 or 3 fans from the firmware also on the Monitor page and in the history |
| **Power mode** | High performance / Gaming / Office, read back from the firmware. Office also limits the graphics card (NVIDIA power limits of the firmware) and stops the system fan. On battery the mode is Office, like in Leishen ControlCenter; the mode chosen on AC comes back with the charger (*Office on battery*, on by default) |
| **Fans** | *Automatic* (the controller), *Fixed speed* or a *Curve* for the processor and graphics card fans, run by the service every 2 s like Leishen ControlCenter (factory curve of the NLY: 30 % up to 70 °C, then 50 / 60 / 70 / 100 %). Leishen ControlCenter does not go below 30 % (≈1450 rpm, system fan ≈1800); here 20 % works (≈1000 rpm, system fan ≈1250), lower only after a question. The system fan stays automatic unless a fixed speed is given for it (a fixed speed made it surge between 1000 and 2000 rpm in Office mode). When the service stops, the fans go back to automatic |
| **Keyboard** | Windows key lock, touchpad on / off; on RGB keyboards zone, effect (static, breathing, colour cycle, ambilight), level and colour. On a single-colour keyboard the firmware's light command is not sent (it waits for an RGB controller); the level is shown and changed with the Fn keys |
| **Mode key** | (Windows, off by default) Fn mode key switches Office → Gaming → High performance, like Leishen ControlCenter does. Turn it on only when Leishen ControlCenter is closed |

Nothing is sent until **Allow commands** is on (the banner at the top of the window, the platform window,
*Mode selection → Allow commands* or `uwccctl leishen writes on`).
The firmware does not report the Windows key, the touchpad or the light colours: the page shows the values last set
there. Saved settings (mode, fixed fan speeds, Windows key) are sent again when the service starts (can be turned off).

Not done: the display mode switch (`0x203`, needs a restart), refresh-rate switch (`0x204`), camera and adapter events.

## Command line

```bash
uwccctl leishen                         # status
uwccctl leishen writes on               # allow commands
uwccctl leishen mode office             # performance | gaming | office
uwccctl leishen fan fixed 50 50         # CPU GPU [SYS|auto] %, below 20 % with --low
uwccctl leishen fan curve 30:30 70:50 80:60 90:70 100:100
uwccctl leishen fan auto
uwccctl leishen winkey lock             # lock | free
uwccctl leishen touchpad off            # on | off
uwccctl leishen light all static 2 00A0FF   # RGB keyboards: ZONE EFFECT LEVEL(0-2) RRGGBB
uwccctl leishen hotkey on               # Windows: the mode key
uwccctl leishen battery-office off      # keep the chosen mode on battery
```

## Testing

1. Close Leishen ControlCenter (tray) — both programs would send commands.
2. Open *Fan settings*: temperatures and fan speeds should match Leishen ControlCenter.
3. Turn on *Allow commands*, try the power mode, then the fans (*Fixed speed* 60 %, then *Automatic*).
4. Make a diagnostic report (*Information → Diagnostic report*): it contains the raw answers of the firmware.
