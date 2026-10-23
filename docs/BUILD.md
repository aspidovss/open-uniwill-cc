# Building and debugging

**English** · [Русский](#сборка-и-отладка)

## Repository layout

In detail, module by module: [STRUCTURE.md](STRUCTURE.md).

| Path | What |
|---|---|
| `uwccd/` | the service (Python, shared by Linux and Windows) and the web UI (`uwccd/web`) |
| `uwccd/win/` | Windows backends: EC through `UWACPIDriver`, WMI hot keys, HID, tray app, service host |
| `uwccd/lighting/oem/` | OEM-derived lighting code (proprietary, optional) |
| `bin/` | `uwcc` (window), `uwcc-agent` (Linux session agent), `uwccctl` (console) |
| `kernel/` | Linux kernel module `uwcc` (GPL-2.0, DKMS) |
| `windows/` | PyInstaller spec, Inno Setup script, `install.ps1` / `uninstall.ps1` |
| `proprietary/` | OEM ACPI driver and factory fan tables (proprietary, optional) |
| `tests/` | tests against a simulated EC |
| `tools/re/` | analysis tools used to recover the protocol |

## Running without the laptop (`--mock`)

The service can simulate the EC, the keyboard and the liquid cooler — for UI work and tests on any computer.

```bash
python3 -m uwccd --mock --token test -v          # Linux / macOS, Python 3.9+
# open http://127.0.0.1:47321/#token=test
UWCC_MOCK_PROJECT=0x10 python3 -m uwccd --mock --token test   # simulate another project
```

Windows (after building): `dist\ControlCenter\uwccd.exe run --mock -v`, then `dist\ControlCenter\ControlCenter.exe --show`.

Tests: `python3 -m unittest discover -s tests` (no hardware, no root).

## Linux

Install from a source checkout — the same as from the release archive:

```bash
sudo bash install.sh            # service, kernel module (DKMS), desktop entries
sudo bash uninstall.sh [--purge]
```

Dependencies the installer pulls in: `python3`, `python3-bleak`, `dkms`, kernel headers, `acpi-call-dkms` (fallback).
The kernel module alone: `cd kernel && make -C /lib/modules/$(uname -r)/build M=$PWD modules`.

Release archive (from a tagged commit, includes `proprietary/`):

```bash
git archive --format=tar.gz --prefix=open-uniwill-cc-1.4.0/ -o open-uniwill-cc-linux-1.4.0.tar.gz v1.4.0
```

## Windows

Requirements: Windows 10/11 x64, Python 3.9–3.14 **64-bit** from python.org; optional
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`) for `setup.exe`.

```powershell
.\build.cmd                     # = powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
.\build.cmd -Clean -NoInstaller
.\build.cmd -Public             # without proprietary/ (OEM driver, fan tables)
```

The script creates `.venv-win`, installs `windows\requirements.txt`, runs PyInstaller (`windows\uwcc.spec`) and
Inno Setup. Result in `dist\`: the `ControlCenter\` folder (`uwccd.exe`, `ControlCenter.exe`, `uwccctl.exe`),
`open-uniwill-cc-windows-<ver>-portable.zip`, `open-uniwill-cc-windows-<ver>-setup.exe`.

`SyntaxWarning` lines from pystray during the build are harmless.

## Debugging

### Debug log without restarting

```text
uwccctl debug on        # or Settings → Switches → Debug logging
... reproduce the problem ...
uwccctl debug off
```

The setting is stored; it also works from the start with the environment variable `UWCC_DEBUG=1`.

### Logs

| | Linux | Windows |
|---|---|---|
| service | `journalctl -u uwccd -b` | `%ProgramData%\UWCC\log\uwccd.log` |
| tray / agent | `journalctl --user -b | grep uwcc-agent` | `%LOCALAPPDATA%\UWCC\tray.log` |
| kernel module / driver | `sudo dmesg \| grep uwcc` | Device Manager → System devices → ACPIDriver |
| settings | `/var/lib/uwcc/` | `%ProgramData%\UWCC\data\` |

### Running the service in a console

```bash
# Linux
sudo systemctl stop uwccd
sudo python3 -m uwccd -v              # from /opt/uwcc, or a source checkout
sudo systemctl start uwccd
```

```powershell
# Windows, elevated PowerShell
sc.exe stop uwccd
& "C:\Program Files\UWCC Control Center\uwccd.exe" run -v
sc.exe start uwccd
```

### Looking at the hardware

```text
uwccctl status                        project, EC backend, mode, fans, battery
uwccctl ec read 0x751                 one EC register through the service
uwccctl nvram                         UniWillVariable fields
uwccctl lighting                      keyboard / light bar HID devices, keyboard type, firmware
uwccctl history csv h.csv             last hour of sensors
sudo uwccctl ec-direct dump 0x700     256 EC bytes without the service (Linux: root, Windows: admin)
```

### Bug report checklist

1. Laptop model, BIOS and EC version (Information page or `uwccctl status`).
2. OS and version; Linux: `uname -r`, Secure Boot state (`mokutil --sb-state`).
3. `uwccctl status` output.
4. The service log with debug logging on, covering the moment of the problem.

---

# Сборка и отладка

[English](#building-and-debugging) · **Русский**

## Структура репозитория

Подробно, по модулям: [STRUCTURE.ru.md](STRUCTURE.ru.md).

| Путь | Что |
|---|---|
| `uwccd/` | служба (Python, общая для Linux и Windows) и веб-интерфейс (`uwccd/web`) |
| `uwccd/win/` | Windows-часть: EC через `UWACPIDriver`, горячие клавиши WMI, HID, трей, служба |
| `uwccd/lighting/oem/` | код подсветки, производный от кода производителя (проприетарный, необязательный) |
| `bin/` | `uwcc` (окно), `uwcc-agent` (агент сеанса Linux), `uwccctl` (консоль) |
| `kernel/` | модуль ядра Linux `uwcc` (GPL-2.0, DKMS) |
| `windows/` | спецификация PyInstaller, скрипт Inno Setup, `install.ps1` / `uninstall.ps1` |
| `proprietary/` | ACPI-драйвер и заводские таблицы вентиляторов (проприетарные, необязательные) |
| `tests/` | тесты на эмуляции EC |
| `tools/re/` | инструменты анализа, которыми восстанавливался протокол |

## Запуск без ноутбука (`--mock`)

Служба умеет эмулировать EC, клавиатуру и СЖО — для работы над интерфейсом и тестов на любом компьютере.

```bash
python3 -m uwccd --mock --token test -v          # Linux / macOS, Python 3.9+
# открыть http://127.0.0.1:47321/#token=test
UWCC_MOCK_PROJECT=0x10 python3 -m uwccd --mock --token test   # другой проект
```

Windows (после сборки): `dist\ControlCenter\uwccd.exe run --mock -v`, затем `dist\ControlCenter\ControlCenter.exe --show`.

Тесты: `python3 -m unittest discover -s tests` (без железа и root).

## Linux

Установка из исходников — так же, как из архива релиза:

```bash
sudo bash install.sh            # служба, модуль ядра (DKMS), ярлыки
sudo bash uninstall.sh [--purge]
```

Зависимости ставит установщик: `python3`, `python3-bleak`, `dkms`, заголовки ядра, `acpi-call-dkms` (запасной путь).
Только модуль ядра: `cd kernel && make -C /lib/modules/$(uname -r)/build M=$PWD modules`.

Архив релиза (из коммита с тегом, вместе с `proprietary/`):

```bash
git archive --format=tar.gz --prefix=open-uniwill-cc-1.4.0/ -o open-uniwill-cc-linux-1.4.0.tar.gz v1.4.0
```

## Windows

Нужно: Windows 10/11 x64, Python 3.9–3.14 **64-bit** с python.org; по желанию
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`) для `setup.exe`.

