"""Diagnostic report: everything needed to add support for another laptop or to understand a bug report.

A zip with report.json (all data), report.txt (short readable summary) and the service log. Read-only: the EC
areas the program itself uses are read, nothing is written to the EC, NVRAM or HID devices.

Private details are left out unless the user ticks them (Information → Diagnostic report):
  serial — serial numbers of the laptop / board;  uuid — system UUID;  mac — MAC addresses (network, cooler);
  names  — computer name and user names in paths;  apps — programs from App binding and processes on the GPU.
"""
import glob
import io
import json
import logging
import os
import platform as platform_mod
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile

from . import CONTACT, __version__, build_info, version_string
from . import regs as R

log = logging.getLogger("uwccd.report")

SECTIONS = ("system", "platform", "ec", "bios", "acpi", "firmware", "selfcheck", "oem_registry", "oem_software", "oem_files",
            "oem_files_full", "power", "lighting", "nvidia", "sensors", "original", "cooler", "log", "settings")
DEFAULT_SECTIONS = tuple(s for s in SECTIONS if s != "oem_files_full")      # the complete OEM folders are large
PRIVATE = ("serial", "uuid", "mac", "names", "apps")
EC_AREAS = ((0x400, 0x100), (0x700, 0x100), (0xD40, 0x10), (0xF00, 0x80))  # areas GCUService reads (0xD48: LC HWOC support)
HIDDEN = "<hidden>"
MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b")
USER_PATH_RE = re.compile(r"(?i)([A-Z]:\\{1,2}Users\\{1,2})([^\\/\"'\s]+)|(/home/)([^/\"'\s]+)")


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def _run(cmd, timeout=20):
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    flags = 0x08000000 if sys.platform == "win32" else 0         # CREATE_NO_WINDOW
    r = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout, check=False,
                       creationflags=flags)
    return (r.stdout or r.stderr or "").strip()


def _read(path, binary=False):
    try:
        with open(path, "rb" if binary else "r") as f:
            return f.read() if binary else f.read().strip()
    except OSError:
        return None


# ---------------------------------------------------------------- collectors
def system_info(svc, private):
    from .hw import dmi
    fields = ("sys_vendor", "product_name", "product_version", "product_sku", "product_family", "board_vendor",
              "board_name", "board_version", "bios_vendor", "bios_version", "bios_date", "bios_release",
              "ec_firmware_release", "chassis_type")
    out = {"program": version_string(), "version": __version__, "build": build_info(),
           "os": platform_mod.platform(), "python": sys.version.split()[0], "machine": platform_mod.machine(),
           "dmi": {f: dmi(f) for f in fields}, "cpu": getattr(svc.monitor, "cpu_model", None)}
    from .monitor import tjmax
    out["tjmax"] = _safe(tjmax)
    out["memory"] = _safe(svc.monitor.memory)
    if sys.platform == "win32":
        from .win.winplat import powershell
        _rc, txt, _e = powershell("Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + ' | ' + "
                                  "$_.PNPDeviceID + ' | ' + $_.DriverVersion }")
        out["display"] = [ln.strip() for ln in (txt or "").splitlines() if ln.strip()]
        _rc, txt, _e = powershell("(Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, "
                                  "OSArchitecture | ConvertTo-Json -Compress)")
        out["windows"] = _safe(json.loads, txt) if txt else None
        if "serial" in private or "uuid" in private:
            _rc, txt, _e = powershell("[pscustomobject]@{bios=(Get-CimInstance Win32_BIOS).SerialNumber; "
                                      "board=(Get-CimInstance Win32_BaseBoard).SerialNumber; "
                                      "uuid=(Get-CimInstance Win32_ComputerSystemProduct).UUID} | ConvertTo-Json -Compress")
            ids = _safe(json.loads, txt) if txt else {}
            if isinstance(ids, dict):
                if "serial" in private:
                    out["serial"] = {"product": ids.get("bios"), "board": ids.get("board")}
                if "uuid" in private:
                    out["uuid"] = ids.get("uuid")
    else:
        out["kernel"] = platform_mod.release()
        out["os_release"] = _read("/etc/os-release")
        out["display"] = (_run(["lspci", "-nn"]) or "").splitlines()
        out["display"] = [ln for ln in out["display"] if re.search(r"VGA|3D|Display", ln)]
        out["modules"] = [ln.split()[0] for ln in (_read("/proc/modules") or "").splitlines()
                          if re.match(r"(uwcc|acpi_call|nvidia|i915|amdgpu|xe|tuxedo|clevo|uniwill)", ln)]
        if "serial" in private:
            out["serial"] = {"product": _read("/sys/class/dmi/id/product_serial"),
                             "board": _read("/sys/class/dmi/id/board_serial")}
        if "uuid" in private:
            out["uuid"] = _read("/sys/class/dmi/id/product_uuid")
    if "names" in private:
        out["hostname"] = socket.gethostname()
    if "mac" in private:
        out["mac"] = _macs()
    return out


