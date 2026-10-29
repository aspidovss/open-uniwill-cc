# uwccctl — справочник командной строки

`uwccctl` (Linux) / `uwccctl.exe` (Windows) управляет службой `uwccd`. Из консоли доступно всё, что меняется в окне:
ноутбуком можно управлять из скриптов, горячих клавиш, по SSH или в системе без рабочего стола.

- Linux: `man -L ru uwccctl` (английская: `man uwccctl`); автодополнение для bash ставит `install.sh`.
- Обе системы: `uwccctl help` и `uwccctl help КОМАНДА`.
- Доступ: ключ `/run/uwcc/token` читают группа `uwcc` (после установки один раз войдите в сеанс заново) и root;
  в Windows — администраторы и пользователь, установивший программу.

```text
uwccctl [--json] КОМАНДА [АРГУМЕНТЫ]
```

Команда без аргументов показывает состояние; с аргументами — меняет его и показывает новое.

## Вывод для скриптов

| | |
|---|---|
| `--json` | в любом месте строки; один документ JSON (`monitor --watch` — объект на строку, NDJSON) |
| ошибки | текст в stderr; с `--json` — `{"error": "..."}` в stdout |
| коды возврата | `0` успех, `1` служба отклонила (диапазон, нет на этом ноутбуке), `2` неверная команда, `3` служба не запущена / нет доступа |
| окружение | `UWCC_PORT` (по умолчанию 47321), `UWCC_TOKEN`, `UWCC_TOKEN_FILE` |

```bash
uwccctl --json monitor | jq .cpu.temp
uwccctl --json monitor --watch 5 >> sensors.ndjson
uwccctl mode turbo || echo "ошибка: $?"
```

## Обзор

| Команда | |
|---|---|
| `status` | модель, режим, профиль, PL, вентиляторы, температуры, батарея, СЖО, переключатели |
| `monitor [--watch [СЕК]]` | датчики один раз или каждые СЕК с (по умолчанию 2) до Ctrl+C |
| `history [csv\|csv-excel\|json] [1m\|5m\|15m\|1h\|24h] [ФАЙЛ]` | записанная история датчиков |

## Производительность

| Команда | |
|---|---|
| `mode [office\|gaming\|turbo\|custom]` | показать / сменить режим |
| `profile [N]` | активный профиль / выбрать ячейку N (с 0) текущего режима |
| `profile list` | все профили, активный отмечен `*` |
| `profile show [ЦЕЛЬ]` | значения профиля |
| `profile set [ЦЕЛЬ] КЛЮЧ=ЗНАЧЕНИЕ ...` | изменить профиль (ключи ниже) |
| `profile reset [ЦЕЛЬ]` | заводские значения и кривая ячейки |
| `boost [on\|off]` | FanBoost |
| `super [on\|off]` | суперпроизводительность (таблица Turbo, максимум cTGP + Dynamic Boost) в любом режиме |
| `ramoc [on\|off]` | разгон ОЗУ; действует после перезагрузки |
| `restore --yes` | заводские профили и таблицы всех режимов |

`ЦЕЛЬ`: `office`, `custom:2` (режим и ячейка с 0) или `Mode4_Profile3`; по умолчанию — активный профиль.

| Ключ | Значение |
|---|---|
| `pl1`, `pl2`, `pl4` | Вт (PL2 поднимается до PL1; PL4 ≥ PL2) |
| `tcc` | °C ниже Tjmax или `off` |
| `ctgp` | настраиваемый TGP NVIDIA, Вт, или `off` |
| `db` | Dynamic Boost, Вт, или `off` |
| `gputemp` | предел температуры ГП, °C, или `off` |
| `fanspeed` | скорость переключения вентилятора 100..12700 об/мин или `off` |
| `name` | имя пользовательской ячейки, до 24 символов |

```bash
uwccctl profile set custom:0 pl1=65 pl2=90 tcc=10 ctgp=off name=Тихий
```

## Таблицы вентиляторов

| Команда | |
|---|---|
| `fan list` | таблицы и профили, которые их используют |
| `fan show [ТАБЛИЦА]` | уровни в виде `ВВЕРХ/ВНИЗ:СКОРОСТЬ` |
| `fan set ТАБЛИЦА cpu\|gpu ТОЧКА ...` | заменить кривую, до 16 точек |
| `fan set ТАБЛИЦА --file ФАЙЛ` | загрузить JSON, сохранённый `fan show --json` |
| `fan separate ТАБЛИЦА on\|off` | раздельные кривые ЦП и ГП |
| `fan reset ТАБЛИЦА` | заводская кривая |

