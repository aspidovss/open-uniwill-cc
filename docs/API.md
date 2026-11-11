# Service API — the contract for scripts and integrations

**English** · [Русский](API.ru.md)

The service `uwccd` listens on **`http://127.0.0.1:47321`** (set `UWCC_PORT` to change it) and serves the window,
the tray, `uwccctl` **and your scripts** over plain HTTP + JSON. This page is the contract: what is stable, how to
authenticate, every endpoint and every event. An exporter for a monitoring system is ~40 lines —
see [`examples/zabbix_exporter.py`](../examples/zabbix_exporter.py).

## Stability

`GET /api/state` returns `"api": {"version": 1, "program": "<version>"}`.

- **`api.version` grows only when something breaks**: an endpoint or field below is removed or changes meaning.
  New endpoints, events and fields appear without a version change — ignore what you do not know.
- Everything on this page is covered by that promise. Fields *not* documented here may change in any release.
- The event names are `uwccd/bus.py` → `EVENTS`; a new event is added there and here first.

## Authentication

Every `/api/` request needs the access token — the service writes it on start to:

| OS | Token file |
|---|---|
| Linux | `/run/uwcc/token` (readable by group `uwcc`) |
| Windows | `%ProgramData%\UWCC\run\token` |

Send it as the header **`X-UWCC-Token: <token>`** (for `/api/events` the query `?token=` also works).
The server answers only on 127.0.0.1 and checks the `Host:` header.

## Endpoints (the stable set)

| Method, path | Returns / does |
|---|---|
| `GET /api/state` | everything at once: `api`, `platform`, `power`, `settings`, `battery`, `keyboard`, `liquid`, `afterburner`, `update`, `modules`, `capabilities`, … |
| `GET /api/monitor` | one sensor sample: temperatures, fans, load, power |
| `GET /api/history?range=1h` | recorded sensor history (`1m 5m 15m 1h 24h`) |
| `GET /api/events` | the event stream (SSE, see below); `&monitor=1` adds a `monitor` event per sample |
| `GET /api/langs` | interface languages: `{languages: [{code, name, builtin}]}` |
| `GET /api/lang/<code>` | one language file (docs/TRANSLATING.md) |
| `POST /api/mode` | `{mode: 0..3}` — switch the laptop mode |
| `POST /api/fanboost` | `{on: bool}` |
| `POST /api/setting` | `{key, value}` — any switch (`uwccctl get` lists the keys) |
| `POST /api/module` | `{name, enabled}` — switch a service module; answers `{modules: [...]}` |
| `POST /api/battery` | `{limit_up?, limit_down?, health_mode?}` |
| `POST /api/lc/...` | liquid cooler: `scan`, `connect`, `disconnect`, `config` |
| `POST /api/afterburner` | `{action: "apply", slot}` and the other actions of the card |

The window uses more endpoints than this table; they work but are not part of the promise yet.

### Capabilities

`state.capabilities` is the **capability registry**: one explicit answer to "what does this laptop have", the same
list the window (Information → *Functions on this laptop*), the tray and `uwccctl caps` read:

```json
"capabilities": {"modes": {"available": true, "source": "ec"},
                 "power_limits": {"available": true, "source": "driver", "detail": "from the firmware table SMRW"},
                 "liquid_cooler": {"available": false, "source": "none", "detail": "python3-bleak is not installed"},
                 ...}
```

`source`: `ec` — the EC capability bits of this laptop; `profile` — the platform profile; `driver` — depends on
the access path (OEM driver / kernel module vs WMI); `os` — the OS or another program provides it; `none` — absent.

### Modules

`state.modules` lists the switchable parts of the service (`uwccd/modules.py`): `name`, `title`, `available`,
`enabled`, `running`, `live` (`false`: the switch takes effect at the next service start). Switch with
`POST /api/module` or `uwccctl modules NAME on|off`; the choice is kept in the settings.

## Events (`GET /api/events`)

Server-sent events: each line is `data: {"type": "<kind>", "data": {...}, "t": <unix time>}`.
Inside the service the same bus carries them (`uwccd/bus.py`); modules subscribe instead of calling each other.

| Kind | Meaning |
|---|---|
| `status` | something changed — re-read `/api/state` |
| `mode` | mode applied `{mode, slot?, osd}` |
| `fanboost` | Fan Boost switched `{on}` |
| `setting` | a setting changed `{key, value}` |
| `monitor` | sensor sample (only with `?monitor=1`) |
| `ac` | power source changed `{online}` |
| `overheat`, `overheat_boost` | temperature held over the limit / Fan Boost forced |
| `lc` | liquid cooler `{event: connected / disconnected / flow_fault / hwoc, ...}` |
| `keyboard`, `kb_level` | keyboard backlight state / level |
| `load_rule` | an automation rule fired `{rule, mode, slot}` |
| `update` | an update is available `{version, url, optional}` |
| `busy` | long operation progress `{ops}` |
| `modules` | a module was switched `{name, enabled, running}` |
| `afterburner`, `clevo`, `leishen`, `selfcheck`, `detect`, `admin`, `osd`, `toast`, … | the rest of `bus.EVENTS` |

Unknown kinds must be ignored — new ones appear without an API version change.

## Writing an integration

1. Read the token file, call `GET /api/state` once, then either poll `GET /api/monitor` or hold `GET /api/events` open.
2. Honour `capabilities` — do not assume every laptop has a GPU fan or a liquid cooler.
3. Examples: [`examples/zabbix_exporter.py`](../examples/zabbix_exporter.py) (Zabbix / any agent that runs a
   command), `uwccctl --json status` for shell scripts.

Python example:

```python
import json, urllib.request
TOKEN = open("/run/uwcc/token").read().strip()        # Windows: %ProgramData%\UWCC\run\token
req = urllib.request.Request("http://127.0.0.1:47321/api/monitor", headers={"X-UWCC-Token": TOKEN})
m = json.load(urllib.request.urlopen(req, timeout=5))
print(m["cpu"]["temp"], m["fans"]["cpu_rpm"])
```
