"""Update check against the GitHub releases of the project (once a day when enabled, or on request).

Only https://api.github.com/repos/<REPO>/releases/latest is requested (no identifiers besides the usual
User-Agent). On Windows the service can also download the setup.exe of the release, check it against the
SHA256SUMS.txt of the same release and hand it to the tray application, which starts it with elevation.
"""
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.request

from . import __version__

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
                       setup=next((u for n, u in assets.items() if n.endswith("-setup.exe")), None),
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

    # -- Windows: download + verify, then the tray starts the installer --------------------------------------------
    def download(self):
        if sys.platform != "win32":
            raise NotImplementedError("on Linux install the release archive with install.sh")
        res = self.result
        if not res.get("newer") or not res.get("setup") or not res.get("sums"):
            raise ValueError("no newer release with a Windows installer")
        threading.Thread(target=self._download, args=(res,), daemon=True, name="update-download").start()
        return {"started": True}

    def _download(self, res):
        try:
            from .win.winplat import acl_users_read, data_root
            folder = os.path.join(data_root(), "updates")
            os.makedirs(folder, exist_ok=True)
            acl_users_read(folder)                       # users may read and run it, but not replace it
            name = res["setup"].rsplit("/", 1)[1]
            if not re.fullmatch(r"[\w.\-]+\.exe", name):
                raise ValueError(f"unexpected file name {name}")
            sums = {}
            for line in _get(res["sums"]).decode("utf-8", "replace").splitlines():
                m = re.match(r"([0-9a-fA-F]{64})\s+\*?(\S+)", line.strip())
                if m:
                    sums[m.group(2)] = m.group(1).lower()
            if name not in sums:
                raise ValueError(f"{name} is not listed in SHA256SUMS.txt")
            data = _get(res["setup"], timeout=300)
            digest = hashlib.sha256(data).hexdigest()
            if digest != sums[name]:
                raise ValueError("checksum mismatch — the download is damaged")
            path = os.path.join(folder, name)
            if os.path.exists(path):
                os.remove(path)
            with open(path, "wb") as f:
                f.write(data)
            with self.lock:
                self.result = {**self.result, "download": {"path": path, "sha256": digest}}
            log.info("update downloaded: %s", path)
            self.svc.emit("update_ready", {"path": path, "sha256": digest, "version": res["latest"]})
        except Exception as e:  # noqa: BLE001
            log.warning("update download: %s", e)
            self.svc.emit("update_error", {"error": str(e)})

    def status(self):
        with self.lock:
            return {**self.result, "enabled": self.enabled(), "can_install": sys.platform == "win32"}
