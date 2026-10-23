import copy
import json
import logging
import os
import sys
import tempfile
import threading

log = logging.getLogger("uwccd.store")

if sys.platform == "win32":
    DATA_DIR = os.environ.get("UWCC_DATA", os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UWCC", "data"))
else:
    DATA_DIR = os.environ.get("UWCC_DATA", "/var/lib/uwcc")
SHARE_DIR = os.environ.get("UWCC_SHARE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

_lock = threading.Lock()


def path(*p):
    return os.path.join(DATA_DIR, *p)


def load_json(p, default=None):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return copy.deepcopy(default)
    except (OSError, ValueError) as e:
        log.warning("cannot read %s: %s", p, e)
        return copy.deepcopy(default)


def save_json(p, obj):
    with _lock:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)


class Settings:
    """Generic key/value settings (replaces the Windows registry keys under OEM\\GamingCenter2)."""

    def __init__(self, name="settings.json"):
        self.p = path(name)
        self.d = load_json(self.p, {}) or {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        if self.d.get(k) != v:
            self.d[k] = v
            save_json(self.p, self.d)

    def update(self, **kw):
        changed = False
        for k, v in kw.items():
            if self.d.get(k) != v:
                self.d[k] = v
                changed = True
        if changed:
            save_json(self.p, self.d)