def _macs():
    if sys.platform == "win32":
        from .win.winplat import powershell
        _rc, txt, _e = powershell("Get-NetAdapter | ForEach-Object { $_.Name + ' ' + $_.MacAddress }")
        return [ln.strip() for ln in (txt or "").splitlines() if ln.strip()]
    return {os.path.basename(p): _read(os.path.join(p, "address")) for p in glob.glob("/sys/class/net/*")
            if os.path.basename(p) != "lo"}


def platform_info(svc):
    p = svc.power if getattr(svc, "fan_control", False) else None
    out = {"platform": {k: (f"0x{v:X}" if k in ("project_id", "project_raw") and isinstance(v, int) else v)
                        for k, v in svc.pf.as_dict().items()},
           "fan_control": getattr(svc, "fan_control", None), "mock": getattr(svc, "mock", None),
           "ec_backend": type(svc.ec).__name__,
           "threads": sorted(t.name for t in getattr(svc, "threads", []))}
    if p is not None:
        out["fan_manager"] = getattr(p, "manager", None)
        out["mode"] = _safe(lambda: p.option.get("OperatingMode"))
        st = _safe(p.status)
        out["power_status"] = st
        out["tables"] = _safe(lambda: p.tables.tables)
        out["profiles"] = _safe(lambda: p.profiles)
    return out


def ec_dump(svc):
    out, named = {}, {}
    for base, size in EC_AREAS:
        vals = []
        for a in range(base, base + size):
            try:
                vals.append(svc.ec.read(a))
            except Exception:  # noqa: BLE001
                vals.append(None)
        rows = {}
        for i in range(0, size, 16):
            row = vals[i:i + 16]
            rows[f"{base + i:04X}"] = " ".join("--" if v is None else f"{v:02X}" for v in row)
        out[f"{base:04X}-{base + size - 1:04X}"] = rows
        for name, addr in vars(R).items():
            if name.isupper() and isinstance(addr, int) and base <= addr < base + size:
                v = vals[addr - base]
                named[name] = {"addr": f"0x{addr:03X}", "value": v, "hex": None if v is None else f"0x{v:02X}",
                               "bits": None if v is None else f"{v:08b}"}
    return {"dump": out, "named": dict(sorted(named.items(), key=lambda kv: kv[1]["addr"]))}


def bios_info(svc):
    out = {}
    nv = getattr(svc, "nvram", None)
    if nv is not None:
        raw = _safe(nv.read_all)
        out["uniwill_variable"] = {"fields": _safe(nv.fields),
                                   "hex": raw.hex(" ") if isinstance(raw, (bytes, bytearray)) else raw,
                                   "verified": _safe(lambda: nv.verify(svc.pf.project_id))}
    p = getattr(svc, "power", None)
    out["firmware_limits"] = _safe(lambda: (p.status() or {}).get("limits")) if p is not None else None
    return out


def lighting_info(svc):
    from .lighting import ite
    kb = getattr(svc, "keyboard", None)
    out = {"keyboard": _safe(kb.status) if kb else None, "ite_devices": _safe(ite.list_devices),
           "hid": _safe(_hid_devices)}
    return out


