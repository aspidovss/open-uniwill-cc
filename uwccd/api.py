"""Local HTTP API + web UI.

Security: binds to 127.0.0.1 only, checks the Host header (DNS-rebinding), and every
state-changing request needs the X-UWCC-Token header (token in /run/uwcc/token, group uwcc).
"""
import json
import logging
import mimetypes
import os
import queue
import re
import secrets
import time
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


log = logging.getLogger("uwccd.api")

# changes that need administrator rights (admin.py): how the EC is reached, its settings, platform profiles
ADMIN_PATHS = ("/api/ec-access", "/api/ec-access/config", "/api/ec-access/install-driver", "/api/ec-access/fetch-driver",
               "/api/history/config", "/api/platform/import",
               "/api/platform/apply-draft", "/api/platform/reset")
# refused while a mode / profile is being applied (the window shows "Applying…")
BUSY_PATHS = ("/api/mode", "/api/profile", "/api/fanboost", "/api/restore")
BUSY_SETTINGS = ("super_performance", "tcc_extended")

for _ext, _type in ((".js", "text/javascript"), (".css", "text/css"), (".svg", "image/svg+xml"), (".html", "text/html"),
                    (".md", "text/markdown")):
    mimetypes.add_type(_type, _ext)      # the Windows registry may map .js to text/plain

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def _docs_dir():
    """docs/ next to the package (source, Linux /opt/uwcc), or bundled by PyInstaller (Windows)."""
    for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"),
              os.path.join(getattr(sys, "_MEIPASS", ""), "docs")):
        if os.path.isdir(os.path.join(d, "EC")):
            return os.path.normpath(d)
    return None


