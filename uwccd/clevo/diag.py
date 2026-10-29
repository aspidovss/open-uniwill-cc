"""Control Center 3.0 / Clevo — diagnostics for the general diagnostic report (section "clevo", read only).

Collected on every laptop, Clevo or not, so a report tells why the module did or did not find an interface:
    module   what uwccd/clevo found (transport, capability words, fan buffers, EC version, saved state)
    system   DMI vendor / board, ACPI device CLV0001, the Clevo WMI GUIDs
    Windows  Control Center 3 (Store packages), the CC3 driver and its device interface, services, root\\WMI classes
    Linux    CLV0001 in sysfs, WMI devices ABBC0F6x, loaded modules (uwcc, tuxedo clevo_acpi / clevo_wmi)
Nothing here sends a DCHU command that changes anything.
"""
import glob
import os
import re
import sys

WMI_GUIDS = ("ABBC0F6D-8EA1-11D1-00A0-C90629100000",      # Clevo DCHU methods (older firmware)
             "ABBC0F6B-8EA1-11D1-00A0-C90629100000")      # Clevo hot-key events
CC3_STORE_ID = "9N6WG0G8B041"                             # Control Center 3.0 in the Microsoft Store


def _readf(p):
    try:
        with open(p, errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None


def _linux():
    devs = []
    for p in sorted(glob.glob("/sys/bus/acpi/devices/CLV0001:*")):
        devs.append({"device": os.path.basename(p), "path": _readf(os.path.join(p, "path")),
                     "status": _readf(os.path.join(p, "status")),
                     "driver": os.path.basename(os.path.realpath(os.path.join(p, "physical_node", "driver")))
                     if os.path.exists(os.path.join(p, "physical_node", "driver")) else None})
    wmi = []
    for p in sorted(glob.glob("/sys/bus/wmi/devices/*")):
        n = os.path.basename(p)
        if n.upper().startswith("ABBC0F6"):
            drv = os.path.join(p, "driver")
            wmi.append({"guid": n, "driver": os.path.basename(os.path.realpath(drv)) if os.path.exists(drv) else None})
    mods = [ln.split()[0] for ln in (_readf("/proc/modules") or "").splitlines()
            if re.match(r"(uwcc|clevo|tuxedo|acpi_call)", ln)]
    return {"acpi_clv0001": devs, "wmi": wmi, "modules": mods, "dev_uwcc": os.path.exists("/dev/uwcc")}


def _windows():
    from ..report_oem import _ps_json
    flt = r"$_.DeviceID -match 'CLV0001' -or $_.Name -match 'Clevo|DCHU|Insyde' -or $_.Manufacturer -match 'Clevo|Insyde'"
    out = {
        "store_packages": _ps_json("Get-AppxPackage -AllUsers | Where-Object { $_.Name -match 'ControlCenter|Clevo' "
                                   "-or $_.Publisher -match 'Clevo' } | Select-Object Name, Version, Publisher, "
                                   "PackageFamilyName, InstallLocation"),
        "devices": _ps_json(f"Get-CimInstance Win32_PnPEntity | Where-Object {{ {flt} }} | "
                            "Select-Object Name, DeviceID, PNPClass, Status, ConfigManagerErrorCode"),
        "drivers": _ps_json(r"Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceID -match 'CLV0001' "
                            r"-or $_.DeviceName -match 'Clevo|DCHU|Insyde' -or $_.Manufacturer -match 'Clevo|Insyde' } | "
                            "Select-Object DeviceName, DeviceID, DriverVersion, DriverDate, DriverProviderName, InfName, "
                            "IsSigned, Signer"),
        "services": _ps_json("Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'Clevo|DCHU|Insyde|ControlCenter' "
                             "-or $_.DisplayName -match 'Clevo|DCHU|Insyde|Control Center' } | "
                             "Select-Object Name, DisplayName, State, StartMode, PathName"),
        "wmi_classes": _ps_json("Get-CimClass -Namespace root\\WMI | Where-Object { $_.CimClassName -match 'CLEVO' } | "
                                "ForEach-Object { [pscustomobject]@{ class = $_.CimClassName; "
                                "methods = @($_.CimClassMethods | ForEach-Object Name) } }"),
    }
    try:
        from .transport import WinDchu
        d = WinDchu()
        out["cc3_driver_interface"] = d.path
        d.close()
    except Exception as e:  # noqa: BLE001
        out["cc3_driver_interface"] = f"not present: {e}"
    return out


def collect(svc=None):
    from ..hw import dmi
    cl = getattr(svc, "clevo", None)
    r = {"module": cl.diagnostics() if cl else {"present": False, "reason": "module not started"},
         "dmi": {k: dmi(k) for k in ("sys_vendor", "product_name", "board_vendor", "board_name", "bios_vendor",
                                     "bios_version")},
         "store_id": CC3_STORE_ID}
    try:
        r.update(_windows() if sys.platform == "win32" else _linux())
    except Exception as e:  # noqa: BLE001
        r["probe_error"] = str(e)
    if cl and cl.present:
        try:
            r["module"]["fans"] = cl.fans()
        except Exception as e:  # noqa: BLE001
            r["module"]["fans"] = f"error: {e}"
    r["verdict"] = verdict(r)
    return r


def verdict(r):
    """One line for report.txt: what the module found and, if nothing, the most likely reason."""
    m = r.get("module") or {}
    if m.get("present"):
        return (f"interface found via {m.get('transport')}; commands {'allowed' if m.get('writes') else 'off'}"
                f"; EC {m.get('ec_version') or '?'}")
    hints = []
    if r.get("acpi_clv0001"):
        hints.append("ACPI CLV0001 present" + ("" if "uwcc" in (r.get("modules") or []) else ", but the uwcc module is not loaded"))
    if any(w["guid"].upper().startswith("ABBC0F6D") for w in r.get("wmi") or []):
        hints.append("Clevo WMI ABBC0F6D present")
    if r.get("store_packages"):
        hints.append("Control Center 3 app installed")
    dif = str(r.get("cc3_driver_interface") or "")
    if dif and not dif.startswith("not present"):
        hints.append("CC3 driver interface present")
    vend = " ".join(str(v) for v in (r.get("dmi") or {}).values()).lower()
    if "clevo" in vend or "notebook" in vend:
        hints.append("DMI looks like a Clevo chassis")
    return "not found (" + (m.get("reason") or "-") + ")" + (": " + "; ".join(hints) if hints else "")
