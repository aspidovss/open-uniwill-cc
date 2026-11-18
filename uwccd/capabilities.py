"""Capability registry (1.8.0.0; reasons and unlocking in 1.8.2.0).

One explicit answer to "what does this laptop have?", built from the EC, the platform profile, the service modules
and the managers. It is part of `/api/state` ("capabilities"), shown by `uwccctl caps` and on the Information page;
the window and the tray read feature availability from here instead of piecing it together from scattered fields,
and grey out what is not available.

Shape: {name: {"available": bool, "source": str, "detail": str?, "reason": str?, "unlock": {...}?, "lock": {...}?}}.

Sources:
  ec       — the EC capability bits / registers of this laptop
  profile  — the platform profile (uwccd/platforms/*.json or your own)
  driver   — depends on the access path (OEM driver / kernel module vs WMI)
  os       — provided by the operating system / another program
  user     — turned on by the user over the profile (unlocked)
  none     — the hardware or its prerequisite is absent

Reasons (only on unavailable capabilities; the window translates them):
  no_hardware      the laptop does not have it — nothing to unlock
  no_fan_control   the EC does not report fan control (RamFan 1.5)
  module_off       the service module is off (Switches -> Service modules)
  wmi_feature_off  the platform profile keeps this off on the WMI path (not confirmed on this project)
  writes_off       experimental platform (Clevo / Leishen): commands not allowed yet
  wmi_consent      the WMI warning has not been accepted (EC Manager)
  no_driver        no EC access at all (Windows without the OEM driver and without WMI)
  not_installed    the outside program is not installed
  locked           deliberately not available on this path (e.g. PWUP without the OEM driver)
  no_custom        the fan manager of this platform has no Custom mode (only the std manager has it)
  no_events        no hotkey event source (Linux: the kernel module; Windows: the OEM driver), the keys are polled
  modes_only       this laptop has the battery protection modes, not a custom charge limit (kernel uniwill-laptop)
  limit_only       this laptop has the custom charge limit, not the protection modes (kernel uniwill-laptop)

"unlock" says how the user can turn the capability on: {"type": "module"|"wmi_feature"|"consent"|"page",
"key": ..., "risk": bool, "restart": bool}. risk=true means the window must show the warning first
(`POST /api/unlock` performs it and records it in the settings under "unlocks" — reports carry that list).
"lock" is the reverse action on a capability the user unlocked earlier.
"""


def _cap(available, source, detail="", reason=None, unlock=None, lock=None):
    d = {"available": bool(available), "source": source}
    if detail:
        d["detail"] = detail
    if not available and reason:
        d["reason"] = reason
    if not available and unlock:
        d["unlock"] = unlock
    if available and lock:
        d["lock"] = lock
    return d


def _mod_off(mods, name):
    m = mods.get(name)
    return bool(m) and m.get("available") and not m.get("enabled")


