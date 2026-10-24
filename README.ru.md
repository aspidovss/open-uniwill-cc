<p align="center">
  <img src="uwccd/web/icon.svg" width="112" height="112" alt="open-uniwill-cc">
</p>

<h1 align="center">open-uniwill-cc</h1>

<p align="center"><b>Открытый Control Center для ноутбуков на Uniwill — режимы, вентиляторы, мощность, подсветка, СЖО. Без слежки.</b></p>

<p align="center"><a href="README.md">English</a> · <b>Русский</b> · <a href="docs/STRUCTURE.ru.md">Структура проекта</a> · <a href="docs/CLI.ru.md">Командная строка</a></p>

<p align="center">
  <a href="https://github.com/aspidovss/open-uniwill-cc/releases/latest"><img src="https://img.shields.io/badge/%D0%A1%D0%BA%D0%B0%D1%87%D0%B0%D1%82%D1%8C-%D0%BF%D0%BE%D1%81%D0%BB%D0%B5%D0%B4%D0%BD%D0%B8%D0%B9%20%D1%80%D0%B5%D0%BB%D0%B8%D0%B7-e8613c?logo=github&logoColor=white" alt="Скачать"></a>
</p>

<p align="center">
  <a href="https://github.com/aspidovss/open-uniwill-cc/releases/latest"><img src="https://img.shields.io/github/v/release/aspidovss/open-uniwill-cc?label=release&color=2ea44f" alt="release"></a>
  <a href="https://github.com/aspidovss/open-uniwill-cc/releases"><img src="https://img.shields.io/github/downloads/aspidovss/open-uniwill-cc/total?label=downloads&color=2ea44f" alt="downloads"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078d4" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/Linux-DKMS-f0b400?logo=linux&logoColor=white" alt="Linux">
  <img src="https://img.shields.io/badge/Python-3.9+-3776ab?logo=python&logoColor=white" alt="Python 3.9+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-4c1" alt="license MIT"></a>
  <img src="https://img.shields.io/badge/telemetry-none-4c1" alt="telemetry none">
</p>

Открытая замена **Uniwill «Control Center»** (5.52.x) для игровых ноутбуков на платформах Uniwill —
под **Linux** и **Windows**: режимы производительности, кривые вентиляторов, лимиты мощности CPU/GPU,
RGB-подсветка клавиатуры, защита батареи, аппаратные переключатели, а также управление по Bluetooth
**жидкостным охлаждением XMG Oasis** и его аналогами.

**Всё работает в самостоятельной фоновой службе** (`uwccd`: systemd в Linux, служба Windows): она применяет
настройки при загрузке и после сна и держит кривые вентиляторов, лимиты мощности и СЖО без открытого окна — без
оригинальной службы производителя и её приложения из Microsoft Store. Окно, значок в трее и
командная строка `uwccctl` — лишь пульты управления ею.

> **Неофициальная программа.** Не связана с Uniwill и производителями ноутбуков и не поддерживается ими.
> Пишет в контроллер ноутбука (EC) так же, как оригинальная служба, но вы используете её на свой риск.
> Оригинальный Control Center можно вернуть в любой момент (см. «Удаление»).

> [!WARNING]
> **Проект создан с помощью ИИ.** Весь исходный код, документация и прочие тексты в этом репозитории сгенерированы
> ИИ-моделью по запросу и под руководством сопровождающего. Сопровождающий проверил программу на реальном ноутбуке
> (см. «Проверено на»). Прежде чем полагаться на неё, просмотрите код.

<p align="center">
  <img src="docs/screenshots/ru/modes.png" width="49%" alt="Режимы и лимиты мощности">
  <img src="docs/screenshots/ru/fans.png" width="49%" alt="Кривые вентиляторов">
  <img src="docs/screenshots/ru/liquid.png" width="49%" alt="Жидкостное охлаждение">
  <img src="docs/screenshots/ru/light.png" width="49%" alt="Подсветка клавиатуры">
  <img src="docs/screenshots/ru/battery.png" width="49%" alt="Защита аккумулятора">
  <img src="docs/screenshots/info-windows.png" width="49%" alt="Информация о системе в Windows">
</p>

## Возможности

- **Режимы** Office / Gaming / Turbo (и **Custom** с 5 именованными слотами на платформах, где он есть), клавиша режима Fn, Fan Boost;
  **суперпроизводительность** в любом режиме (вентиляторы Турбо, максимальная мощность видеокарты) и **разгон памяти**, если BIOS его поддерживает
- **Лимиты мощности** PL1 / PL2 / PL4, NVIDIA cTGP и Dynamic Boost — в пределах, которые сообщает прошивка
- **Пределы температуры** для каждого режима / профиля: CPU в °C (85–100 °C, по желанию до 60 °C) и целевая температура
  GPU NVIDIA
- **Кривые вентиляторов** CPU и GPU (16 точек), пресеты, сброс к заводским
- **Подсветка клавиатуры**: 17 аппаратных эффектов, цвет каждой клавиши, игровые зоны, программные эффекты, автоотключение;
  **подсветка корпуса** (зоны: сзади, корпус, логотип)