`ТАБЛИЦА`: `M1T1` … `M4T5` или `current`. Точка `ВВЕРХ/ВНИЗ:СКОРОСТЬ` — уровень включается при ВВЕРХ °C, отпускается
ниже ВНИЗ °C, вентилятор работает на СКОРОСТЬ %. Уровень 0 начинается с 0 °C, температуры не убывают, на последнем
уровне не меньше 40 %.

```bash
uwccctl fan set current cpu 0/45:0 55/50:30 70/65:60 85/80:100
```

## Батарея

| Команда | |
|---|---|
| `battery` | режим, пределы, циклы, приоритет Type-C |
| `battery mode full\|balanced\|stationary` | режим защиты |
| `battery limit ВЕРХ [НИЗ]` | прекращать заряд на ВЕРХ % (1..100), возобновлять ниже НИЗ % (1..95) |
| `battery typec on\|off` | заряжать в первую очередь от Type-C |

## Клавиатура и световая полоса

| Команда | |
|---|---|
| `kb` / `kb on\|off` | состояние / питание |
| `kb effects` | эффекты с номерами и поддержкой на этой клавиатуре |
| `kb effect ИМЯ\|N [параметры]` | включить эффект; неуказанные параметры сохраняются |
| `kb effect ИМЯ --try` | эффект, не проверенный на этой клавиатуре (серый в окне) |
| `kb feedback ИМЯ yes\|no` | сработал ли непроверенный эффект (сохраняется для диагностического отчёта) |
| `kb level N` | яркость 0..4 |
| `kb fx` | эффекты BetterRGB (рисует служба): номера, параметры, настройки |
| `kb fx ИМЯ\|N [--light 0..4] [КЛЮЧ=ЗНАЧЕНИЕ ...]` | включить эффект BetterRGB; неуказанные параметры сохраняются |
| `kb fx-config КЛЮЧ=ЗНАЧЕНИЕ ...` | `fps_ac`, `fps_battery` (10..60), `transition`, `transition_ms`, `bar`, `bar_direction`, `bar_start`, `bar_end` |
| `kb fx-calibrate start\|cancel\|reset` / `kb fx-calibrate apply RRGGBB` | калибровка белого (RRGGBB — цвет, который вы видите) |
| `lb [hinge\|base\|logo] on\|off` | зона световой полосы (по умолчанию `hinge`) |
| `lb [ЗОНА] color RRGGBB [ЭФФЕКТ]` | цвет |
| `lb [ЗОНА] effect static\|breathing\|breathing_multi\|wave\|cycle\|rainbow\|colorbreath\|colorwave` | эффект |
| `lb [ЗОНА] light 0..4` | яркость |

Параметры эффекта: `--light 0..4`, `--speed 0..4`, `--dir right|left|up|down`, `--color RRGGBB[,RRGGBB...]`,
`--multi` / `--no-multi`, `--text ТЕКСТ` (Alphabet).

```bash
uwccctl kb effect wave --speed 3 --multi
uwccctl kb effect single --color 00A0FF --light 2
uwccctl kb fx rain density=4 color_count=2 colors=5080FF,FFFFFF
uwccctl kb fx-config transition=ripple_center bar=battery
```

Эффекты BetterRGB: [LIGHTING.ru.md](LIGHTING.ru.md).

Control Center 3.0 / Clevo (экспериментально): `uwccctl clevo …` — см. [CLEVO.ru.md](CLEVO.ru.md).

## Переключатели и автоматизация

`uwccctl get [КЛЮЧ]`, `uwccctl set КЛЮЧ ЗНАЧЕНИЕ` (логические: `on` / `off`).