DOCS_DIR = _docs_dir()
if sys.platform == "win32":
    RUN_DIR = os.environ.get("UWCC_RUN", os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UWCC", "run"))
else:
    RUN_DIR = os.environ.get("UWCC_RUN", "/run/uwcc")


def write_token(token):
    try:
        os.makedirs(RUN_DIR, exist_ok=True)
        p = os.path.join(RUN_DIR, "token")
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        if sys.platform == "win32":
            from .win.winplat import acl_users_read
            acl_users_read(p)
            return
        try:
            import grp
            gid = grp.getgrnam("uwcc").gr_gid
            os.chown(p, 0, gid)
            os.chown(RUN_DIR, 0, gid)
            os.chmod(RUN_DIR, 0o750)
        except (KeyError, PermissionError, ImportError):
            os.chmod(p, 0o644)
    except OSError as e:
        log.warning("token file: %s", e)


class Handler(BaseHTTPRequestHandler):
    server_version = "uwccd"
    svc = None
    token = None
    port = 0

    def log_message(self, fmt, *args):
        log.debug("%s %s", self.address_string(), fmt % args)

    # -- helpers ---------------------------------------------------------------
    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _auth(self):
        tok = self.headers.get("X-UWCC-Token") or parse_qs(urlparse(self.path).query).get("token", [None])[0]
        return tok is not None and secrets.compare_digest(tok, self.token)

    @staticmethod
    def _range(u):
        """?range= seconds (60, 300, 900, 3600, 86400) or 1m / 5m / 15m / 1h / 24h; default one hour."""
        v = (parse_qs(u.query).get("range") or ["3600"])[0].lower()
        v = {"1m": "60", "5m": "300", "15m": "900", "1h": "3600", "24h": "86400"}.get(v, v)
        return int(v) if v.isdigit() and 0 < int(v) <= 86400 else 3600

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4_000_000:
            raise ValueError("body too large")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        base = WEB_DIR
        if path.startswith("/help/"):                    # built-in help: the documentation (Markdown) of docs/
            base, path = DOCS_DIR, unquote(path[5:])
            if not base or not path.endswith(".md"):
                return self._json(404, {"error": "not found"})
        fp = os.path.normpath(os.path.join(base, path.lstrip("/")))
        if not fp.startswith(base + os.sep) or not os.path.isfile(fp):
            return self._json(404, {"error": "not found"})
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(data)

    # -- routing ---------------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return self._static(u.path)
        if not self._auth():
            return self._json(401, {"error": "token required"})
        s = self.svc
        try:
            if u.path == "/api/state":
                return self._json(200, s.state())
            if u.path == "/api/monitor":
                return self._json(200, s.sampler.snapshot())
            if u.path == "/api/history":
                return self._json(200, s.sampler.points(self._range(u)))
            if u.path == "/api/lighting/devices":
                from .lighting import ite
                kb = s.keyboard
                return self._json(200, {
                    "devices": [] if s.mock else ite.list_devices(),
                    "keyboard": {"kind": kb.kind, **(kb.rgb.info() if kb.rgb else {}),
                                 "effect": kb.rgb.saved if kb.rgb else None},
                    "ec": {"caps_78e": f"{s.ec.read(0x78E):02X}", "caps_742": f"{s.ec.read(0x742):02X}",
                           "kb_id_73c": f"{s.ec.read(0x73C):02X}", "status_768": f"{s.ec.read(0x768):02X}",
                           "rgb_lightbar": s.pf.rgb_lightbar}})
            if u.path == "/api/export":
                from . import backup
                q = parse_qs(u.query)
                what = q.get("what", ["all"])[0]
                table = q.get("table", [None])[0]
                if table and table not in s.power.tables.tables:
                    return self._json(404, {"error": f"no table {table}"})
                data = json.dumps(backup.export(s, what, table), ensure_ascii=False, indent=1).encode()
                tag = table or ("fans" if what == "fans" else "backup")
                name = time.strftime(f"uwcc-{tag}-{s.pf.project_name}-%Y%m%d-%H%M%S.json")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return None
            if u.path == "/api/update":
                return self._json(200, s.updater.status())
            if u.path == "/api/dynamic-boost":
                from . import nvpowerd
                return self._json(200, nvpowerd.status(refresh="refresh" in u.query) if s.pf.nv_gpu and not s.mock
                                  else {"present": False, "active": False, "can_enable": False, "service": None})
            if u.path == "/api/import/original":
                from . import backup
                return self._json(200, {"available": bool(backup.original_dir()), "dir": backup.original_dir()})
            if u.path == "/api/history/export":
                from .automation import export_history
                fmt = parse_qs(u.query).get("format", ["csv"])[0]
                if fmt not in ("csv", "csv-excel", "json"):
                    return self._json(400, {"error": "format: csv | csv-excel | json"})
                data, mime, ext = export_history(s.sampler.points(self._range(u)), fmt)
                name = time.strftime(f"uwcc-history-%Y%m%d-%H%M%S.{ext}")
                self.send_response(200)
                self.send_header("Content-Type", f"{mime}; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return None
            if u.path == "/api/report/summary":
                from . import report
                return self._json(200, report.summary(s))
            if u.path == "/api/report/status":
                from . import report
                j = report.Job.current
                return self._json(200, j.status() if j else {"state": "none"})
            if u.path == "/api/report/file":
                from . import report
                j = report.Job.current
                if not j or j.state != "done" or (parse_qs(u.query).get("id") or [""])[0] != j.id:
                    return self._json(404, {"error": "the report is not ready"})
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{j.name}"')
                self.send_header("Content-Length", str(len(j.data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(j.data)
                return None
            if u.path == "/api/report":
                from . import report
                q = parse_qs(u.query)
                split = lambda k, d: [x for x in (q.get(k) or [d])[0].split(",") if x]   # noqa: E731
                secs = split("sections", ",".join(report.DEFAULT_SECTIONS))
                if (q.get("full") or ["0"])[0] == "1" and "oem_files_full" not in secs:
                    secs.append("oem_files_full")
                data, name = report.build(s, secs, split("private", ""))
                want = (q.get("name") or [""])[0]
                if re.fullmatch(r"uwcc-report-[\w.-]{1,80}\.zip", want):
                    name = want
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("X-UWCC-Filename", name)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return None
            if u.path == "/api/gpu":
                from .monitor import dgpu_state, dgpu_users
                st = dgpu_state()
                return self._json(200, {"present": st is not None, "state": st,
                                        "users": dgpu_users() if st is not None else []})
            if u.path == "/api/events":
                return self._sse()
            if u.path.startswith("/api/table/"):
                name = u.path.rsplit("/", 1)[1]
                return self._json(200, s.power.tables.tables.get(name))
            if u.path == "/api/ec-access":
                return self._json(200, s.ec_access())
            if u.path == "/api/ec-access/config":
                from . import ecaccess
                pid = s.pf.project_raw
                return self._json(200, {"effective": ecaccess.config(pid), "user": ecaccess.user_config(),
                                        "defaults": ecaccess.factory(pid)})
            if u.path == "/api/platform":
                from . import platformdb
                return self._json(200, {**platformdb.summary(s.pf.project_raw),
                                        "profile": platformdb.export(s.pf.project_raw)})
            if u.path == "/api/clevo":                    # Control Center 3.0 / Clevo (experimental)
                return self._json(200, s.clevo.status())
            if u.path == "/api/selfcheck":
                return self._json(200, {**s.selfcheck.summary(), "result": s.selfcheck.last})
            if u.path == "/api/selfcheck/export":
                return self._json(200, s.selfcheck.export())
            if u.path == "/api/admin":
                return self._json(200, s.admin.status())
            if u.path == "/api/busy":
                return self._json(200, {"ops": s.busy.state()})
            if u.path == "/api/nvram":
                return self._json(200, s.nvram.fields())
            if u.path.startswith("/api/ec/"):
                addr = int(u.path.rsplit("/", 1)[1], 16)
                return self._json(200, {"addr": addr, "value": s.ec.read(addr)})
        except Exception as e:  # noqa: BLE001
            log.exception("GET %s", u.path)
            return self._json(500, {"error": str(e)})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        return self._write("POST")

    def do_PUT(self):
        return self._write("PUT")

    def _write(self, method):
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        if not self.headers.get("X-UWCC-Token") or not self._auth():
            return self._json(401, {"error": "token required"})
        s = self.svc
        u = urlparse(self.path)
        path = u.path
        try:
            b = self._body()
            if path in ADMIN_PATHS or (path == "/api/selfcheck" and int(b.get("stage", 1)) >= 2):
                if not s.admin.allowed(self.headers.get("X-UWCC-Admin")):
                    return self._json(403, {"error": "administrator rights required", "admin_required": True})
            busy = s.busy.blocking()
            if busy and (path in BUSY_PATHS or path.startswith(("/api/profiles/", "/api/profile-reset/", "/api/selfcheck"))
                         or (path == "/api/setting" and b.get("key") in BUSY_SETTINGS)):
                return self._json(409, {"error": "busy", "busy": busy})
            if (path in ("/api/mode", "/api/profile", "/api/fanboost", "/api/restore")
                    or path.startswith(("/api/profiles/", "/api/table/", "/api/profile-reset/"))) and not s.fan_control:
                return self._json(409, {"error": "fan control disabled on this EC (no RamFan 1.5)"})
            if path == "/api/mode":
                s.power.user_set_mode(int(b["mode"]))
            elif path == "/api/profile":
                s.power.set_profile_index(int(b["mode"]), int(b["index"]))
            elif path == "/api/fanboost":
                s.power.set_fan_boost(bool(b["on"]))
            elif path == "/api/restore":
                s.power.restore()
            elif path.startswith("/api/profile-reset/"):
                if not hasattr(s.power, "restore_profile"):
                    return self._json(409, {"error": "custom profiles are not available on this platform"})
                return self._json(200, s.power.restore_profile(path.rsplit("/", 1)[1]))
            elif path.startswith("/api/profiles/"):
                name = path.rsplit("/", 1)[1]
                return self._json(200, s.power.update_profile(name, b))
            elif path.startswith("/api/table/") and path.endswith("/restore"):
                name = path.split("/")[3]
                if name not in s.power.TABLE_NAMES:
                    raise KeyError(name)
                return self._json(200, s.power.restore_table(name))
            elif path.startswith("/api/table/"):
                name = path.rsplit("/", 1)[1]
                return self._json(200, s.power.update_table(name, b))
            elif path == "/api/setting":
                self._setting(b["key"], b["value"])
            elif path == "/api/battery":
                if "health_mode" in b:
                    s.battery.set_health(int(b["health_mode"]))
                if "limit_up" in b or "limit_down" in b:
                    s.battery.set_limits(b.get("limit_up"), b.get("limit_down"), b.get("limit_mode"))
                if "typec_priority" in b:
                    s.battery.set_typec_priority(bool(b["typec_priority"]))
            elif path == "/api/keyboard/effect":
                s.keyboard.set_effect(idx=int(b["effect"]), light=int(b.get("light", 4)),
                                      speed=int(b.get("speed", 2)), direction=int(b.get("direction", 0)),
                                      colors=b.get("colors"), circular=bool(b.get("circular")), user=b.get("user"),
                                      alphabet=(str(b["alphabet"])[:40] if b.get("alphabet") else None),
                                      fx=b.get("fx") if isinstance(b.get("fx"), dict) else None,
                                      untested=bool(b.get("untested")))
            elif path in ("/api/import", "/api/import/original"):
                from . import backup
                if path == "/api/import/original":
                    data = backup.read_original()
                    if not data:
                        return self._json(404, {"error": "the original Control Center was not found"})
                else:
                    data = b.get("data")
                sections = [x for x in (b.get("sections") or ["fans", "profiles"]) if x in ("fans", "profiles", "settings")]
                res = backup.import_data(s, data, sections, check_project=not b.get("force"))
                s.emit("status", {})
                if res["restart"] and not s.mock:
                    log.info("settings imported — restarting the service")
                    threading.Timer(1.5, lambda: os._exit(3)).start()   # systemd / SCM restart the service
                return self._json(200, res)
            elif path == "/api/update/check":
                s.updater.check()
                return self._json(200, s.updater.status())
            elif path == "/api/update/download":
                return self._json(200, s.updater.request_install())
            elif path == "/api/service/restart":
                return self._json(200, {"restarting": s.restart_service("restart button")})
            elif path == "/api/history/clear":
                s.sampler.clear()
                return self._json(200, s.sampler.info())
            elif path == "/api/history/config":
                return self._json(200, s.sampler.move_to(str(b.get("dir") or "")))
            elif path == "/api/admin/unlock":
                if not s.admin.valid(self.headers.get("X-UWCC-Admin")):
                    return self._json(403, {"error": "administrator key required", "admin_required": True})
                return self._json(200, s.admin.unlock(int(b.get("seconds", 600))))
            elif path == "/api/admin/lock":
                return self._json(200, s.admin.lock_now())
            elif path == "/api/admin/request":
                s.emit("admin_request", {})
                return self._json(200, {"tray": s.tray_clients > 0, **s.admin.status()})
            elif path == "/api/admin/declined":
                s.emit("admin", {**s.admin.status(), "declined": True})
            elif path == "/api/selfcheck":
                stage = int(b.get("stage", 1))
                if stage not in (1, 2):
                    raise ValueError("stage: 1 | 2")
                s.selfcheck.start(stage)
                return self._json(200, {"started": stage})
            elif path.startswith("/api/platform/"):
                return self._json(200, self._platform(path[14:], b))
            elif path == "/api/report/start":
                from . import report
                secs = [x for x in (b.get("sections") or list(report.DEFAULT_SECTIONS)) if x in report.SECTIONS]
                if b.get("full") and "oem_files_full" not in secs:
                    secs.append("oem_files_full")
                want = str(b.get("name") or "")
                name = want if re.fullmatch(r"uwcc-report-[\w.-]{1,80}\.zip", want) else None
                return self._json(200, report.Job.start(s, secs, [x for x in (b.get("private") or []) if x in report.PRIVATE],
                                                        name).status())
            elif path == "/api/reveal":                    # the tray shows a downloaded file in Explorer
                name = os.path.basename(str(b.get("name", "")))
                if not name.startswith("uwcc-") or not s.tray_clients:
                    return self._json(200, {"tray": False})
                s.emit("reveal", {"name": name})
                return self._json(200, {"tray": True})
            elif path == "/api/update/progress":           # reported by the tray, which downloads and installs
                return self._json(200, s.updater.set_progress(b))
            elif path == "/api/dynamic-boost/enable":
                from . import nvpowerd
                return self._json(200, nvpowerd.enable())
            elif path == "/api/lightbar":
                s.keyboard.lightbar(str(b.get("zone", "hinge")), power=b.get("power"), effect=b.get("effect"),
                                    light=b.get("light"), speed=b.get("speed"), colors=b.get("colors"))
            elif path == "/api/keyboard/power":
                s.keyboard.set_power(bool(b["on"]))
            elif path == "/api/keyboard/level":
                s.keyboard.set_level(int(b["level"]))
            elif path == "/api/keyboard/feedback":          # untested effect: does it work on this keyboard?
                r = s.keyboard.feedback(int(b["effect"]), bool(b.get("works")))
                s.emit("keyboard", s.keyboard.status())
                return self._json(200, r)
            elif path == "/api/keyboard/fx/input":         # tray / agent: key presses, screen picture, audio levels
                return self._json(200, s.keyboard.fx_input(keys=b.get("keys"), screen=b.get("screen"),
                                                           metrics=b.get("metrics")))
            elif path == "/api/keyboard/fx/config":
                cfg = s.keyboard.set_fx_config(b)
                s.emit("keyboard", s.keyboard.status())
                return self._json(200, cfg)
            elif path == "/api/keyboard/fx/calibrate":
                r = s.keyboard.fx_calibrate(str(b.get("action", "")), b.get("observed"))
                s.emit("keyboard", s.keyboard.status())
                return self._json(200, r)
            elif path == "/api/clevo":                    # Control Center 3.0 / Clevo (experimental)
                return self._json(200, s.clevo.command(b))
            elif path == "/api/load-rules":               # Automation: mode by power / temperature / load
                from .automation import check_load_rules
                s.settings_store.set("load_rules", check_load_rules(b.get("rules", [])))
                s.load_rules.active = None
                s.load_rules.since.clear()
                s.emit("status", {})
                return self._json(200, s.load_rules.status())
            elif path == "/api/appbinding":
                rules = [{"process": str(r["process"])[:64], "mode": int(r["mode"]),
                          "enabled": bool(r.get("enabled", True))} for r in b.get("rules", [])]
                s.settings_store.set("app_binding", rules)
            elif path == "/api/idle":
                kb_timeout = int(s.settings_store.get("kb_timeout", 0) or 0)
                s.keyboard.idle(bool(b.get("idle")) and kb_timeout > 0)
                return self._json(200, {"ok": True, "timeout": kb_timeout})
            elif path == "/api/resume":
                s.on_poll_change("resume", None)
            elif path.startswith("/api/ec-access"):
                return self._json(200, self._ec_access(path, b))
            elif path.startswith("/api/lc/"):
                r = self._liquid(path[8:], b)
                if r is not None:
                    return self._json(200, r)
            else:
                return self._json(404, {"error": "not found"})
            s.emit("status", {})
            return self._json(200, {"ok": True})
        except NotImplementedError as e:
            return self._json(501, {"error": str(e)})
        except (ConnectionError, LookupError, TimeoutError) as e:
            return self._json(409, {"error": str(e) or type(e).__name__})
        except (KeyError, ValueError, TypeError) as e:
            return self._json(400, {"error": f"{type(e).__name__}: {e}"})
        except Exception as e:  # noqa: BLE001
            log.exception("%s %s", method, path)
            return self._json(500, {"error": str(e)})

    def _liquid(self, op, b):
        lc = self.svc.liquid
        if op == "scan":
            return {"devices": lc.scan()}
        if op == "connect":
            lc.connect(b["address"])
        elif op == "disconnect":
            lc.disconnect(forget=bool(b.get("forget")))
        elif op == "config":
            lc.configure(b)
        elif op == "prime":
            lc.prime(stop=bool(b.get("stop")))
        elif op == "suspend":
            lc.suspend()
        elif op == "profile":                      # cooler profiles: apply / save / copy / remove / rename
            return {"id": lc.profile(b), "status": lc.status()}
        else:
            raise KeyError(op)
        return None

    def _platform(self, op, b):
        """Platform profile of this laptop (administrator): import a file, apply the self-check draft, reset."""
        from . import platformdb
        s = self.svc
        pid = s.pf.project_raw
        if op == "import":
            p = platformdb.save_user(b.get("profile") or {})
        elif op == "apply-draft":
            d = (s.selfcheck.last or {}).get("draft")
            if not d:
                raise LookupError("run the self-check first")
            p = platformdb.save_user(d)
        elif op == "reset":
            platformdb.reset_user(pid)
            p = None
        else:
            raise KeyError(op)
        if p is not None and pid is not None and pid not in [int(x, 16) for x in p["match"]["project"]]:
            log.warning("platform profile %s is for %s, this laptop is 0x%02X", p["id"], p["match"]["project"], pid)
        s.emit("status", {})
        return {**platformdb.summary(pid), "restart_needed": s.ec_info.get("active") == "wmi"}

    def _ec_access(self, path, b):
        """EC Manager: EC path (OEM driver / WMI beta), the WMI warning, ec_wmi.json, a quick test."""
        from . import ecaccess
        s = self.svc
        st = s.settings_store
        if path == "/api/ec-access":
            restart = False
            if "consent" in b:
                if int(b["consent"]) != ecaccess.WMI_CONSENT_VERSION:
                    raise ValueError(f"warning edition is {ecaccess.WMI_CONSENT_VERSION}")
                if st.get("wmi_consent") != ecaccess.WMI_CONSENT_VERSION:
                    st.set("wmi_consent", ecaccess.WMI_CONSENT_VERSION)
                    log.warning("WMI EC path: the user accepted the warning (edition %d)", ecaccess.WMI_CONSENT_VERSION)
                    restart = s.ec_info.get("active") == "none"
            if "backend" in b:
                v = str(b["backend"])
                if v not in ecaccess.BACKENDS:
                    raise ValueError("backend: auto | oem | wmi")
                if v != st.get("ec_backend", "auto"):
                    st.set("ec_backend", v)
                    log.info("EC path setting: %s", v)
                    restart = True
            restarting = s.restart_service("EC path changed") if restart else False
            return {**s.ec_access(), "restarting": bool(restarting), "restart_needed": restart}
        if path == "/api/ec-access/config":
            if b.get("reset"):
                ecaccess.reset_user_config()
            else:
                ecaccess.save_user_config(b.get("config") or {})
            s.emit("status", {})
            return {"effective": ecaccess.config(), "user": ecaccess.user_config(),
                    "restart_needed": s.ec_info.get("active") == "wmi"}
        if path == "/api/ec-access/fetch-driver":
            r = ecaccess.fetch_oem_driver(mock=s.mock)
            pkg = ecaccess.oem_driver_package(check=True)
            s.emit("status", {})
            return {**r, "package": pkg}
        if path == "/api/ec-access/install-driver":
            try:
                r = ecaccess.install_oem_driver(mock=s.mock, accept_risks=bool(b.get("accept_risks")))
            except PermissionError as e:
                pkg = ecaccess.oem_driver_package(check=True)
                return {"installed": False, "risk_required": True, "error": str(e), "check": (pkg or {}).get("check")}
            restart = s.ec_info.get("active") != "oem"
            if restart and st.get("ec_backend", "auto") == "wmi":
                st.set("ec_backend", "auto")                  # the OEM driver is there now: the recommended path
            r["restarting"] = s.restart_service("OEM driver installed") if restart else False
            return {**r, "restart_needed": restart}
        if path == "/api/ec-access/test":
            import time as _t
            ec = s.ec
            raw = getattr(ec, "_read", ec.read)
            res = {"path": s.ec_info.get("active"), "reads": []}
            if res["path"] == "none":
                raise LookupError("no EC access")
            t0 = _t.perf_counter()
            pid = raw(0x740) & 0xFF
            res["project"] = f"0x{pid:02X}"
            from . import platformdb
            res["tested_platform"] = platformdb.summary(pid)["status"] == "verified"
            for a in (0x751, 0x783, 0x784, 0x785, 0x7B9, 0x74E):
                res["reads"].append({"addr": f"0x{a:03X}", "value": raw(a) & 0xFF})
            res["ms_per_read"] = round((_t.perf_counter() - t0) / 7 * 1000, 1)
            return res
        raise KeyError(path)

    def _setting(self, key, value):
        s = self.svc
        st = s.settings
        if key == "winkey_lock":
            st.set_winkey(bool(value))
        elif key == "fn_lock":
            st.set_fn_lock(bool(value))
        elif key == "usb_charger":
            st.set_usb_charger(bool(value))
        elif key == "touchpad_toggle":
            st.set_touchpad_toggle(bool(value))
        elif key == "touchpad_enabled":
            st.set_touchpad(bool(value))
        elif key == "ac_recovery":
            st.set_ac_recovery(bool(value))
        elif key == "dgpu_direct":
            st.set_dgpu_direct(bool(value))
        elif key == "lightbar_trigger":
            st.lightbar_trigger()
        elif key in ("wifi", "bluetooth"):
            st.rfkill(key if key == "bluetooth" else "wifi", bool(value))
        elif key == "kb_timeout":
            v = int(value)
            if not 0 <= v <= 3600:
                raise ValueError("0..3600 s")
            s.settings_store.set("kb_timeout", v)
        elif key == "osd":
            s.settings_store.set("osd", bool(value))
        elif key == "lc_hwoc":
            s.settings_store.set("lc_hwoc", bool(value))
            s.hwoc.wake.set()
        elif key == "mem_oc":
            s.settings.set_mem_oc(bool(value))
        elif key == "super_performance":
            if not hasattr(s.power, "user_set_super"):
                raise ValueError("super performance is not available on this laptop")
            s.power.user_set_super(bool(value))
        elif key == "eula_accepted":
            from . import EULA_VERSION
            if int(value) != EULA_VERSION:
                raise ValueError(f"agreement edition is {EULA_VERSION}")
            s.settings_store.set("eula_accepted", EULA_VERSION)
            log.info("user agreement %d accepted in the window", EULA_VERSION)
        elif key == "history_record":
            s.settings_store.set("history_record", bool(value))
        elif key == "update_check":
            s.settings_store.set("update_check", bool(value))
        elif key == "kb_fx_screen":                  # Linux: allow BetterRGB Screen ambient (off by default)
            s.keyboard.set_screen_fx(bool(value))
        elif key in ("clevo_writes", "clevo_restore"):     # Control Center 3.0 / Clevo (experimental)
            s.settings_store.set(key, bool(value))
            s.emit("clevo", {})
        elif key in ("kb_unlock_effects", "kb_untested_no_ask"):   # untested keyboard effects (no admin: lighting only)
            s.settings_store.set(key, bool(value))
            if key == "kb_unlock_effects" and not value:
                s.settings_store.set("kb_untested_no_ask", False)      # locking again asks again next time
        elif key == "kb_picture_modes":
            s.settings_store.set("kb_picture_modes", bool(value))
        elif key == "tcc_extended":
            s.settings_store.set("tcc_extended", bool(value))
            if hasattr(s.power, "set_tcc_extended"):
                s.power.set_tcc_extended(bool(value))
        elif key == "debug":
            from .service import apply_debug
            s.settings_store.set("debug", bool(value))
            apply_debug(bool(value))
        elif key == "webcam":
            st.set_webcam(bool(value))
        elif key in ("alerts", "overheat_boost", "kb_off_on_battery", "ppd_sync", "ppd_follow"):
            s.settings_store.set(key, bool(value))
        elif key == "ppd_modes":                  # system power profile -> laptop mode
            from .automation import SYS_PROFILES
            if not isinstance(value, dict) or set(value) - set(SYS_PROFILES):
                raise ValueError("ppd_modes: {power-saver|balanced|performance: keep | 0..3}")
            out = {}
            for k in SYS_PROFILES:
                v = value.get(k, "keep")
                if v != "keep":
                    v = int(v)
                    if v not in s.power.MODES:
                        raise ValueError(f"ppd_modes {k}: mode not available")
                out[k] = v
            s.settings_store.set(key, out)
        elif key in ("cpu_alert", "gpu_alert"):
            v = int(value)
            if not 60 <= v <= 105:
                raise ValueError("60..105 °C")
            s.settings_store.set(key, v)
        elif key in ("mode_on_ac", "mode_on_battery"):
            if value not in ("keep", "previous", 0, 1, 2, 3) or (key == "mode_on_battery" and value == "previous"):
                raise ValueError("keep | previous | 0..3")
            if isinstance(value, int) and value not in s.power.MODES:
                raise ValueError("mode not available")
            s.settings_store.set(key, value)
        elif key == "fan_manager":
            if value not in ("auto", "cml", "std"):
                raise ValueError("fan_manager: auto | cml | std")
            if value == s.settings_store.get("fan_manager", "auto"):
                return
            s.settings_store.set("fan_manager", value)
            log.info("fan manager set to %s — restarting the service", value)
            s.restart_service("fan manager changed")          # the manager is chosen at start-up
        elif key == "monitoring":                         # EC Manager drop-down: all three switches at once
            flags = {"full": (0, 0, 0), "off_oem": (1, 0, 0), "off_wmi": (0, 1, 0), "off_both": (1, 1, 0),
                     "off_all": (0, 0, 1)}.get(value)
            if flags is None:
                raise ValueError("monitoring: full | off_oem | off_wmi | off_both | off_all")
            for k, v in zip(("monitor_off_oem", "monitor_off_wmi", "monitor_off_all"), flags):
                s.settings_store.set(k, bool(v))
            log.info("monitoring: %s -> %s", value, s.monitor_level())
            s.sampler.wake()
        elif key == "monitor_interval":
            v = float(value or 0)
            if v and not 1 <= v <= 60:
                raise ValueError("monitor_interval: 0 (automatic) or 1..60 s")
            s.settings_store.set("monitor_interval", v)
            s.sampler.wake()
        elif key == "history_max_kb":
            v = int(value)
            if not 64 <= v <= 512000:
                raise ValueError("history_max_kb: 64..512000")
            s.settings_store.set("history_max_kb", v)
            s.sampler.save_day()
        elif key in ("monitor_off_oem", "monitor_off_wmi", "monitor_off_all"):
            s.settings_store.set(key, bool(value))
            log.info("monitoring setting %s = %s -> %s", key, bool(value), s.monitor_level())
            s.sampler.wake()
        elif key == "lang":
            if value not in ("en", "ru"):
                raise ValueError("lang: en | ru")
            s.settings_store.set("lang", value)
        else:
            raise KeyError(key)

    def _sse(self):
        s = self.svc
        q = s.subscribe()
        tray = (parse_qs(urlparse(self.path).query).get("client") or [""])[0] == "tray"
        if tray:
            s.tray_clients += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=1.5)
                except queue.Empty:
                    msg = json.dumps({"type": "monitor", "data": s.sampler.snapshot()}, default=str)
                self.wfile.write(f"data: {msg}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            s.unsubscribe(q)
            if tray:
                s.tray_clients -= 1


def serve(svc, port=47321, token=None):
    Handler.svc = svc
    Handler.token = token or secrets.token_urlsafe(24)
    Handler.port = port
    write_token(Handler.token)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True, name="http")
    t.start()
    log.info("UI/API on http://127.0.0.1:%d/", port)
    return httpd