```powershell
.\build.cmd                     # = powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
.\build.cmd -Clean -NoInstaller
.\build.cmd -Public             # без proprietary/ (драйвер, таблицы вентиляторов)
```

Скрипт создаёт `.venv-win`, ставит `windows\requirements.txt`, запускает PyInstaller (`windows\uwcc.spec`) и Inno Setup.
Результат в `dist\`: папка `ControlCenter\` (`uwccd.exe`, `ControlCenter.exe`, `uwccctl.exe`),
`open-uniwill-cc-windows-<ver>-portable.zip`, `open-uniwill-cc-windows-<ver>-setup.exe`.

Строки `SyntaxWarning` от pystray при сборке безвредны.

## Отладка

### Отладочный журнал без перезапуска

```text
uwccctl debug on        # или Настройки → Переключатели → «Отладочный журнал»
... повторить проблему ...
uwccctl debug off
```

Настройка сохраняется; с самого старта то же включает переменная окружения `UWCC_DEBUG=1`.

### Журналы

| | Linux | Windows |
|---|---|---|
| служба | `journalctl -u uwccd -b` | `%ProgramData%\UWCC\log\uwccd.log` |
| трей / агент | `journalctl --user -b | grep uwcc-agent` | `%LOCALAPPDATA%\UWCC\tray.log` |
| модуль ядра / драйвер | `sudo dmesg \| grep uwcc` | Диспетчер устройств → Системные устройства → ACPIDriver |
| настройки | `/var/lib/uwcc/` | `%ProgramData%\UWCC\data\` |

### Служба в консоли

```bash
# Linux
sudo systemctl stop uwccd
sudo python3 -m uwccd -v              # из /opt/uwcc или из исходников
sudo systemctl start uwccd
```

```powershell
# Windows, PowerShell от администратора
sc.exe stop uwccd
& "C:\Program Files\UWCC Control Center\uwccd.exe" run -v
sc.exe start uwccd
```

### Посмотреть железо

```text
uwccctl status                        проект, доступ к EC, режим, вентиляторы, батарея
uwccctl ec read 0x751                 один регистр EC через службу
uwccctl nvram                         поля UniWillVariable
uwccctl lighting                      HID-устройства клавиатуры / световой полосы, тип клавиатуры, прошивка
uwccctl history csv h.csv             последний час датчиков
sudo uwccctl ec-direct dump 0x700     256 байт EC без службы (Linux: root, Windows: администратор)
```

### Что приложить к отчёту об ошибке

1. Модель ноутбука, версии BIOS и EC (страница «Информация» или `uwccctl status`).
2. ОС и версия; для Linux: `uname -r`, состояние Secure Boot (`mokutil --sb-state`).
3. Вывод `uwccctl status`.
4. Журнал службы с включённым отладочным режимом за момент проблемы.

## Publishing a release (update check)

The update check reads `https://api.github.com/repos/aspidovss/open-uniwill-cc/releases/latest` and compares its tag
(`v1.4.0`) with the running version. For *Download and install* on Windows the release must have these assets:

