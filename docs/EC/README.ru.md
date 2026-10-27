# EC — MAIBENBEN Tsunami X629

[English](README.md) · **Русский**

Документация и инструмент для встроенного контроллера (EC) ноутбука MAIBENBEN Tsunami X629 (Uniwill, проект `0x10`).

| Файл | Что внутри |
|---|---|
| [Registers.ru.md](Registers.ru.md) | описание регистров EC: адреса, биты, значения на Tsunami, таблица вентиляторов, СЖО, методы прошивки, примеры |
| [WMI-vs-Driver.ru.md](WMI-vs-Driver.ru.md) | сравнение доступа через OEM-драйвер и через WMI: что работает, скорость, чего стоит отказ от драйвера |
| [WMI-config.ru.md](WMI-config.ru.md) | настройки доступа через WMI (`ec_wmi.json`): все ключи, функции, настройка для другого ноутбука |
| [Platforms.ru.md](Platforms.ru.md) | профили платформ, самопроверка, менеджер EC, права администратора, жёсткие потолки, переключатели мониторинга |
| `ec_tool.py` | тестовая программа (вывод на английском) |
| `ec_tool.json` | настройки программы по умолчанию |

## ec_tool.py

Нужны Python 3 и, для WMI, `pywin32` (`python -m pip install pywin32`). Запускать от имени администратора.

```
python ec_tool.py COMMAND [ARGS] [--backend driver|wmi|service|auto] [options]
```

| Команда | Что делает |
|---|---|
| `info` | сводка: проект, возможности, режим, мощность, вентиляторы, батарея, СЖО |
| `read ADDR …` | чтение; диапазоны `0x783-0x787` |
| `dump START [LEN]` | шестнадцатеричный дамп |
| `decode [ГРУППА …]` | все известные регистры с расшифровкой; группы — `groups` |
| `fantable` | таблица вентиляторов `0xF00–0xF5F` по уровням |
| `watch ADDR …` | значения каждые `--interval` с, `--count`, `--csv FILE` |
| `write ADDR VALUE` / `bit ADDR BIT on\|off` | запись (только регистры из списка «запись»; `--force` — на свой риск; `--restore SEC` — вернуть через SEC с) |
| `compare [ADDR …] --with BACKEND` | сравнить два канала доступа |
| `bench [N]` | скорость чтения |
| `pwup LEVEL` | вызвать `PWUP(level)` (только OEM-драйвер) |

Каналы: `driver` — OEM-драйвер; `wmi` — штатный WMI Windows; `service` — служба open-uniwill-cc (только чтение);
`auto` — драйвер, если есть, иначе WMI.

### Настройки `ec_tool.json`
| Ключ | По умолчанию | Что это |
|---|---|---|
| `backend` | `auto` | канал по умолчанию |
| `compare_with` | `driver` | второй канал для `compare` |
| `wmi_instance` | `1_1` | экземпляр `AcpiTest_MULong` |
| `service_port` | `47321` | порт службы |
| `interval`, `count` | `2.0`, `0` | для `watch` (`0` — до Ctrl+C) |
| `watch` | обороты, скважность, режим, СЖО | регистры `watch` без аргументов |
| `writable_extra` | `[]` | дополнительно разрешить запись в эти регистры |
| `writable_deny` | `0x7C7`, `0xF5D–0xF5F` | запретить запись даже в «записываемые» |
| `names` | | свои подписи для неизвестных регистров |

### Примеры
```powershell
python ec_tool.py info
python ec_tool.py --backend wmi decode power fans
python ec_tool.py read 0x783-0x787 --json
python ec_tool.py fantable
python ec_tool.py watch --interval 1 --count 60 --csv ec.csv
python ec_tool.py bit 0x74E 4 on --restore 5        # Fn Lock на 5 секунд
python ec_tool.py --backend wmi compare --with driver
python ec_tool.py --backend wmi bench 20
```
