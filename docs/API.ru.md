# API службы — контракт для скриптов и интеграций

[English](API.md) · **Русский**

Служба `uwccd` слушает **`http://127.0.0.1:47321`** (порт меняется переменной `UWCC_PORT`) и обслуживает окно,
трей, `uwccctl` **и ваши скрипты** по обычному HTTP + JSON. Эта страница — контракт: что стабильно, как
авторизоваться, все конечные точки и все события. Экспортёр для системы мониторинга — это ~40 строк:
[`examples/zabbix_exporter.py`](../examples/zabbix_exporter.py).

## Стабильность

`GET /api/state` возвращает `"api": {"version": 1, "program": "<версия>"}`.

- **`api.version` растёт только при ломающем изменении**: когда конечная точка или поле из этого документа
  убирается или меняет смысл. Новые точки, события и поля появляются без смены версии — неизвестное игнорируйте.
- Обещание касается всего, что описано здесь. Поля, *не* описанные здесь, могут меняться в любом выпуске.
- Имена событий — это `uwccd/bus.py` → `EVENTS`; новое событие сначала добавляется туда и сюда.

## Авторизация

Каждому запросу `/api/` нужен ключ доступа — служба пишет его при старте в:

| ОС | Файл ключа |
|---|---|
| Linux | `/run/uwcc/token` (читается группой `uwcc`) |
| Windows | `%ProgramData%\UWCC\run\token` |

Передавайте его заголовком **`X-UWCC-Token: <ключ>`** (для `/api/events` работает и `?token=`).
Сервер отвечает только на 127.0.0.1 и проверяет заголовок `Host:`.

## Конечные точки (стабильный набор)

| Метод, путь | Возвращает / делает |
|---|---|
| `GET /api/state` | всё сразу: `api`, `platform`, `power`, `settings`, `battery`, `keyboard`, `liquid`, `afterburner`, `update`, `modules`, `capabilities`, … |
| `GET /api/monitor` | один отсчёт датчиков: температуры, вентиляторы, загрузка, мощность |
| `GET /api/history?range=1h` | записанная история датчиков (`1m 5m 15m 1h 24h`) |
| `GET /api/events` | поток событий (SSE, ниже); `&monitor=1` добавляет событие `monitor` на каждый отсчёт |
| `GET /api/langs` | языки интерфейса: `{languages: [{code, name, builtin}]}` |
| `GET /api/lang/<код>` | один файл языка (docs/TRANSLATING.md) |
| `POST /api/mode` | `{mode: 0..3}` — переключить режим ноутбука |
| `POST /api/fanboost` | `{on: bool}` |
| `POST /api/setting` | `{key, value}` — любой переключатель (ключи: `uwccctl get`) |
| `POST /api/module` | `{name, enabled}` — включить/выключить модуль службы; отвечает `{modules: [...]}` |
| `POST /api/battery` | `{limit_up?, limit_down?, health_mode?}` |
| `POST /api/lc/...` | СЖО: `scan`, `connect`, `disconnect`, `config` |
| `POST /api/afterburner` | `{action: "apply", slot}` и остальные действия карточки |

Окно использует больше точек, чем в таблице; они работают, но в обещание пока не входят.

### Возможности (capabilities)

`state.capabilities` — **реестр возможностей**: один явный ответ «что есть на этом ноутбуке». Этот же список
читают окно («Информация → Функции на этом ноутбуке»), трей и `uwccctl caps`:

```json
"capabilities": {"modes": {"available": true, "source": "ec"},
                 "power_limits": {"available": true, "source": "driver", "detail": "from the firmware table SMRW"},
                 "liquid_cooler": {"available": false, "source": "none", "detail": "python3-bleak is not installed"},
                 ...}
```

`source`: `ec` — биты возможностей EC этого ноутбука; `profile` — профиль платформы; `driver` — зависит от пути
доступа (OEM-драйвер / модуль ядра или WMI); `os` — даёт ОС или другая программа; `none` — отсутствует.

### Модули

`state.modules` перечисляет отключаемые части службы (`uwccd/modules.py`): `name`, `title`, `available`,
`enabled`, `running`, `live` (`false`: переключение вступает в силу при следующем запуске службы). Переключение:
`POST /api/module` или `uwccctl modules NAME on|off`; выбор хранится в настройках.

## События (`GET /api/events`)

Server-sent events: каждая строка — `data: {"type": "<вид>", "data": {...}, "t": <unix-время>}`.
Внутри службы их несёт та же шина (`uwccd/bus.py`); модули подписываются на неё, а не вызывают друг друга.

| Вид | Значение |
|---|---|
| `status` | что-то изменилось — перечитайте `/api/state` |
| `mode` | применён режим `{mode, slot?, osd}` |
| `fanboost` | переключена турбовентиляция `{on}` |
| `setting` | изменилась настройка `{key, value}` |
| `monitor` | отсчёт датчиков (только с `?monitor=1`) |
| `ac` | сменился источник питания `{online}` |
| `overheat`, `overheat_boost` | температура держится выше предела / включён Fan Boost |
| `lc` | СЖО `{event: connected / disconnected / flow_fault / hwoc, ...}` |
| `keyboard`, `kb_level` | состояние / уровень подсветки клавиатуры |
| `load_rule` | сработало правило автоматики `{rule, mode, slot}` |
| `update` | доступно обновление `{version, url, optional}` |
| `busy` | ход долгой операции `{ops}` |
| `modules` | переключён модуль `{name, enabled, running}` |
| `afterburner`, `clevo`, `leishen`, `selfcheck`, `detect`, `admin`, `osd`, `toast`, … | остальное из `bus.EVENTS` |

Неизвестные виды нужно игнорировать — новые появляются без смены версии API.

## Как написать интеграцию

1. Прочитайте файл ключа, один раз вызовите `GET /api/state`, дальше либо опрашивайте `GET /api/monitor`, либо
   держите открытым `GET /api/events`.
2. Уважайте `capabilities` — не считайте, что у каждого ноутбука есть вентилятор ГП или СЖО.
3. Примеры: [`examples/zabbix_exporter.py`](../examples/zabbix_exporter.py) (Zabbix / любой агент, умеющий
   запустить команду), `uwccctl --json status` для скриптов оболочки.

Пример на Python:

```python
import json, urllib.request
TOKEN = open("/run/uwcc/token").read().strip()        # Windows: %ProgramData%\UWCC\run\token
req = urllib.request.Request("http://127.0.0.1:47321/api/monitor", headers={"X-UWCC-Token": TOKEN})
m = json.load(urllib.request.urlopen(req, timeout=5))
print(m["cpu"]["temp"], m["fans"]["cpu_rpm"])
```