def _hid_devices():
    """All HID collections; report descriptors of ITE and vendor-defined ones (Linux)."""
    from .lighting import ite
    if sys.platform == "win32":
        from .win.hid import enumerate_devices
        return [{**d, "vid": f"{d.get('vid', 0):04X}", "pid": f"{d['pid']:04X}",
                 "usage_page": f"{d['usage_page']:04X}" if d.get("usage_page") is not None else None}
                for d in enumerate_devices(None, None)]
    out = []
    for hr in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        uevent = _read(os.path.join(hr, "device", "uevent")) or ""
        kv = dict(ln.split("=", 1) for ln in uevent.splitlines() if "=" in ln)
        parts = kv.get("HID_ID", "::").split(":")
        if len(parts) != 3:
            continue
        vid, pid = int(parts[1], 16), int(parts[2], 16)
        desc = _read(os.path.join(hr, "device", "report_descriptor"), binary=True) or b""
        up = ite._usage_page(desc) if desc else None
        d = {"node": "/dev/" + os.path.basename(hr), "vid": f"{vid:04X}", "pid": f"{pid:04X}", "name": kv.get("HID_NAME"),
             "usage_page": f"{up:04X}" if up else None}
        if vid == ite.VID or (up or 0) >= 0xFF00:
            d["report_descriptor"] = desc.hex(" ")
        out.append(d)
    return out


def nvidia_info(svc, private):
    if not svc.pf.nv_gpu:
        return {"present": False}
    from . import nvpowerd
    p = getattr(svc, "power", None)
    gt = getattr(p, "gputemp", None) if p is not None else None
    out = {"present": True, "monitor": _safe(svc.monitor.nvidia), "target_temperature": _safe(gt.info, True) if gt else None,
           "dynamic_boost_service": _safe(nvpowerd.status, True)}
    q = _run(["nvidia-smi", "-q"], timeout=30)
    if q:
        if "serial" not in private:
            q = re.sub(r"(?m)^(\s*Serial Number\s*:).*$", r"\1 " + HIDDEN, q)
        if "uuid" not in private:
            q = re.sub(r"(?m)^(\s*GPU UUID\s*:).*$", r"\1 " + HIDDEN, q)
        out["nvidia_smi"] = q
    if "apps" not in private and isinstance(out["monitor"], dict):
        out["monitor"] = {k: v for k, v in out["monitor"].items() if k not in ("users", "processes")}
    return out


def sensors_info(svc):
    return {"now": _safe(svc.sampler.snapshot), "last_15_min": _safe(svc.sampler.points, 900),
            "battery": _safe(svc.monitor.battery)}


def original_info():
    from . import backup
    d = backup.original_dir()
    if not d:
        return {"installed": False}
    out = {"installed": True, "dir": d, "data": _safe(backup.read_original)}
    exe = os.path.join(os.path.dirname(os.path.dirname(d)), "GCUService.exe")
    out["files"] = sorted(os.listdir(os.path.dirname(d))) if os.path.isdir(os.path.dirname(d)) else []
    if os.path.exists(exe):
        out["gcuservice_size"] = os.path.getsize(exe)
    return out


def cooler_info(svc, private):
    lc = getattr(svc, "liquid", None)
    if lc is None:
        return None
    st = _safe(lc.status)
    if "mac" not in private and isinstance(st, dict):
        st = json.loads(MAC_RE.sub("XX:XX:XX:XX:XX:XX", json.dumps(st)))
    return st


def log_tail(lines=2000):
    if sys.platform == "win32":
        from .win.winplat import data_root
        path = os.path.join(data_root(), "log", "uwccd.log")
        txt = ""
        for p in (path + ".1", path):
            t = _read(p)
            if t:
                txt += t + "\n"
        return "\n".join(txt.splitlines()[-lines:])
    out = _run(["journalctl", "-u", "uwccd", "-n", str(lines), "--no-pager", "-o", "short-iso"], timeout=30)
    return out or "(no journal: journalctl not available)"


def settings_info(svc, private):
    st = {k: v for k, v in svc.settings_store.d.items() if "token" not in k}
    if "apps" not in private:
        st.pop("app_binding", None)
    return st


# ---------------------------------------------------------------- report
def _redact(text, private, secrets_):
    if "names" not in private:
        text = USER_PATH_RE.sub(lambda m: (m.group(1) or m.group(3)) + "<user>", text)
        host = socket.gethostname()
        if host and len(host) > 2:
            text = text.replace(host, "<computer>")
    if "mac" not in private:
        text = MAC_RE.sub("XX:XX:XX:XX:XX:XX", text)
    for s in secrets_:
        if s and len(s) > 3:
            text = text.replace(s, HIDDEN)
    return text


