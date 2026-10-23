# open-uniwill-cc

[English](README.md) · **Русский**

Открытая замена **Uniwill «Control Center»** (5.52.x) для игровых ноутбуков на платформах Uniwill —
под **Linux** и **Windows**: режимы производительности, кривые вентиляторов, лимиты мощности CPU/GPU,
RGB-подсветка клавиатуры, защита батареи, аппаратные переключатели, а также управление по Bluetooth
**жидкостным охлаждением XMG Oasis** и его аналогами.

> **Неофициальная программа.** Не связана с Uniwill и производителями ноутбуков и не поддерживается ими.
> Пишет в контроллер ноутбука (EC) так же, как оригинальная служба, но вы используете её на свой риск.
> Оригинальный Control Center можно вернуть в любой момент (см. «Удаление»).

<p align="center">
  <img src="docs/screenshots/modes.png" width="49%" alt="Режимы и лимиты мощности">
  <img src="docs/screenshots/fans.png" width="49%" alt="Кривые вентиляторов">
  <img src="docs/screenshots/liquid.png" width="49%" alt="Жидкостное охлаждение">
  <img src="docs/screenshots/info-windows.png" width="49%" alt="Информация о системе в Windows">
</p>

## Возможности

- **Режимы** Office / Gaming / Turbo (и **Custom** с 5 именованными слотами на платформах, где он есть), клавиша режима Fn, Fan Boost
- **Лимиты мощности** PL1 / PL2 / PL4, смещение TCC, NVIDIA cTGP и Dynamic Boost — в пределах, которые сообщает прошивка
- **Кривые вентиляторов** CPU и GPU (16 точек), пресеты, сброс к заводским
- **Подсветка клавиатуры**: 17 аппаратных эффектов, цвет каждой клавиши, игровые зоны, программные эффекты, автоотключение
- **Батарея**: режимы защиты, свои пределы заряда, приоритет зарядки по USB-C
- **Переключатели**: блокировка Win, Fn Lock, тачпад, питание USB во сне, включение от сети, MUX (dGPU напрямую), веб-камера
- **Мониторинг**: температуры, загрузка, частоты, вентиляторы, мощность, память, диски, батарея, история за час
- **Автоматизация**: режим по источнику питания, оповещения о перегреве (с включением Fan Boost), привязка программ к режимам
- **СЖО** XMG Oasis (LCT21001 Mk1 / LCT22002 Mk2), Eluktronics Liquid Pad Pro, PCS Liquid Series, TUXEDO Aquaris:
  автоматические ступени по температуре, режим «как у ноутбука», подсветка, контроль протока, цикл заполнения
- Интерфейс **на английском и русском**; приложение в трее с уведомлениями в Windows, уведомления рабочего стола в Linux
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

Затем выйдите из сеанса и войдите снова (пользователь добавляется в группу `uwcc`) и запустите **Control Center**
из меню или командой `uwcc`. Установщик собирает модуль ядра `uwcc` через DKMS (если он не загрузится, используется `acpi_call`).

**Secure Boot:** если `modprobe uwcc` пишет *Key was rejected*, выполните
`sudo mokutil --import /var/lib/shim-signed/mok/MOK.der`, перезагрузитесь и выберите *Enroll MOK*.
**TUXEDO Control Center** управляет тем же EC — установщик останавливает `tccd`; не запускайте их одновременно.

## Использование

- **Окно** — все настройки; переключатель языка (EN / RU) внизу боковой панели.
- **Трей (Windows)** — правый щелчок: режим, Fan Boost, подсветка, СЖО, язык, «Запускать вместе с Windows».
- **Консоль** (`uwccctl` в Linux, `uwccctl.exe` в Windows):

```text
uwccctl status                   режим, вентиляторы, температуры, батарея, СЖО
uwccctl mode office|gaming|turbo|custom
uwccctl profile 1                профиль текущего режима
uwccctl boost on|off             Fan Boost
uwccctl kb off|on|effect N       подсветка клавиатуры
uwccctl lc scan / connect ADDR   СЖО: поиск / подключение
uwccctl lc mode auto|ec|low|medium|high|off
uwccctl lang en|ru
uwccctl debug on|off             подробный журнал службы
```

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

[docs/BUILD.md](docs/BUILD.md) — сборка пакетов для Linux и Windows, запуск без железа (`--mock`), отладочный журнал,
где лежат логи, что приложить к отчёту об ошибке.

## Лицензия

MIT — см. [LICENSE](LICENSE), **кроме** `kernel/` (GPL-2.0), а также `proprietary/` и `uwccd/lighting/oem/`

> **AI WARING**
> AI-generated project. All source code, documentation and other text in this repository were generated by an AI model at the request and under the direction of the maintainer.
> The maintainer tested the program with a real camera. Review the code before relying on it.
(файлы производителя и производный от них код, все права у владельцев, включены для совместимости).
Благодарности и проекты, которые помогли: [NOTICE.md](NOTICE.md).