def capabilities(svc):
    pf, caps = svc.pf, {}
    ec_path = (svc.ec_info or {}).get("active")
    wmi = ec_path == "wmi"
    alt = getattr(svc, "alt", None)
    mods = {m["name"]: m for m in svc.modules.status()}

    feats = factory_feats = {}
    if wmi:
        try:
            from . import ecaccess
            feats = (ecaccess.config(pf.project_raw) or {}).get("features") or {}
            factory_feats = (ecaccess.factory(pf.project_raw) or {}).get("features") or {}
        except Exception:  # noqa: BLE001
            feats = factory_feats = {}

    def ec_cap(ok, detail="", feat=None, unlockable=True):
        """An EC-backed capability: on the WMI path the profile's feature switch gates it (1.8.2.0)."""
        if not (ok and feat and wmi):
            return _cap(ok, "ec", detail)
        state = feats.get(feat, "off")
        if state == "off":
            return _cap(False, "profile", detail, reason="wmi_feature_off",
                        unlock={"type": "wmi_feature", "key": feat, "risk": True, "restart": True} if unlockable else None)
        if state == "slow":
            detail = (detail + " · " if detail else "") + "slow with WMI"
        if factory_feats.get(feat, "off") == "off":            # profile said off, the user turned it on
            return _cap(True, "user", (detail + " · " if detail else "") + "unlocked by the user",
                        lock={"type": "wmi_feature", "key": feat, "restart": True})
        return _cap(True, "ec", detail)

    def module_gate(cap, name, restart=False):
        """A capability whose service module is off wins over everything else."""
        if _mod_off(mods, name):
            return _cap(False, "none", "", reason="module_off",
                        unlock={"type": "module", "key": name, "risk": False, "restart": restart})
        return cap

    # modes and fans
    if alt is not None:                                        # Clevo / Leishen: one consent for all commands
        allowed = alt.writes_allowed()
        consent = {"type": "consent", "key": f"{alt.kind}_writes", "risk": True, "restart": False}
        alt_cap = (_cap(True, "driver", alt.kind, lock={**consent, "risk": False}) if allowed
                   else _cap(False, "driver", alt.kind, reason="writes_off", unlock=consent))
        caps["modes"] = caps["fan_boost"] = caps["fan_tables"] = alt_cap
        caps["turbo_mode"] = _cap(False, "none", reason="no_hardware")
        caps["custom_mode"] = _cap(False, "none", reason="no_hardware")
    else:
        fc = svc.fan_control
        nofc = "" if fc else "no RamFan 1.5 (0x78E bit6)"
        caps["modes"] = ec_cap(fc, nofc, feat="modes") if fc else _cap(False, "ec", nofc, reason="no_fan_control")
        caps["fan_boost"] = ec_cap(fc, feat="fan_boost") if fc else _cap(False, "ec", reason="no_fan_control")
        caps["fan_tables"] = ec_cap(fc, feat="fan_tables") if fc else _cap(False, "ec", reason="no_fan_control")
        caps["turbo_mode"] = ec_cap(pf.turbo_support and fc, feat="modes") if pf.turbo_support and fc \
            else _cap(False, "ec", reason="no_fan_control" if not fc else "no_hardware")
        std = getattr(svc.power, "manager", "") == "std"
        caps["custom_mode"] = ec_cap(fc and std, feat="modes") if fc and std \
            else _cap(False, "ec", reason="no_fan_control" if not fc else "no_custom")

    # power
    lim = getattr(svc.power, "limits", None) or {}
    src = lim.get("source") or ("profile" if wmi else "firmware")
    pl = ec_cap(svc.fan_control, {"firmware": "from the firmware table SMRW",
                                  "profile": "from the platform profile"}.get(src, src) if lim or wmi else "",
                feat="power_limits")
    if pl["available"] and not wmi:
        pl["source"] = "driver"
    caps["power_limits"] = pl
    caps["gpu_power"] = ec_cap(svc.fan_control and pf.nv_gpu, "cTGP / Dynamic Boost", feat="gpu_power") \
        if pf.nv_gpu else _cap(False, "none", reason="no_hardware")
    hwoc = getattr(svc, "hwoc", None)
    if bool(hwoc) and hwoc.supported():
        caps["liquid_overclock"] = _cap(True, "driver", "PWUP")
    else:
        caps["liquid_overclock"] = _cap(False, "driver" if wmi else "none", "PWUP",
                                        reason="locked" if wmi else "no_hardware")   # PWUP: OEM driver only

    # battery and switches
    # Uniwill boards have either the charge limit or the protection modes; the kernel driver knows which (1.8.2.2)
    kk = svc.battery.kernel_kind() if getattr(svc, "battery", None) else None
    caps["battery_limits"] = ec_cap(True, feat="battery") if kk != "modes" else \
        _cap(False, "os", "uniwill-laptop: charge_types only", reason="modes_only")
    caps["battery_modes"] = ec_cap(True, feat="battery") if kk != "limit" else \
        _cap(False, "os", "uniwill-laptop: charge_control_end_threshold only", reason="limit_only")
    caps["switches"] = ec_cap(True, feat="switches")

    # lighting (module "lighting" needs a service restart to start again)
    kb = svc.keyboard
    caps["keyboard_backlight"] = module_gate(
        _cap(kb.kind not in (None, "none"), "ec", kb.kind or "", reason="no_hardware"), "lighting", restart=True)
    caps["keyboard_rgb"] = module_gate(
        _cap(kb.kind == "rgb", "ec", reason="no_hardware"), "lighting", restart=True)
    caps["lightbar"] = module_gate(
        ec_cap(pf.rgb_lightbar, feat="lightbar_ec") if pf.rgb_lightbar else _cap(False, "none", reason="no_hardware"),
        "lighting", restart=True)

    # devices and integrations
    caps["liquid_cooler"] = module_gate(
        _cap(svc.liquid.available, "os" if svc.liquid.available else "none", svc.liquid.reason or "",
             reason=None if svc.liquid.available else "no_hardware"), "liquid")
    ab = svc.afterburner.status()
    caps["afterburner"] = module_gate(
        _cap(ab.get("available") and ab.get("found"), "os",
             ab.get("version") or ("not installed" if ab.get("available") else "Windows only"),
             reason="not_installed" if ab.get("available") else "no_hardware"), "afterburner")
    caps["automation"] = module_gate(_cap(True, "os"), "automation")
    caps["clevo"] = _cap(svc.clevo.present, "driver", reason="no_hardware")
    caps["leishen"] = _cap(svc.leishen.present, "driver", reason="no_hardware")

    # service paths
    caps["hotkeys"] = _cap(any(t.name == "hotkeys" and getattr(t, "available", False) for t in svc.threads),
                           "driver", "events" if not wmi else "polling", reason="no_events")
    if ec_path in ("none", None):
        reason = (svc.ec_info or {}).get("reason") or "no_driver"
        caps["ec_write"] = _cap(False, "none", reason=reason if reason in ("wmi_consent", "oem_missing") else "no_driver",
                                unlock={"type": "page", "key": "driver", "risk": False, "restart": False})
    else:
        caps["ec_write"] = _cap(True, "driver", ec_path)
    return caps
