"""Capability registry (1.8.0.0).

One explicit answer to "what does this laptop have?", built from the EC, the platform profile and the managers.
It is part of `/api/state` ("capabilities"), shown by `uwccctl caps` and on the Information page; the window and
the tray read feature availability from here instead of piecing it together from scattered fields.

Shape: {name: {"available": bool, "source": str, "detail": str?}}. Sources:
  ec       — the EC capability bits / registers of this laptop
  profile  — the platform profile (uwccd/platforms/*.json or your own)
  driver   — depends on the access path (OEM driver / kernel module vs WMI)
  os       — provided by the operating system / another program
  none     — the hardware or its prerequisite is absent
"""


def _cap(available, source, detail=""):
    d = {"available": bool(available), "source": source}
    if detail:
        d["detail"] = detail
    return d


def capabilities(svc):
    pf, caps = svc.pf, {}
    ec_path = (svc.ec_info or {}).get("active")
    wmi = ec_path == "wmi"
    alt = getattr(svc, "alt", None)

    # modes and fans
    caps["modes"] = (_cap(True, "ec", alt.kind) if alt is not None
                     else _cap(svc.fan_control, "ec", "" if svc.fan_control else "no RamFan 1.5 (0x78E bit6)"))
    caps["fan_boost"] = _cap(svc.fan_control or alt is not None, "ec")
    caps["fan_tables"] = _cap(svc.fan_control, "ec", "slow on the WMI path" if wmi and svc.fan_control else "")
    caps["turbo_mode"] = _cap(pf.turbo_support and svc.fan_control, "ec")
    caps["custom_mode"] = _cap(svc.fan_control and getattr(svc.power, "manager", "") == "std", "ec")

    # power
    lim = getattr(svc.power, "limits", None) or {}
    src = lim.get("source") or ("profile" if wmi else "firmware")
    caps["power_limits"] = _cap(svc.fan_control, "driver" if not wmi else "profile",
                                {"firmware": "from the firmware table SMRW", "profile": "from the platform profile"}.get(src, src)
                                if lim or wmi else "")
    caps["gpu_power"] = _cap(svc.fan_control and pf.nv_gpu, "ec", "cTGP / Dynamic Boost")
    hwoc = getattr(svc, "hwoc", None)
    caps["liquid_overclock"] = _cap(bool(hwoc) and hwoc.supported(), "driver", "PWUP")

    # battery
    caps["battery_limits"] = _cap(True, "ec")
    caps["battery_modes"] = _cap(True, "ec")

    # lighting
    kb = svc.keyboard
    caps["keyboard_backlight"] = _cap(kb.kind not in (None, "none"), "ec", kb.kind or "")
    caps["keyboard_rgb"] = _cap(kb.kind == "rgb", "ec")
    caps["lightbar"] = _cap(pf.rgb_lightbar, "ec")

    # devices and integrations
    caps["liquid_cooler"] = _cap(svc.liquid.available, "os" if svc.liquid.available else "none",
                                 svc.liquid.reason or "")
    ab = svc.afterburner.status()
    caps["afterburner"] = _cap(ab.get("available") and ab.get("found"), "os",
                               ab.get("version") or ("not installed" if ab.get("available") else "Windows only"))
    caps["clevo"] = _cap(svc.clevo.present, "driver")
    caps["leishen"] = _cap(svc.leishen.present, "driver")

    # service paths
    caps["hotkeys"] = _cap(any(t.name == "hotkeys" and getattr(t, "available", False) for t in svc.threads),
                           "driver", "events" if not wmi else "polling")
    caps["ec_write"] = _cap(ec_path not in ("none", None), "driver", ec_path or "none")
    return caps
