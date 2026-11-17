"""External API: scripts and other computers (Settings -> API, 1.8.2.0). Off by default.

The window, the tray and uwccctl keep using the ordinary token (api.py, every local user can read it). This module adds
a separate, revocable token for other programs, with a scope, and optionally a listener in the local network:

  enabled  off by default; without it the external token is refused everywhere
  scope    "read"  — GET of the stable read endpoints (state, monitor, history, events, languages)
           "full"  — plus the stable control endpoints (mode, profile, Fan Boost, switches, battery, keyboard, cooler,
                     Afterburner, modules); never administrator paths, unlocks, consents, updates, import or reports
  lan      a second listener on 0.0.0.0:<port> (default 47322) that answers only /api/ with the external token,
           only to addresses in "allow" (CIDR list), and blocks an address for 5 minutes after 10 wrong tokens.
           Windows: an inbound firewall rule for the port and the allowed addresses is added and removed with it.
  https    the network listener speaks TLS with a self-signed certificate (uwccd/selfcert.py); clients check its
           SHA-256 fingerprint. Without it the token crosses the network in plain text — the window warns.

The token itself is never stored: only its SHA-256 and the first four characters (to recognise it). It is shown once,
when it is made. Every external request (time, address, method, path, answer) is kept in a list of the last 200.
Docs: docs/API.md "External access".
"""
import collections
import hashlib
import ipaddress
import logging
import os
import re
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import time

from . import store

log = logging.getLogger("uwccd.extapi")

KEY = "api_external"
DEFAULTS = {"enabled": False, "scope": "read", "lan": False, "allow": [], "https": True, "port": 47322}
FIREWALL_RULE = "open-uniwill-cc API"
FAIL_MAX, FAIL_WINDOW_S, BLOCK_S = 10, 600, 300

# what an external token may reach (the stable set of docs/API.md)
READ_GET = ("/api/version", "/api/state", "/api/monitor", "/api/history", "/api/events", "/api/langs")
READ_GET_PREFIX = ("/api/lang/",)
FULL_POST = ("/api/mode", "/api/profile", "/api/fanboost", "/api/setting", "/api/module", "/api/battery",
             "/api/lightbar", "/api/keyboard/power", "/api/keyboard/level", "/api/keyboard/colour",
             "/api/keyboard/effect", "/api/afterburner")
FULL_POST_PREFIX = ("/api/lc/",)
# switches an external program must not flip: consents, warnings and the program's own housekeeping
SETTING_DENY = ("eula_accepted", "clevo_writes", "leishen_writes", "kb_unlock_effects", "kb_untested_no_ask",
                "tcc_extended", "super_performance", "mem_oc", "lc_hwoc", "debug", "fan_manager", "monitoring",
                "update_check", "update_minor", "detect_seen", "history_max_kb", "monitor_interval",
                "monitor_off_oem", "monitor_off_wmi", "monitor_off_all", "webcam")


def permitted(scope, method, path, body=None):
    """May a token of this scope do this? (the caller has already checked the token)"""
    if method == "GET":
        return path in READ_GET or path.startswith(READ_GET_PREFIX)
    if scope != "full":
        return False
    if not (path in FULL_POST or path.startswith(FULL_POST_PREFIX)):
        return False
    if path == "/api/setting":
        k = str((body or {}).get("key") or "")
        return k not in SETTING_DENY and not k.startswith("api")
    return True