- `open-uniwill-cc-windows-<ver>-setup.exe` — the installer (any name ending in `-setup.exe`);
- `SHA256SUMS.txt` — `<sha256>  <file name>` per line; the download is refused when the installer is missing from it
  or its hash differs;
- `open-uniwill-cc-linux-<ver>.tar.gz` — shown as the Linux download.

`SHA256SUMS.txt` for all files in `dist\` (PowerShell):

```powershell
Get-ChildItem dist\open-uniwill-cc-* -File | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_ -Algorithm SHA256).Hash.ToLower(), $_.Name } |
  Set-Content -Encoding ascii dist\SHA256SUMS.txt
```

On Linux: `sha256sum open-uniwill-cc-* > SHA256SUMS.txt`.

## Build stamp

The version shown by the program is `<version> · build <date> · <commit>`:

- Windows: `build_windows.ps1` writes `uwccd/_build.py` (build date, `git rev-parse --short HEAD`) for PyInstaller
  and removes it afterwards;
- Linux: `install.sh` writes `/opt/uwcc/uwccd/_build.py` (install date, commit of the checkout); a release archive made
  with `git archive` carries the commit in `uwccd/_gitinfo.txt` (`export-subst` in `.gitattributes`);
- running from a source checkout shows the last commit and `dev`.

## Bug reports

*Information → Diagnostic report* or `uwccctl report` creates a zip with everything needed (no serial numbers, MAC
addresses or user names unless ticked). Attach it to a GitHub issue or send it to OUCC@aspidov.ru.
