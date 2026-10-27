"""Update check against the GitHub releases of the project (once a day when enabled, or on request).

Only https://api.github.com/repos/<REPO>/releases/latest is requested (no identifiers besides the usual
User-Agent). On Windows the tray application (running as the user) downloads the setup.exe of the release to the user's
Downloads folder, checks it against the SHA256SUMS.txt of the same release and starts it (UAC prompt).
"""
import hashlib
import json
import os
import logging
import re
import sys
import threading
import time
import urllib.request

from . import CONTACT, __version__, build_info, version_string

log = logging.getLogger("uwccd.update")

REPO = "aspidovss/open-uniwill-cc"
REPO_URL = f"https://github.com/{REPO}"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
UA = f"open-uniwill-cc/{__version__}"
DAY = 24 * 3600


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


class Updater(threading.Thread):
    def __init__(self, svc):
        super().__init__(daemon=True, name="updates")
        self.svc = svc
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.result = {"current": __version__, "repo": REPO_URL, "latest": None, "newer": False, "checked": None,
                       "error": None, "download": None}
        self.notified = self.svc.settings_store.get("update_notified")

    def enabled(self):
        return bool(self.svc.settings_store.get("update_check", True))

    def run(self):
        if self.stop.wait(90):
            return
        while not self.stop.is_set():
            last = self.svc.settings_store.get("update_last_check") or 0
            if self.enabled() and time.time() - last >= DAY:
                self.check()
            self.stop.wait(3600)

    def check(self):
        res = dict(self.result)
        try:
            rel = json.loads(_get(API))
            tag = rel.get("tag_name") or ""
            assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
            res.update(latest=tag.lstrip("v"), url=rel.get("html_url") or f"{REPO_URL}/releases",
                       notes=(rel.get("body") or "")[:4000], published=rel.get("published_at"),
                       newer=vtuple(tag) > vtuple(__version__), error=None,
                       setup=_setup_asset(assets),
                       linux=next((u for n, u in assets.items() if n.endswith(".tar.gz") and "linux" in n), None),
                       sums=assets.get("SHA256SUMS.txt"))
        except Exception as e:  # noqa: BLE001
            res["error"] = str(e)
            log.info("update check failed: %s", e)
        res["checked"] = time.time()
        with self.lock:
            self.result = res
        self.svc.settings_store.set("update_last_check", res["checked"])
        if res.get("newer"):
            log.info("update available: %s", res["latest"])
            if self.notified != res["latest"]:
                self.notified = res["latest"]
                self.svc.settings_store.set("update_notified", res["latest"])
                self.svc.emit("update", {"version": res["latest"], "url": res.get("url")})
        self.svc.emit("status", {})
        return res

    # -- Windows: the tray app (running as the user) downloads to the user's Downloads, verifies and starts it --
    def request_install(self):
        if sys.platform != "win32":
            raise NotImplementedError("on Linux install the release archive with install.sh")
        res = self.result
        if not res.get("newer") or not res.get("setup") or not res.get("sums"):
            raise ValueError("no newer release with a Windows installer")
        if not self.svc.tray_clients:
            return {"tray": False, "url": res.get("url")}
        self.set_progress({"state": "requested"})
        self.svc.emit("update_install", {"version": res["latest"], "setup": res["setup"], "sums": res["sums"]})
        return {"tray": True}

    def set_progress(self, b):
        state = str(b.get("state", ""))
        if state not in ("requested", "downloading", "verified", "started", "declined", "error"):
            raise ValueError("state")
        d = {"state": state, "path": b.get("path"), "error": b.get("error"), "percent": b.get("percent")}
        with self.lock:
            self.result = {**self.result, "download": d}
        if state in ("error", "declined", "started", "verified"):
            log.info("update: %s %s", state, b.get("path") or b.get("error") or "")
        self.svc.emit("status", {})
        return d

    def status(self):
        with self.lock:
            return {**self.result, "enabled": self.enabled(), "can_install": sys.platform == "win32",
                    "build": build_info(), "version_full": version_string(), "contact": CONTACT,
                    "tray": bool(getattr(self.svc, "tray_clients", 0))}


def parse_sums(text):
    sums = {}
    for line in text.splitlines():
        m = re.match(r"([0-9a-fA-F]{64})\s+\*?(\S+)", line.strip())
        if m:
            sums[m.group(2)] = m.group(1).lower()
    return sums


def download_verified(setup_url, sums_url, folder, progress=None):
    """Download the installer into `folder` (the user's Downloads), check it against SHA256SUMS.txt.
    Returns the path; a file that does not match is deleted. Used by the Windows tray app."""
    name = setup_url.rsplit("/", 1)[1]
    if not re.fullmatch(r"[\w.\-]+\.exe", name):
        raise ValueError(f"unexpected file name {name}")
    sums = parse_sums(_get(sums_url).decode("utf-8", "replace"))
    if name not in sums:
        raise ValueError(f"{name} is not listed in SHA256SUMS.txt")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    part = path + ".part"
    h = hashlib.sha256()
    req = urllib.request.Request(setup_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
        for chunk in iter(lambda: r.read(1 << 16), b""):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else None
            if progress and pct is not None and pct >= last + 10:
                last = pct
                progress(pct)
    if h.hexdigest() != sums[name]:
        os.remove(part)
        raise ValueError("checksum mismatch — the download is damaged and was deleted")
    if os.path.exists(path):
        os.remove(path)
    os.replace(part, path)
    return path


def _setup_asset(assets):
    """setup.exe of the same edition: "-free-setup.exe" for the free build, "-setup.exe" (non-free) otherwise."""
    from . import edition
    free = edition() == "free"
    for n, u in assets.items():
        if n.endswith("-setup.exe") and n.endswith("-free-setup.exe") == free:
            return u
    return None
