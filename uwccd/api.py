"""Local HTTP API + web UI.

Security: binds to 127.0.0.1 only, checks the Host header (DNS-rebinding), and every
state-changing request needs the X-UWCC-Token header (token in /run/uwcc/token, group uwcc).
"""
import json
import logging
import mimetypes
import os
import queue
import secrets
import time
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


log = logging.getLogger("uwccd.api")

for _ext, _type in ((".js", "text/javascript"), (".css", "text/css"), (".svg", "image/svg+xml"), (".html", "text/html")):
    mimetypes.add_type(_type, _ext)      # the Windows registry may map .js to text/plain

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
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
        if n > 1_000_000:
            raise ValueError("body too large")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not fp.startswith(WEB_DIR) or not os.path.isfile(fp):
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
                return self._json(200, list(s.sampler.history))
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
            if u.path == "/api/history/export":
                from .automation import export_history
                fmt = parse_qs(u.query).get("format", ["csv"])[0]
                if fmt not in ("csv", "csv-excel", "json"):
                    return self._json(400, {"error": "format: csv | csv-excel | json"})
                data, mime, ext = export_history(list(s.sampler.history), fmt)
                name = time.strftime(f"uwcc-history-%Y%m%d-%H%M%S.{ext}")
                self.send_response(200)
                self.send_header("Content-Type", f"{mime}; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
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
                                      alphabet=(str(b["alphabet"])[:40] if b.get("alphabet") else None))
            elif path == "/api/lightbar":
                s.keyboard.lightbar(str(b.get("zone", "hinge")), power=b.get("power"), effect=b.get("effect"),
                                    light=b.get("light"), speed=b.get("speed"), colors=b.get("colors"))
            elif path == "/api/keyboard/power":
                s.keyboard.set_power(bool(b["on"]))
            elif path == "/api/keyboard/level":
                s.keyboard.set_level(int(b["level"]))
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
        else:
            raise KeyError(op)
        return None

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
        elif key == "debug":
            from .service import apply_debug
            s.settings_store.set("debug", bool(value))
            apply_debug(bool(value))
        elif key == "webcam":
            st.set_webcam(bool(value))
        elif key in ("alerts", "overheat_boost", "kb_off_on_battery", "ppd_sync"):
            s.settings_store.set(key, bool(value))
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
        elif key == "lang":
            if value not in ("en", "ru"):
                raise ValueError("lang: en | ru")
            s.settings_store.set("lang", value)
        else:
            raise KeyError(key)

    def _sse(self):
        s = self.svc
        q = s.subscribe()
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
