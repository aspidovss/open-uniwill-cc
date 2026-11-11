#!/usr/bin/env python3
"""Sensors of open-uniwill-cc for a monitoring system — an example of an "outside plugin" (docs/API.md).

Reads one sample from the service API and prints it flat, one `key value` per line — the format Zabbix
(UserParameter / zabbix_sender), Prometheus textfile collectors and plain scripts all digest. Needs nothing but
Python; works as any user in group `uwcc` (Linux) or any user (Windows).

    $ python3 zabbix_exporter.py
    uwcc.cpu.temp 52
    uwcc.cpu.power_w 17.3
    uwcc.fans.cpu_rpm 1729
    uwcc.mode 1
    ...

    $ python3 zabbix_exporter.py uwcc.cpu.temp        # one value (Zabbix UserParameter)
    52

Zabbix agent, one line in the agent configuration:

    UserParameter=uwcc[*],/usr/bin/python3 /opt/uwcc/examples/zabbix_exporter.py uwcc.$1

Then items like `uwcc[cpu.temp]`, `uwcc[fans.cpu_rpm]`, `uwcc[battery.percent]`.
"""
import json
import os
import sys
import urllib.request

PORT = int(os.environ.get("UWCC_PORT", "47321"))
TOKEN_FILE = (os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UWCC", "run", "token")
              if sys.platform == "win32" else "/run/uwcc/token")


def api(path):
    tok = open(TOKEN_FILE).read().strip()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/{path}", headers={"X-UWCC-Token": tok})
    return json.load(urllib.request.urlopen(req, timeout=5))


def flat(prefix, v, out):
    if isinstance(v, dict):
        for k, x in v.items():
            flat(f"{prefix}.{k}", x, out)
    elif isinstance(v, bool):
        out[prefix] = int(v)
    elif isinstance(v, (int, float)) and v is not None:
        out[prefix] = v


def collect():
    out = {}
    flat("uwcc", api("monitor"), out)                       # temperatures, fans, load, power, battery
    st = api("state")
    out["uwcc.mode"] = st["power"].get("mode")
    out["uwcc.fan_boost"] = int(bool(st["power"].get("fan_boost")))
    lc = st.get("liquid") or {}
    if (st.get("capabilities", {}).get("liquid_cooler") or {}).get("available"):
        out["uwcc.lc.connected"] = int(bool(lc.get("connected")))
        for k in ("temp", "fan", "pump", "flow"):               # coolant °C, fan %, pump V, flow ticks
            if lc.get(k) is not None:
                flat(f"uwcc.lc.{k}", lc[k], out)
    return out


def main():
    out = collect()
    if len(sys.argv) > 1:                                   # one key: Zabbix UserParameter mode
        key = sys.argv[1]
        if key not in out:
            print("ZBX_NOTSUPPORTED: no such key", file=sys.stderr)
            return 1
        print(out[key])
        return 0
    for k, v in out.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
