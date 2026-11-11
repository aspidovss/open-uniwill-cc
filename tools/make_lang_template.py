#!/usr/bin/env python3
"""Make a translation template: every interface text of open-uniwill-cc as one JSON file (1.8.0.0).

    python3 tools/make_lang_template.py > de.json

Fill the empty strings with the translation (leave a string empty to fall back to English), set "name" to the
language's own name, save the file as `uwccd/web/lang/<code>.json` (or `<data dir>/langs/<code>.json` to try it on
an installed copy) and restart the window. docs/TRANSLATING.md has the details and the rules for the `{0}`
placeholders. The keys come from the Russian dictionary (uwccd/web/i18n.js), which always covers every text, and
from the notification / tray texts (uwccd/agentcore.py).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def web_keys():
    """The English keys of the RU dictionary in uwccd/web/i18n.js (RU translates everything, so its keys = all texts)."""
    src = open(os.path.join(ROOT, "uwccd", "web", "i18n.js"), encoding="utf-8").read()
    keys, seen = [], set()
    # "English text": "..."  — the key is any double-quoted string followed by a colon
    for m in re.finditer(r'(?m)^\s*"((?:[^"\\]|\\.)*)"\s*:', src):
        k = m.group(1).replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def main():
    from uwccd.agentcore import TEXT, TRAY
    out = {
        "name": "",                                    # the language's own name, e.g. "Deutsch"
        "web": {k: "" for k in web_keys()},            # window texts: English -> translation
        "service": {k: "" for k in TEXT["en"]},        # notifications: key -> translation of TEXT["en"][key]
        "service_en": TEXT["en"],                      # reference only — delete before shipping
        "tray": {k: "" for k in TRAY["en"]},           # tray menu: key -> translation of TRAY["en"][key]
        "tray_en": TRAY["en"],                         # reference only — delete before shipping
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
