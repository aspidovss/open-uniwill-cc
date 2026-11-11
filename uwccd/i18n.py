"""Interface languages (1.8.0.0).

English is the source language (the keys); Russian is built in (uwccd/web/i18n.js, agentcore). Any other language
is ONE JSON file, no code — docs/TRANSLATING.md tells how to write one and `tools/make_lang_template.py` makes the
blank. The file is looked for in two places; the data directory wins, so a translation can be tried without
touching the installation:

    uwccd/web/lang/<code>.json             shipped with the program (contributed translations)
    <data dir>/langs/<code>.json           added by the user (%ProgramData%\\UWCC\\data\\langs, /var/lib/uwcc/langs)

Shape ("web" keys are the English interface texts):

    {"name": "Deutsch", "web": {"Settings": "Einstellungen", ...},
     "service": {"upd": "...{}...", ...}, "tray": {"open": "...", ...}}

"service" and "tray" translate the notifications and the tray menu (the keys of agentcore.TEXT / agentcore.TRAY);
both are optional — missing keys fall back to English. The window loads "web" through /api/lang/<code>.
"""
import json
import logging
import os
import re

from . import store

log = logging.getLogger("uwcc.i18n")

SHIPPED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "lang")
BUILTIN = {"en": "English", "ru": "Русский"}
_cache = {}


def _user_dir():
    return store.path("langs")


def _file(code):
    for d in (_user_dir(), SHIPPED):
        p = os.path.join(d, f"{code}.json")
        if os.path.isfile(p):
            return p
    return None


def available():
    """[{code, name, builtin}] — the languages the interface can offer, builtins first."""
    out = [{"code": c, "name": n, "builtin": True} for c, n in BUILTIN.items()]
    seen = set(BUILTIN)
    for d in (SHIPPED, _user_dir()):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in names:
            code = fn[:-5].lower()
            if not fn.endswith(".json") or code in seen or not re.fullmatch(r"[a-z]{2}(-[a-z0-9]{2,8})?", code):
                continue
            lang = load(code)
            if lang:
                seen.add(code)
                out.append({"code": code, "name": lang.get("name") or code, "builtin": False})
    return out


def load(code):
    """The parsed language file, or None. Cached by file path + mtime."""
    code = (code or "").lower()
    p = _file(code)
    if not p:
        return None
    try:
        mtime = os.path.getmtime(p)
        hit = _cache.get(code)
        if hit and hit[0] == (p, mtime):
            return hit[1]
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
        if not isinstance(d, dict) or not isinstance(d.get("web", {}), dict):
            raise ValueError("not a language file")
        _cache[code] = ((p, mtime), d)
        return d
    except (OSError, ValueError) as e:
        log.warning("language %s: %s", code, e)
        return None


def valid(code):
    return code in BUILTIN or load(code) is not None


def texts(code, section):
    """The "service"/"tray" dict of an extra language ({} for builtins and unknowns)."""
    if code in BUILTIN:
        return {}
    d = load(code) or {}
    sec = d.get(section)
    return sec if isinstance(sec, dict) else {}
