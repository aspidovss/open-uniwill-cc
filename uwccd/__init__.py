"""uwccd — Linux re-implementation of the Uniwill/Tongfang "Control Center" (5.52.x, MBB build).

Hardware protocol reconstructed from GCUService.exe (interoperability analysis):
EC RAM is accessed through the firmware ACPI methods ECRR(addr) / ECRW(addr, data)
of the ACPI device INOU0000, exactly like the Windows UWACPIDriver.sys does.
"""
import os
import sys

__version__ = "1.6.5"
CONTACT = "OUCC@aspidov.ru"
# Edition of the user agreement (uwccd/web/eula.*.txt); a higher number asks for acceptance again.
EULA_VERSION = 1
_build = None


def build_info():
    """{"date": "YYYY-MM-DD", "commit": "abc1234", "source": ...} of this copy of the program.

    build    — uwccd/_build.py written by build_windows.ps1 / install.sh;
    archive  — uwccd/_gitinfo.txt filled in by `git archive` (export-subst);
    checkout — `git log` of a source checkout; otherwise unknown."""
    global _build
    if _build is not None:
        return _build
    info = {"date": None, "commit": None, "source": "unknown"}
    try:
        from ._build import BUILD
        info = {**info, **BUILD, "source": "build"}
    except ImportError:
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(here, "_gitinfo.txt"), encoding="utf-8") as f:
                parts = f.read().split()
            if len(parts) >= 2 and not parts[0].startswith("$"):
                info = {"commit": parts[0], "date": parts[1], "source": "archive"}
        except OSError:
            pass
        if info["commit"] is None and os.path.isdir(os.path.join(here, "..", ".git")):
            try:
                import subprocess
                out = subprocess.run(["git", "-C", os.path.join(here, ".."), "log", "-1", "--format=%h %cs"],
                                     capture_output=True, text=True, timeout=5, check=False).stdout.split()
                if len(out) >= 2:
                    info = {"commit": out[0], "date": out[1], "source": "checkout"}
            except (OSError, ValueError):
                pass
    _build = info
    return info


# Windows builds: "full" — with the OEM driver UWACPIDriver (non-free files), "free" — WMI only, no proprietary files;
# build_windows.ps1 writes the word to EDITION next to the executables. Sources / Linux: "source".


def edition():
    env = os.environ.get("UWCC_EDITION")
    if env in ("free", "full"):
        return env
    if getattr(sys, "frozen", False):
        try:
            with open(os.path.join(os.path.dirname(sys.executable), "EDITION"), encoding="ascii") as f:
                v = f.read().strip().lower()
            if v in ("free", "full"):
                return v
        except OSError:
            pass
        return "full"
    return "source"


def version_string(word="build"):
    """1.4.2 · build 2026-10-23 · a1b2c3d   (free Windows build: 1.6.1 · free · build …)"""
    b = build_info()
    parts = [__version__]
    if edition() == "free":
        parts.append("free")
    if b.get("date"):
        parts.append(f"{word} {b['date']}")
    if b.get("commit"):
        parts.append(b["commit"])
    if b.get("source") == "checkout":
        parts.append("dev")
    return " · ".join(parts)