def _secrets(private):
    """Values that must not appear anywhere in the report unless their private item is ticked."""
    out = []
    if "serial" not in private:
        out += [_read("/sys/class/dmi/id/product_serial"), _read("/sys/class/dmi/id/board_serial")]
    if "uuid" not in private:
        out.append(_read("/sys/class/dmi/id/product_uuid"))
    return [s for s in out if s and s.lower() not in ("to be filled by o.e.m.", "default string", "none", "0")]


def summary(svc):
    from .hw import dmi
    kb = (_safe(svc.keyboard.status) if getattr(svc, "keyboard", None) else {}) or {}
    dev = kb.get("device") or {}
    return {"program": version_string(), "vendor": dmi("sys_vendor"), "model": dmi("product_name"),
            "board": dmi("board_name"), "bios": f"{dmi('bios_version')} ({dmi('bios_date')})",
            "ec": dmi("ec_firmware_release"), "project": svc.pf.project_name,
            "project_id": f"0x{svc.pf.project_id:X}", "cpu": getattr(svc.monitor, "cpu_model", None),
            "os": platform_mod.platform(), "nvidia": svc.pf.nv_gpu,
            "keyboard": f"{kb.get('kind')} {dev.get('pid', '')} fw {dev.get('fw', '')}".strip(),
            "fan_control": getattr(svc, "fan_control", None), "support": getattr(svc.pf, "support", None)}


class Job:
    """One report at a time in the background: the window asks for it, polls, then downloads the ready file."""
    lock = threading.Lock()
    current = None

    def __init__(self, svc, sections, private, name=None):
        self.id = f"{int(time.time() * 1000):x}"
        self.state, self.started, self.error, self.data, self.name, self.took = "running", time.time(), None, None, name, None
        threading.Thread(target=self._run, args=(svc, sections, private), daemon=True, name="report").start()

    def _run(self, svc, sections, private):
        try:
            data, name = build(svc, sections, private)
            self.data, self.name = data, self.name or name
            self.state = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("diagnostic report")
            self.state, self.error = "error", str(e)
        self.took = round(time.time() - self.started, 1)

    def status(self):
        return {"id": self.id, "state": self.state, "error": self.error, "name": self.name,
                "size": len(self.data) if self.data else None,
                "elapsed": round((self.took if self.took is not None else time.time() - self.started), 1)}

    @classmethod
    def start(cls, svc, sections, private, name=None):
        with cls.lock:
            if cls.current is None or cls.current.state != "running":
                cls.current = cls(svc, sections, private, name)
            return cls.current


MARK = {"ok": "OK  ", "warn": "!   ", "fail": "FAIL", "skip": "-   ", "na": "-   "}


def selfcheck_info(svc):
    """Self-check stage 1 (read only) run now: the table of checks, what is not clear, the draft platform profile.
    -> (result, {"selfcheck.json": the same file as EC Manager -> Export for GitHub})"""
    sc = getattr(svc, "selfcheck", None)
    if sc is None:
        return {"error": "no self-check in this service"}, {}
    from . import version_string
    r = sc.run_now(1)
    exp = {"program": version_string(), "result": r, "draft_profile": r.get("draft"), "from": "diagnostic report"}
    return r, {"selfcheck.json": json.dumps(exp, indent=1, ensure_ascii=False, default=str)}


def selfcheck_text(r):
    """report.txt: the stage 1 table"""
    if not isinstance(r, dict):
        return []
    out = ["", "self-check, stage 1 (read only)", "-" * 31]
    if r.get("error"):
        return out + [f"error: {r['error']}"]
    out.append(f"EC path: {r.get('path')}")
    for it in r.get("items") or []:
        out.append(f"{MARK.get(it.get('status'), str(it.get('status'))[:4].ljust(4))} {str(it.get('group', '')):<10} "
                   f"{str(it.get('name', '')):<44} {str(it.get('detail', ''))[:160]}")
    if r.get("unknowns"):
        out += ["", "not clear:"] + [f"  - {u}" for u in r["unknowns"]]
    f = r.get("features")
    if isinstance(f, dict) and f:
        out += ["", "features (draft): " + ", ".join(f"{k}={v}" for k, v in f.items())]
    return out


