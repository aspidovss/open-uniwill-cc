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
Сервер отвечает только на 127.0.0.1 и проверяет заголовок `Host:`; с 1.8.2.0 он также отклоняет запросы, у которых
`Origin:` — другой сайт, поэтому страница, открытая в браузере, не может управлять службой. `GET /api/version`
отвечает без ключа: `{"api": {...}, "external": bool}`.

Этот ключ — для собственных клиентов программы (окно, трей, `uwccctl`). Для ваших скриптов и других компьютеров
используйте **внешний ключ** — см. [Внешний доступ](#внешний-доступ-настройки--api) ниже.

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
| `POST /api/flydigi/...` | кулер Flydigi BS (1.8.2.7): `config` `{mode: curve/rpm/gear/stop/device, rpm, gear, level, curve, temp_source, hysteresis, min_change, ramp_up, ramp_down}`, `device` `{rgb, gear_light, power_on_start, smart_start_stop}`, `search` (BS1 по Bluetooth LE), `forget`, `refresh`; состояние — в `state.flydigi` |
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
доступа (OEM-драйвер / модуль ядра или WMI); `os` — даёт ОС или другая программа; `user` — включено пользователем
поверх профиля (разблокировано); `none` — отсутствует.

С 1.8.2.0 недоступная возможность сообщает **почему** (`reason`) и, если её можно включить, **как** (`unlock`):

```json
"fan_tables": {"available": false, "source": "profile", "reason": "wmi_feature_off",
               "unlock": {"type": "wmi_feature", "key": "fan_tables", "risk": true, "restart": true}}
```

`reason`: `no_hardware`, `no_fan_control`, `module_off`, `wmi_feature_off`, `writes_off`, `wmi_consent`,
`oem_missing`, `no_driver`, `not_installed`, `locked`, `no_custom`, `no_events`, `modes_only`, `limit_only`. `unlock.type`: `module` (модуль службы), `wmi_feature`
(функция, которую профиль платформы держит выключенной на пути WMI), `consent` (команды Clevo / Leishen), `page`
(открыть Менеджер EC). Окно делает элементы недоступной функции неактивными и показывает кнопку разблокировки;
`risk: true` — сначала показывается предупреждение. Выполняет `POST /api/unlock {type, key, enabled}` (только ключ
окна); у разблокированной пользователем возможности есть `lock` с обратным действием. Рискованные разблокировки
пишутся в журнал и перечисляются в диагностическом отчёте.

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
| `flydigi` | кулер Flydigi BS `{event: connected / disconnected / state}` (1.8.2.7) |
| `keyboard`, `kb_level` | состояние / уровень подсветки клавиатуры |
| `load_rule` | сработало правило автоматики `{rule, mode, slot}` |
| `update` | доступно обновление `{version, url, optional}` |
| `busy` | ход долгой операции `{ops}` |
| `modules` | переключён модуль `{name, enabled, running}` |
| `afterburner`, `clevo`, `leishen`, `selfcheck`, `detect`, `admin`, `osd`, `toast`, … | остальное из `bus.EVENTS` |

Неизвестные виды нужно игнорировать — новые появляются без смены версии API.

## Внешний доступ (Настройки → API)

По умолчанию выключен. «Настройки → API» включает **отдельный ключ** для скриптов, Home Assistant, сервера
мониторинга и т. п. и по желанию — приём подключений из локальной сети. Для изменения этих настроек нужны права
администратора.

| Настройка | Значение |
|---|---|
| Разрешить внешний API | выкл.: внешний ключ отклоняется везде |
| Доступ: **только чтение** | `GET /api/version`, `/api/state`, `/api/monitor`, `/api/history`, `/api/events`, `/api/langs`, `/api/lang/<код>` |
| Доступ: **полный** | чтение + `POST /api/mode`, `/api/profile`, `/api/fanboost`, `/api/setting`, `/api/module`, `/api/battery`, `/api/lightbar`, `/api/keyboard/power`, `/level`, `/colour`, `/effect`, `/api/lc/...`, `/api/flydigi/...`, `/api/afterburner` |
| Ключ | `uwx_…`, показывается **один раз** при создании; служба хранит только его SHA-256. «Создать новый ключ» отзывает старый |
| Доступ из локальной сети | второй приёмник на `0.0.0.0:<порт>` (по умолчанию **47322**) |
| Разрешённые адреса | IPv4-адреса или сети (`192.168.1.0/24`, `192.168.1.20`); остальным — `403` |
| HTTPS | включён по умолчанию: самоподписанный сертификат, созданный службой; сверяйте его отпечаток SHA-256 со страницы |

Передавайте ключ заголовком **`Authorization: Bearer <ключ>`** (или `X-UWCC-Token`). В адресе (URL) на сетевом
приёмнике — никогда.

Даже **полный** ключ не даёт доступа к: путям администратора (доступ к EC, настройки WMI, профили платформ,
самопроверка с записью), разблокировкам и согласиям (`/api/unlock`, `clevo_writes`, `leishen_writes`,
`eula_accepted`, непроверенные эффекты клавиатуры), рискованным переключателям (`super_performance`, `tcc_extended`,
`mem_oc`, `lc_hwoc`, `fan_manager`, `monitoring`), обновлениям, импорту / экспорту, отчётам, прямому доступу к EC и
самим настройкам API. На такие запросы — `403`.

Сетевой приёмник отвечает **только на `/api/`** (окна там нет), принимает только внешний ключ и после **10 неверных
ключей за 10 минут блокирует адрес на 5 минут** (`429`). В Windows служба добавляет входящее правило брандмауэра
*open-uniwill-cc API* для порта и разрешённых адресов и удаляет его, когда приёмник останавливается; в Linux при
включённом брандмауэре откройте порт сами (`sudo ufw allow from 192.168.1.0/24 to any port 47322 proto tcp`).
На странице видны последние внешние запросы (время, адрес, запрос, ответ) и заблокированные адреса.

> [!WARNING]
> Любой в разрешённых сетях, у кого есть ключ, может им воспользоваться. Включайте доступ из сети только в сети,
> которой доверяете. Без HTTPS ключ передаётся по сети открытым текстом.

```bash
curl -s -H "Authorization: Bearer $UWX" http://127.0.0.1:47321/api/monitor            # этот компьютер
curl -sk -H "Authorization: Bearer $UWX" https://192.168.1.5:47322/api/state           # другой компьютер (-k: самоподписанный)
curl -sk -H "Authorization: Bearer $UWX" -d '{"mode": 0}' https://192.168.1.5:47322/api/mode   # полный доступ
```

Чтобы проверять сертификат вместо `-k`, сверьте отпечаток
(`openssl s_client -connect 192.168.1.5:47322 </dev/null | openssl x509 -noout -fingerprint -sha256`) или добавьте в
доверенные `cert.pem` службы (`<data>/api-tls/cert.pem`; его имена — `localhost`, имя компьютера и его адреса).

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
