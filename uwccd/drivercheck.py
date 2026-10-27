"""Minimal check of an OEM driver package (UWACPIDriver.inf / .sys / .cat) before it is installed, and copying it out
of the Windows driver store.

    verify(dir) -> {"level": "ok" | "warn" | "fail" | "hard", "checks": [...], "version", "known", "dir", ...}

    ok    — files present, the INF is the UWACPIDriver for ACPI\\INOU0000 (amd64), signatures valid, SHA-256 known;
    warn  — everything fine, but the SHA-256 is not in KNOWN (another version of the driver): install after confirmation;
    fail  — a signature is not valid / could not be checked: refused unless the user accepts the risk;
    hard  — files missing or the INF is for another device: refused, the driver could not work anyway.

Used by EC Manager (install button), `uwccctl ec check-driver` / `driver-verify DIR` (also without the service: the
Windows installer and install.ps1 call it), and the self-check.
"""
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys

log = logging.getLogger("uwccd.drivercheck")

IS_WIN = sys.platform == "win32"
FILES = ("uwacpidriver.inf", "uwacpidriver.sys", "uwacpidriver.cat")
HWID = "ACPI\\INOU0000"
# SHA-256 of known driver versions: (sys, cat) -> description
KNOWN = {
    ("5b4208d762dad4fec1cfc66adcea29dbb3644e917ba77944306c390b90ce2a20",
     "861344669e9cdc481b26c02c37aff04b828b41415d3ec6bf9ead05aa9dc779c4"):
        "17.53.43.609 (Control Center 5.52.49.6)",
}
LEVELS = ("ok", "warn", "fail", "hard")
EXIT = {"ok": 0, "warn": 10, "fail": 11, "hard": 12}       # exit codes of `uwccctl driver-verify`


def _files(d):
    try:
        names = os.listdir(d)
    except OSError:
        return {}
    low = {n.lower(): os.path.join(d, n) for n in names}
    return {f: low[f] for f in FILES if f in low}


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _signature(paths):
    """Authenticode status of the files (Windows): {path: {"status", "signer"}}; None when it cannot be checked."""
    if not IS_WIN:
        return None
    lst = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    ps = (f"@({lst}) | ForEach-Object {{ $s = Get-AuthenticodeSignature -LiteralPath $_; "
          "[pscustomobject]@{p=$_; s=[string]$s.Status; n=$(if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' })} } "
          "| ConvertTo-Json -Compress")
    try:
        from .win.winplat import CREATE_NO_WINDOW
        out = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                             capture_output=True, text=True, timeout=60, creationflags=CREATE_NO_WINDOW,
                             check=False).stdout.strip()
        data = json.loads(out) if out else []
        if isinstance(data, dict):
            data = [data]
        return {d["p"]: {"status": d["s"], "signer": d["n"]} for d in data}
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        log.warning("signature check: %s", e)
        return None


def _cn(subject):
    m = re.search(r"CN=([^,]+)", subject or "")
    return m.group(1).strip('"') if m else (subject or "")