def local_networks():
    """[(address, "192.168.1.0/24")] of this computer's IPv4 adapters (no loopback, no link-local)."""
    out = []
    try:
        import psutil
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET and a.netmask:
                    out.append((a.address, a.netmask))
    except ImportError:
        try:
            txt = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True, text=True, timeout=5).stdout
            out = [(m.group(1), m.group(2)) for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", txt)]
        except (OSError, subprocess.SubprocessError):
            pass
    res = []
    for addr, mask in out:
        try:
            itf = ipaddress.ip_interface(f"{addr}/{mask}")
        except ValueError:
            continue
        if itf.ip.is_loopback or itf.ip.is_link_local:
            continue
        res.append((str(itf.ip), str(itf.network)))
    return res


def norm_allow(items):
    """["192.168.1.0/24", "10.0.0.5"] -> normalised networks; raises ValueError on a bad entry."""
    nets = []
    for x in items or []:
        x = str(x).strip()
        if not x:
            continue
        n = ipaddress.ip_network(x, strict=False)
        if n.version != 4:
            raise ValueError(f"{x}: only IPv4 addresses")
        if n.prefixlen < 8:
            raise ValueError(f"{x}: the network is too wide")
        nets.append(str(n))
    return list(dict.fromkeys(nets))


class ExtApi:
    def __init__(self, svc, ui_port=47321):
        self.svc = svc
        self.st = svc.settings_store
        self.ui_port = ui_port
        self.log = collections.deque(maxlen=200)
        self.fails = {}                        # ip -> [timestamps of wrong tokens]
        self.blocked = {}                      # ip -> until
        self.lock = threading.Lock()
        self.httpd = None
        self.error = ""
        self.firewall = ""                     # "added" / "failed: ..." / "" (not Windows or not listening)

    # -- settings ----------------------------------------------------------------------------------
    def cfg(self):
        c = {**DEFAULTS, **(self.st.get(KEY) or {})}
        return c

    def _save(self, c):
        self.st.set(KEY, c)

    def status(self):
        c = self.cfg()
        nets = local_networks()
        with self.lock:
            blocked = {ip: int(u - time.time()) for ip, u in self.blocked.items() if u > time.time()}
        return {"enabled": c["enabled"], "scope": c["scope"], "lan": c["lan"], "allow": c["allow"],
                "https": c["https"], "port": c["port"], "ui_port": self.ui_port,
                "token_set": bool(c.get("token_sha256")), "token_hint": c.get("token_hint", ""),
                "token_made": c.get("token_made"),
                "listening": self.httpd is not None, "error": self.error, "firewall": self.firewall,
                "fingerprint": c.get("tls_fp", "") if c["https"] else "",
                "addresses": [a for a, _ in nets], "suggested": list(dict.fromkeys(n for _, n in nets)),
                "blocked": blocked, "os": "windows" if sys.platform == "win32" else "linux",
                "log": list(self.log)[::-1]}

    def configure(self, b):
        c = self.cfg()
        if "scope" in b:
            if b["scope"] not in ("read", "full"):
                raise ValueError("scope: read | full")
            c["scope"] = b["scope"]
        if "allow" in b:
            c["allow"] = norm_allow(b["allow"])
        if "port" in b:
            p = int(b["port"])
            if not 1024 <= p <= 65535 or p == self.ui_port:
                raise ValueError("port: 1024..65535, not the window's port")
            c["port"] = p
        for k in ("enabled", "lan", "https"):
            if k in b:
                c[k] = bool(b[k])
        if c["lan"] and not c["enabled"]:
            c["lan"] = False
        if c["lan"] and not c["allow"]:
            raise ValueError("allow: name the addresses or networks that may connect")
        if c["enabled"] and not c.get("token_sha256"):
            self._new_token(c)              # never on without a token; the window shows it from the answer
            tok = c.pop("_token")
        else:
            tok = None
        self._save(c)
        log.warning("external API: %s, scope %s, network %s%s", "on" if c["enabled"] else "off", c["scope"],
                    ("on, port %d, %s, allow %s" % (c["port"], "https" if c["https"] else "HTTP", ", ".join(c["allow"])))
                    if c["lan"] else "off", "" if tok is None else " — new token made")
        self.restart()
        st = self.status()
        if tok:
            st["token"] = tok
        return st

    def _new_token(self, c):
        tok = "uwx_" + secrets.token_urlsafe(30)
        c["token_sha256"] = hashlib.sha256(tok.encode()).hexdigest()
        c["token_hint"] = tok[:8]
        c["token_made"] = int(time.time())
        c["_token"] = tok

    def new_token(self):
        c = self.cfg()
        self._new_token(c)
        tok = c.pop("_token")
        self._save(c)
        log.warning("external API: new token (the old one stops working)")
        return {**self.status(), "token": tok}

    def clear_log(self):
        self.log.clear()
        with self.lock:
            self.blocked.clear()
            self.fails.clear()
        return self.status()

    # -- requests ----------------------------------------------------------------------------------
    def role(self, tok):
        """The scope of an external token, or None (wrong token, or the external API is off)."""
        c = self.cfg()
        if not tok or not c["enabled"] or not c.get("token_sha256"):
            return None
        if secrets.compare_digest(hashlib.sha256(tok.encode()).hexdigest(), c["token_sha256"]):
            return c["scope"]
        return None

    def addr_allowed(self, ip):
        try:
            a = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            return False
        if a.is_loopback:
            return True
        return any(a in ipaddress.ip_network(n) for n in self.cfg()["allow"])

    def is_blocked(self, ip):
        with self.lock:
            u = self.blocked.get(ip)
            if u and u <= time.time():
                del self.blocked[ip]
                u = None
            return bool(u)

    def failed(self, ip):
        now = time.time()
        with self.lock:
            f = [x for x in self.fails.get(ip, []) if now - x < FAIL_WINDOW_S] + [now]
            self.fails[ip] = f
            if len(f) >= FAIL_MAX:
                self.blocked[ip] = now + BLOCK_S
                self.fails.pop(ip, None)
                log.warning("external API: %s blocked for %d s after %d wrong tokens", ip, BLOCK_S, FAIL_MAX)
                self.log.append({"t": int(now), "ip": ip, "method": "", "path": "", "code": 429, "via": "lan",
                                 "note": "blocked"})

    def record(self, ip, method, path, code, via):
        self.log.append({"t": int(time.time()), "ip": ip, "method": method, "path": path, "code": int(code),
                         "via": via})

    # -- the network listener ----------------------------------------------------------------------
    def start(self):
        c = self.cfg()
        self.error = ""
        if not (c["enabled"] and c["lan"] and c["allow"]):
            return
        from .api import LanHandler, QuietServer
        try:
            httpd = QuietServer(("0.0.0.0", c["port"]), LanHandler)
            if c["https"]:
                cert, key = self._tls(c)
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                ctx.load_cert_chain(cert, key)
                httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        except (OSError, ssl.SSLError, ValueError) as e:
            self.error = str(e)
            log.warning("external API: cannot listen on port %d: %s", c["port"], e)
            return
        LanHandler.ext = self
        httpd.daemon_threads = True
        threading.Thread(target=httpd.serve_forever, daemon=True, name="http-lan").start()
        self.httpd = httpd
        log.info("external API in the network on %s://0.0.0.0:%d/ (allowed: %s)",
                 "https" if c["https"] else "http", c["port"], ", ".join(c["allow"]))
        self._firewall(c)

    def stop(self):
        h, self.httpd = self.httpd, None
        if h:
            h.shutdown()
            h.server_close()
        self._firewall(None)

    def restart(self):
        self.stop()
        self.start()

    def _tls(self, c, renew=False):
        d = store.path("api-tls")
        os.makedirs(d, exist_ok=True)
        cert, key = os.path.join(d, "cert.pem"), os.path.join(d, "key.pem")
        if renew or not (os.path.isfile(cert) and os.path.isfile(key)):
            from . import selfcert
            from .admin import acl_admins_only
            names = ["localhost", socket.gethostname()]
            fp = selfcert.make(cert, key, names=names, ips=["127.0.0.1"] + [a for a, _ in local_networks()])
            acl_admins_only(key)
            c["tls_fp"] = fp
            self._save(c)
            log.info("external API: new TLS certificate %s", fp)
        elif not c.get("tls_fp"):
            from . import selfcert
            with open(cert, encoding="ascii") as f:
                c["tls_fp"] = selfcert.pem_fingerprint(f.read())
            self._save(c)
        return cert, key

    def renew_cert(self):
        c = self.cfg()
        self._tls(c, renew=True)
        self.restart()
        return self.status()

    def _firewall(self, c):
        """Windows: one inbound rule for the port, limited to the allowed addresses; removed when it stops."""
        if sys.platform != "win32":
            self.firewall = ""
            return
        from .win.winplat import CREATE_NO_WINDOW
        run = lambda *a: subprocess.run(["netsh", "advfirewall", "firewall", *a], capture_output=True, text=True,  # noqa: E731
                                        creationflags=CREATE_NO_WINDOW, timeout=20, check=False)
        try:
            run("delete", "rule", f"name={FIREWALL_RULE}")
            if c is None:
                self.firewall = ""
                return
            r = run("add", "rule", f"name={FIREWALL_RULE}", "dir=in", "action=allow", "protocol=TCP",
                    f"localport={c['port']}", f"remoteip={','.join(c['allow'])}", "profile=any")
            self.firewall = "added" if r.returncode == 0 else "failed: " + (r.stdout or r.stderr).strip()[:200]
        except (OSError, subprocess.SubprocessError) as e:
            self.firewall = f"failed: {e}"
        if self.firewall.startswith("failed"):
            log.warning("external API: firewall rule %s", self.firewall)