| Ключи | Значения |
|---|---|
| `winkey_lock` `fn_lock` `usb_charger` `touchpad_toggle` `touchpad_enabled` `ac_recovery` `dgpu_direct` `bluetooth` `wifi` `webcam` `osd` `lc_hwoc` `kb_picture_modes` `tcc_extended` `history_record` `update_check` `debug` `mem_oc` `super_performance` | on / off |
| `kb_timeout` | секунды 0..3600, 0 = никогда |
| `alerts` `overheat_boost` `kb_off_on_battery` `ppd_sync` | on / off |
| `cpu_alert` `gpu_alert` | 60..105 °C |
| `mode_on_ac` | `keep`, `previous` или режим |
| `mode_on_battery` | `keep` или режим |
| `lightbar_trigger` | любое значение: переключает полосу, как горячая клавиша |
| `lang` | `en` / `ru` |
| `fan_manager` | `auto` (по проекту), `cml`, `std`; служба перезапускается |

Привязка к программам: `apps`, `apps add ПРОЦЕСС РЕЖИМ`, `apps remove ПРОЦЕСС`, `apps enable|disable ПРОЦЕСС`.

## Водяное охлаждение

| Команда | |
|---|---|
| `lc [status]` / `lc scan` | состояние / поиск |
| `lc connect АДРЕС` / `lc disconnect [--forget]` | подключить и запомнить / отключить |
| `lc mode auto\|laptop\|ec\|low\|medium\|high\|off` | режим |
| `lc manual ВЕНТ ПОМПА` | вентилятор 0..100 %, помпа 7/8/11/12 В (0 = выкл) |
| `lc tiers НИЖЕ:ВЕНТ:ПОМПА ...` | 1..8 ступеней автоматического режима |
| `lc set КЛЮЧ ЗНАЧЕНИЕ` | `temp_source max\|cpu\|gpu`, `delay_up`/`delay_down` 0..300 с, `smooth` `notify_flow` `flow_guard` `boost_fan` `boost_pump` on/off |
| `lc idle on\|off [off_below= off_after= on_above= on_after= min_run=]` | останавливать помпу при низкой температуре |
| `lc rgb RRGGBB [РЕЖИМ]` / `lc rgb off` | static, breathe, rainbow, breathe_rainbow, spiral, rotating_rainbow, color_wave |
| `lc prime [stop]` / `lc suspend` | заполнение (~68 с) / сон |

## Служба

| Команда | |
|---|---|
| `export fans\|all [ФАЙЛ]` / `import ФАЙЛ [fans,profiles,settings] [--force]` | резервная копия / восстановление |
| `report [ФАЙЛ] [--private serial,uuid,mac,names,apps] [--sections СПИСОК] [--full]` | диагностический архив |
| `lang en\|ru` / `debug [on\|off]` | язык / подробный журнал |
| `version` / `update [check\|install]` | версия / новый выпуск (установка: Windows) |
| `restart` / `resume` | перезапуск службы / применить настройки заново |
| `lighting` / `nvram` / `ec read АДРЕС` | диагностика |
| `driver` | способ доступа к EC, OEM-драйвер, функции WMI (Windows) |
| `driver use auto\|oem\|wmi [--accept-risks]` | OEM-драйвер + WMI (по умолчанию) / только OEM / только WMI (открытая, не рекомендуется, бета) |
| `driver config export\|import ФАЙЛ` / `driver config reset` / `driver test` | настройки WMI `ec_wmi.json` ([EC/WMI-config.ru.md](EC/WMI-config.ru.md)), быстрая проверка |
| `driver unlock [МИН]` / `driver lock` | открыть настройки менеджера EC для окна (администратор / sudo) |
| `driver monitor oem\|wmi\|all on\|off` | мониторинг через способ доступа / весь мониторинг |
| `driver platform [export\|import ФАЙЛ\|reset\|apply-draft]` | профиль платформы ([EC/Platforms.ru.md](EC/Platforms.ru.md)) |
| `driver selfcheck [1\|2] [--export ФАЙЛ]` | самопроверка: только чтение / с записью (администратор, от сети) |
| `ec …` | то же, что `driver …` (менеджер EC); `ec read АДРЕС` читает один регистр |
| `ec fetch-driver` / `ec check-driver` / `ec install-driver [--accept-risks]` | OEM-драйвер: скопировать из хранилища драйверов Windows, проверить, установить ([EC/OEM-driver.ru.md](EC/OEM-driver.ru.md)) |
| `driver-verify ПАПКА [--json]` | проверка любого пакета драйвера без службы (коды 0 / 10 / 11 / 12) |
| `ec-direct read АДРЕС [N]` / `ec-direct dump БАЗА` | EC без службы (root) |
| `release` | вернуть управление вентиляторами EC (root, удаление) |