- **Батарея**: режимы защиты, свои пределы заряда, приоритет зарядки по USB-C
- **Переключатели**: блокировка Win, Fn Lock, тачпад, питание USB во сне, включение от сети, MUX (dGPU напрямую), веб-камера
- **Мониторинг**: температуры, загрузка, частоты, вентиляторы, мощность CPU и GPU, память, диски, батарея; история
  за час с экспортом в CSV / JSON / PNG
- **Автоматизация**: режим по источнику питания, оповещения о перегреве (с включением Fan Boost), привязка программ к режимам
- **СЖО** XMG Oasis (LCT21001 Mk1 / LCT22002 Mk2), Eluktronics Liquid Pad Pro, PCS Liquid Series, TUXEDO Aquaris:
  автоматические ступени по температуре, режим «как у ноутбука», подсветка, контроль протока, цикл заполнения
- Интерфейс **на английском и русском**; приложение в трее с уведомлениями в Windows, уведомления рабочего стола в Linux
- **Резервная копия и перенос**: экспорт / импорт кривых вентиляторов (одной или всех), полная копия настроек, импорт из
  оригинального Control Center
- **Проверка обновлений** по релизам GitHub (раз в день, можно выключить); в Windows — загрузка, проверка контрольной
  суммы и установка из окна или трея
- **Диагностический отчёт** для сообщений об ошибках и новых ноутбуков (выбор личных данных, отправка через GitHub или почту)
- Консольная утилита **`uwccctl`** в обеих системах

Полный список с регистрами EC: [docs/FEATURES.md](docs/FEATURES.md) (англ.).

## Поддерживаемые ноутбуки

Программа читает **ID проекта** из EC и поддерживает те же платформы, что и Control Center 5.52.x (MBB):

| Семейство | Проекты |
|---|---|
| PHxT | PH4TRX1, PH4TUX1, PH4TQx1, PH6TRX1, PH6TQxx |
| PHxA | PH4ARxx, PH4AUxx, PH4AXxx, PH6AQxx, PH6ARxx, PH6AGxx, PH4AUxf |
| PHxP | PH4PRxx, PH4PUxx, PH4PGx1, PH4PGx2, PH6PRxx, PH6PGEx, PH6PG0x, PH6PG3x, PH6PG7x (и версии 150 W), PH4AQE3 |
| другие проекты Uniwill с RamFan 1.5 | например `0x10` — платформы с режимом Custom |

Эти шасси продаются под разными брендами (MAIBENBEN, XMG/Schenker, Eluktronics, Mechrevo, Thunderobot и др.).
Проект показывает первая строка `uwccctl status`. **Не поддерживаются:** Tongfang GK/GM (другой EC), Clevo,
ноутбуки Uniwill, которые поставлялись с Control Center 3.x.

**Проверено на**

| Ноутбук | CPU / GPU | Проект | BIOS / EC | Linux | Windows |
|---|---|---|---|---|---|
| MAIBENBEN Tsunami Series | i9-12900HX / NVIDIA | `0x10` | N.1.23A14 / 1.13 | ✅ Ubuntu 24.04 | ✅ Windows 11 24H2 |