def build(svc, sections=DEFAULT_SECTIONS, private=()):
    """-> (zip bytes, file name)."""
    sections = [s for s in sections if s in SECTIONS]
    private = [p for p in private if p in PRIVATE]
    t0 = time.time()
    data = {"format": "open-uniwill-cc-report", "program": version_string(), "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "contact": CONTACT, "sections": sections, "private_included": private, "summary": _safe(summary, svc)}
    collectors = {
        "system": lambda: system_info(svc, private), "platform": lambda: platform_info(svc),
        "ec": lambda: ec_dump(svc), "bios": lambda: bios_info(svc), "lighting": lambda: lighting_info(svc),
        "nvidia": lambda: nvidia_info(svc, private), "sensors": lambda: sensors_info(svc),
        "original": original_info, "cooler": lambda: cooler_info(svc, private),
        "settings": lambda: settings_info(svc, private),
    }
    from . import report_oem as O
    secrets_ = _secrets(private)
    extra = {}                                       # more files for the zip (ACPI tables, OEM files)

    def with_files(fn):
        def run():
            summary_, files = fn()
            extra.update(files)
            return summary_
        return run
    redact_text = lambda t: _redact(t, private, secrets_)          # noqa: E731
    collectors.update({
        "acpi": with_files(O.acpi_tables), "firmware": O.firmware_info, "oem_registry": O.oem_registry,
        "selfcheck": with_files(lambda: selfcheck_info(svc)),
        "oem_software": O.oem_software, "power": O.power_info,
        "oem_files": with_files(lambda: O.oem_files("oem_files_full" in sections, redact_text)),
    })
    if "oem_files_full" in sections and "oem_files" not in sections:
        sections.insert(sections.index("oem_files_full"), "oem_files")
    # collectors run in parallel: several of them wait for PowerShell / WMI on Windows
    from concurrent.futures import ThreadPoolExecutor
    timings = {}

    def timed(name):
        t1 = time.time()
        try:
            return _safe(collectors[name])
        finally:
            timings[name] = round(time.time() - t1, 1)
    todo = [n for n in sections if n in collectors]
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="report") as ex:
        for name, res in zip(todo, ex.map(timed, todo)):
            data[name] = res
    data["timings_s"] = timings
    if isinstance(data.get("summary"), dict):
        data["summary"]["known_board_elsewhere"] = O.board_hint(data["summary"].get("board")).get("known_elsewhere")
        reg = data.get("oem_registry")
        if isinstance(reg, dict) and reg.get("official_program"):
            data["summary"]["official_program"] = reg["official_program"]
    data["took_s"] = round(time.time() - t0, 1)
    js = _redact(json.dumps(data, indent=1, ensure_ascii=False, default=str), private, secrets_)
    s = data["summary"] if isinstance(data["summary"], dict) else {}
    txt = ["open-uniwill-cc diagnostic report", "=" * 34] + [f"{k:12} {v}" for k, v in s.items()]
    if "selfcheck" in sections:
        txt += selfcheck_text(data.get("selfcheck"))
    txt += ["", f"sections:         {', '.join(sections)}",
            f"private included: {', '.join(private) or 'none'}", "", f"Send to: {CONTACT} or GitHub issues."]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.json", js)
        z.writestr("report.txt", _redact("\n".join(txt) + "\n", private, secrets_))
        for path, blob in sorted(extra.items()):
            z.writestr(path, blob)
        if "log" in sections:
            lt = _safe(log_tail)
            z.writestr("uwccd.log", _redact(lt, private, secrets_) if isinstance(lt, str) else json.dumps(lt))
    model = re.sub(r"[^\w.-]+", "-", str(s.get("model") or s.get("project") or "laptop")).strip("-")[:40] or "laptop"
    name = f"uwcc-report-{model}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    log.info("diagnostic report: %s, %d bytes, sections %s, private %s", name, buf.tell(), sections, private)
    return buf.getvalue(), name