def verify(d):
    checks = []
    add = lambda iid, status, detail: checks.append({"id": iid, "status": status, "detail": detail})   # noqa: E731
    files = _files(d)
    res = {"dir": d, "checks": checks, "version": None, "known": None, "level": "ok", "sha256": {}}
    missing = [f for f in FILES if f not in files]
    if missing:
        add("files", "hard", "missing: " + ", ".join(missing))
        res["level"] = "hard"
        return res
    sizes = {f: os.path.getsize(p) for f, p in files.items()}
    if not (500 <= sizes["uwacpidriver.inf"] <= 65536 and 4096 <= sizes["uwacpidriver.sys"] <= 4 << 20
            and 512 <= sizes["uwacpidriver.cat"] <= 1 << 20):
        add("files", "hard", "unexpected sizes: " + ", ".join(f"{k} {v} B" for k, v in sizes.items()))
        res["level"] = "hard"
        return res
    add("files", "ok", ", ".join(f"{k} {v} B" for k, v in sizes.items()))
    with open(files["uwacpidriver.inf"], "rb") as f:
        raw = f.read()
    inf = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("latin-1")
    up = inf.upper()
    ok_dev = HWID in up and "ADDSERVICE" in up and "UWACPIDRIVER" in up
    ok_arch = "NTAMD64" in up
    m = re.search(r"DriverVer\s*=\s*([^,\r\n]+),\s*([0-9.]+)", inf, re.I)
    res["version"] = m.group(2) if m else None
    if not ok_dev:
        add("inf", "hard", f"the INF is not the UWACPIDriver for {HWID}")
        res["level"] = "hard"
        return res
    add("inf", "ok" if ok_arch else "hard", f"{HWID}, service UWACPIDriver, " + ("amd64" if ok_arch else "no amd64 section")
        + (f", version {res['version']}" if res["version"] else ""))
    if not ok_arch:
        res["level"] = "hard"
        return res
    sha = {f: _sha(files[f]) for f in ("uwacpidriver.sys", "uwacpidriver.cat")}
    res["sha256"] = sha
    known = KNOWN.get((sha["uwacpidriver.sys"], sha["uwacpidriver.cat"]))
    res["known"] = known
    sig = _signature([files["uwacpidriver.cat"], files["uwacpidriver.sys"]])
    level = "ok"
    if sig is None:
        if IS_WIN:
            add("signature", "fail", "the signature could not be checked")
            level = "fail"
        else:
            add("signature", "skip", "checked on Windows only")
    else:
        cat = sig.get(files["uwacpidriver.cat"], {})
        sysf = sig.get(files["uwacpidriver.sys"], {})
        cat_ok = cat.get("status") == "Valid"
        sys_ok = sysf.get("status") in ("Valid", "NotSigned")      # kernel drivers are often signed by the catalog only
        add("signature", "ok" if cat_ok and sys_ok else "fail",
            f"catalog: {cat.get('status')} ({_cn(cat.get('signer'))}); driver: {sysf.get('status')}"
            + (f" ({_cn(sysf.get('signer'))})" if sysf.get("signer") else ""))
        if not (cat_ok and sys_ok):
            level = "fail"
    if known:
        add("hash", "ok", f"known version: {known}")
    else:
        add("hash", "warn", "SHA-256 not in the list of known versions: " + sha["uwacpidriver.sys"][:16] + "…")
        if level == "ok":
            level = "warn"
    res["level"] = level
    return res


_cache = {}


def verify_cached(d):
    """verify() again only when the files changed (the signature check starts PowerShell, ~1 s)."""
    files = _files(d)
    key = (d, tuple(sorted((f, os.path.getsize(p), os.path.getmtime(p)) for f, p in files.items())))
    if key not in _cache:
        _cache.clear()
        _cache[key] = verify(d)
    return _cache[key]


def allowed(res, accept_risks=False):
    """May the package be installed? warn / fail need the user's "I understand the risk"; hard never."""
    lvl = res.get("level")
    return lvl == "ok" or (lvl in ("warn", "fail") and accept_risks)


def driver_store_dir():
    """Newest uwacpidriver.inf_amd64_* folder in the Windows driver store (left by the manufacturer's Control Center)."""
    root = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "DriverStore", "FileRepository")
    cands = [p for p in glob.glob(os.path.join(root, "uwacpidriver.inf_amd64_*")) if os.path.isdir(p)]
    cands = [p for p in cands if len(_files(p)) == len(FILES)]
    return max(cands, key=os.path.getmtime) if cands else None


def fetch_from_system(dest, src=None):
    """Copy the three driver files from the driver store into dest (only those files)."""
    src = src or driver_store_dir()
    if not src:
        raise LookupError("the OEM driver is not in the Windows driver store (the manufacturer's Control Center was never"
                          " installed here) — take it from the repository or the manufacturer's installer")
    os.makedirs(dest, exist_ok=True)
    copied = []
    for f, p in _files(src).items():
        shutil.copyfile(p, os.path.join(dest, os.path.basename(p)))
        copied.append(os.path.basename(p))
    log.warning("OEM driver copied from %s to %s: %s", src, dest, ", ".join(copied))
    return {"from": src, "to": dest, "files": copied}


def main(argv=None):
    """uwccctl driver-verify DIR [--json]: check a package without the service (installers). Exit codes: EXIT."""
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    d = argv[0] if argv else "."
    r = verify(d)
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for c in r["checks"]:
            print(f"[{c['status'].upper():4}] {c['id']}: {c['detail']}")
        print(f"result: {r['level']}")
    return EXIT[r["level"]]