Проверили на своём? Пожалуйста, оставьте [отчёт о модели](https://github.com/aspidovss/open-uniwill-cc/issues/new?template=model_report.yml).

**Ваш ноутбук не поддерживается или что-то не работает?** Создайте диагностический отчёт: *Информация →
Диагностический отчёт → Создать отчёт* (или `uwccctl report`). В нём собрано всё, что нужно для добавления платформы:
регистры EC, настройки BIOS, устройства клавиатуры и подсветки корпуса, пределы NVIDIA, журнал — без серийных номеров,
MAC-адресов и имён пользователей (их можно отметить отдельно, если попросят). Приложите архив к issue или отправьте
на **OUCC@aspidov.ru**.

## Скачать

Со страницы [Releases](https://github.com/aspidovss/open-uniwill-cc/releases):

| Файл | Для чего |
|---|---|
| `open-uniwill-cc-windows-<ver>-setup.exe` | Windows 10/11 x64 — установщик |
| `open-uniwill-cc-windows-<ver>-portable.zip` | Windows — то же самое, установка через `install.ps1` |
| `open-uniwill-cc-linux-<ver>.tar.gz` | Linux на базе Ubuntu / Debian (установщик использует apt; разрабатывалось на Ubuntu 24.04) |
| `SHA256SUMS.txt` | контрольные суммы |

## Установка

### Windows

1. Запустите `open-uniwill-cc-windows-<ver>-setup.exe`, оставьте галочку **«Отключить службу оригинального
   Control Center»** (две программы не должны управлять одним EC).
2. В области уведомлений появится значок. Программа **запускается вместе с Windows и скрыта в трее**;
   окно открывается щелчком по значку или через *Пуск → UWCC Control Center*.

Portable zip: распакуйте и выполните в PowerShell `powershell -ExecutionPolicy Bypass -File .\install.ps1` (попросит права администратора).

Что ставится: служба `uwccd` (LocalSystem), `ControlCenter.exe` (трей / окно), `uwccctl.exe` (консоль) и ACPI-драйвер
производителя `UWACPIDriver`, если его ещё нет. Подробнее: [README.windows.md](README.windows.md).

### Linux

```bash
tar xzf open-uniwill-cc-linux-<ver>.tar.gz
cd open-uniwill-cc-<ver>
sudo bash install.sh
```

Установщик показывает [пользовательское соглашение](uwccd/web/eula.ru.txt) и просит его принять (`--accept-agreement` —
для установки без вопросов). Затем выйдите из сеанса и войдите снова (пользователь добавляется в группу `uwcc`) и запустите **Control Center**
из меню или командой `uwcc`. Установщик собирает модуль ядра `uwcc` через DKMS (если он не загрузится, используется `acpi_call`).

**Secure Boot:** если `modprobe uwcc` пишет *Key was rejected*, выполните
`sudo mokutil --import /var/lib/shim-signed/mok/MOK.der`, перезагрузитесь и выберите *Enroll MOK*.
**TUXEDO Control Center** управляет тем же EC — установщик останавливает `tccd`; не запускайте их одновременно.

## Использование

- **Окно** — все настройки; переключатель языка (EN / RU) внизу боковой панели.
- **Трей (Windows)** — правый щелчок: режим, Fan Boost, подсветка, СЖО, язык, обновления, «Запускать вместе с Windows».
- **Консоль** (`uwccctl` в Linux, `uwccctl.exe` в Windows):

```text
uwccctl status                   режим, вентиляторы, температуры, батарея, СЖО
uwccctl monitor --watch 2        датчики каждые 2 с
uwccctl mode office|gaming|turbo|custom
uwccctl profile set custom:0 pl1=65 pl2=90 tcc=10 name=Тихий
uwccctl fan set current cpu 0/45:0 55/50:30 70/65:60 85/80:100
uwccctl boost on|off  /  super on|off  /  ramoc on|off
uwccctl battery limit 80 60      пределы заряда
uwccctl kb effect wave --speed 3 --multi
uwccctl set fn_lock on           любой переключатель или настройка автоматизации (список: uwccctl get)
uwccctl apps add steam gaming    режим, пока запущена программа
uwccctl lc tiers 55:25:8 70:50:8 999:90:11   ступени СЖО
uwccctl export all backup.json   кривые, профили и настройки в файл
uwccctl report                   диагностический отчёт (zip) для сообщений об ошибках и новых ноутбуков
uwccctl --json status            любая команда в JSON, для скриптов
```

Из консоли доступно всё, что меняется в окне. Полный справочник: [docs/CLI.ru.md](docs/CLI.ru.md), `man -L ru uwccctl` в Linux (`man uwccctl` —
на английском; ставится и автодополнение для bash), `uwccctl help КОМАНДА` в обеих системах.

## Удаление / возврат к оригиналу

- **Windows:** *Параметры → Приложения → UWCC Control Center → Удалить* (или `uninstall.ps1`). Управление вентиляторами
  возвращается EC, оригинальная служба `GCUService` включается обратно.
- **Linux:** `sudo bash uninstall.sh` (`--purge` удалит и настройки из `/var/lib/uwcc`).

## Безопасность

- Пишутся только те регистры EC, которые пишет оригинальная служба, и тем же способом. Если EC не сообщает RamFan 1.5,
  режимы и кривые вентиляторов отключены.
- Кривые вентиляторов и ступени СЖО проверяются перед записью; рискованные настройки требуют подтверждения.
- UEFI-переменная `UniWillVariable` записывается только после проверки её раскладки.
- Служба слушает только `127.0.0.1` и требует ключ, доступный локальным пользователям / группе `uwcc`.
  См. [SECURITY.md](SECURITY.md).

## Диагностика, сборка, отладка

[docs/STRUCTURE.ru.md](docs/STRUCTURE.ru.md) — как устроен проект: служба, клиенты, назначение каждого модуля.

[docs/BUILD.md](docs/BUILD.md) — сборка пакетов для Linux и Windows, запуск без железа (`--mock`), отладочный журнал,
где лежат логи, что приложить к отчёту об ошибке.

## Контакты

- Ошибки, вопросы, новые ноутбуки: [GitHub issues](https://github.com/aspidovss/open-uniwill-cc/issues)
- Почта: **OUCC@aspidov.ru** (в том числе для сообщений об уязвимостях, см. [SECURITY.md](SECURITY.md))

## Лицензия

MIT — см. [LICENSE](LICENSE), **кроме** `kernel/` (GPL-2.0), а также `proprietary/` и `uwccd/lighting/oem/`
(файлы производителя и производный от них код, все права у владельцев, включены для совместимости).
Благодарности и проекты, которые помогли: [NOTICE.md](NOTICE.md).

**Пользовательское соглашение** ([English](uwccd/web/eula.en.txt) · [Русский](uwccd/web/eula.ru.txt)) — его показывают
установщики и окно при первом запуске: программа предоставляется «как есть», ответственность за её использование несёт
пользователь, вы подтверждаете право использовать включённые компоненты производителя или заменяете их сами.
