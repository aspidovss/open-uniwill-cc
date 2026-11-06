# MSI Afterburner (experimental)

**English** · [Русский](AFTERBURNER.ru.md)

Since 1.7.1 every mode of the laptop can switch a profile of **MSI Afterburner** (Windows). The overclock or undervolt
of the graphics card stays in Afterburner: you set it up there as usual and save it into its profile slots **1–5**.
This program only tells Afterburner which slot to apply when the mode changes — for example an undervolt in Office
and an overclock in Turbo.

It works the same on Uniwill, Control Center 3.0 / Clevo and Leishen / Thunderobot laptops: the mode numbers are the
same as in the automation rules.

## How to use it

1. In MSI Afterburner set the clocks / curve you want and save them with *Save* into a profile slot 1–5.
2. Open *Mode selection* → card **MSI Afterburner**: choose a profile for every mode. On Uniwill laptops whose modes
   have presets (Office 1 / 2, Gaming 1 / 2, Turbo 1 / 2, Custom 1–5) every preset has its own row: Turbo 1 can
   switch on profile 3 and Turbo 2 profile 4. *Do not change* (the default) leaves Afterburner as it is. The row
   running now is marked with a dot.
3. Switch the mode — in the window, the tray, with the Fn mode key, a rule or by going on battery: the profile of the
   new mode is applied.

*Apply now* (1–5) on the card and the tray menu *MSI Afterburner → Profile N* apply a slot by hand.

## Default (stock settings)

Afterburner's command line has no "reset" command, so the stock clocks live in a slot too: in Afterburner press
**Reset**, then **Save** into a slot (for example 1), and choose that slot as **Default profile (stock settings)** on
the card. Then:

- the **Default** button (and the tray item *Default*) applies it;
- **Default** in the list of a mode or preset follows that slot — change the Default slot once and every mode set to
  *Default* follows;
- **Restore default settings** at the bottom of *Mode selection* also clears the Afterburner choices of all modes and
  presets (back to *do not change*); the Default slot itself stays.

## When the profile is applied

- the mode or its preset changes, whatever changed it (the window, the tray, the automation rules, the Fn mode key,
  AC / battery);
- the service starts (after a restart of Windows: the profile of the current mode);
- Afterburner starts later than the service (its own start-up profile would win otherwise; ours follows a few seconds
  later).

The program does not know which profile Afterburner uses now: it shows the last one it applied. A profile chosen in
Afterburner itself stays until the next mode change.

## Settings

| Setting | Default | |
|---|---|---|
| *Switch Afterburner profiles with the mode* | on | off: nothing is sent to Afterburner |
| *Default profile (stock settings)* | not set | the slot saved after Reset in Afterburner |
| profile of every mode / preset | *do not change* | *Default* or slot 1–5 |
| *Start Afterburner if it is not running* | on | the command starts a closed Afterburner and applies the slot; off: the slot is applied when Afterburner runs |

## How it works

MSI Afterburner has a documented command line: `MSIAfterburner.exe -Profile1` … `-Profile5`. A running Afterburner
takes the command over and applies the slot; a closed one starts and applies it. Nothing of Afterburner is used or
shipped; it is found through its uninstall entry in the registry or in `Program Files (x86)\MSI Afterburner`.

Afterburner runs with administrator rights, so starting the command from a normal program would show a UAC prompt each
time. The service (LocalSystem) therefore starts it in the session of the signed-in user with that user's full token:
no prompt, and the command reaches the Afterburner window of that session. The user must be an administrator of the
computer (Afterburner needs it anyway). If nobody is signed in yet, the slot is applied as soon as somebody is.

**Experimental:** checked with MSI Afterburner 4.6.6 (the command line); the start without a prompt with UAC on still
needs reports.

## Command line

```bash
uwccctl afterburner                      # found, running, the profile of every mode
uwccctl afterburner 3                    # apply profile 3 now
uwccctl afterburner mode turbo 3         # Turbo -> profile 3 (Clevo / Leishen: their mode names)
uwccctl afterburner mode turbo.2 4       # Turbo, preset 2 -> profile 4 (wins over the mode's own)
uwccctl afterburner mode office keep     # Office: do not change
uwccctl afterburner default 1            # slot 1 holds the stock settings
uwccctl afterburner default              # apply it now
uwccctl afterburner mode office default  # Office -> the Default slot
uwccctl afterburner off                  # do not switch profiles with the mode
uwccctl afterburner launch off           # do not start a closed Afterburner
```
