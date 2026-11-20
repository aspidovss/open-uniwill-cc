"""Flydigi BS laptop coolers: BS1, BS2, BS2 Pro, BS3, BS3 Pro (1.8.2.7).

The protocol, the control logic and the pairing / connection logic are a port of THRM
(https://github.com/TIANLI0/THRM, MIT License, Copyright (c) 2025 Tianli) from Go to Python. The port keeps THRM's
commands, sequences, timings and safety checks unchanged; every function names the THRM file and function it
comes from. What differs is only what Python and this service need: threads instead of goroutines, our own HID
access (hidraw on Linux, hid.dll on Windows) instead of hidapi, bleak instead of tinygo/bluetooth.

    proto.py   <- internal/deviceproto/protocol.go, commands.go; internal/types/types.go (gear presets)
    hidio.py   <- internal/device/hid_report.go (report format), device.go (enumeration), bs1_hid.go
    device.py  <- internal/device/device.go, response.go, query.go (BS2 / BS2 Pro / BS3 / BS3 Pro over HID);
                  internal/device/ble.go, bs1_hid.go (BS1 over Bluetooth LE or USB);
                  internal/device/rgb.go (lighting on / off: 0x46 with the flash-write cache)
    cooler.py  -- this service: connection loop, modes, the temperature curve (THRM defaults), automation

Pairing, as in THRM: every model is seen by a Bluetooth LE scan. BS1 is controlled directly over Bluetooth LE (or
by USB HID, VID 0x04A0 PID 0x2501). BS2 / BS2 Pro / BS3 / BS3 Pro are controlled as HID devices (VID 0x37D7): they are
paired once in the system's Bluetooth settings (or plugged in by USB); the search only reports them (1.9.0.0).

THRM's licence (MIT) is reproduced in THIRD_PARTY_LICENSES.txt.
"""
