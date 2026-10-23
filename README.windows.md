# open-uniwill-cc for Windows

*Русская версия — ниже.*

The Windows build of open-uniwill-cc: the same service code, web interface and settings as on Linux.
It replaces the original Control Center (GCUService + UWP app) on Uniwill-based laptops.

> Tested on a MAIBENBEN Tsunami Series (project `0x10`) with Windows 11 24H2. Keep the original Control Center
> installer at hand; the uninstaller turns the original GCUService back on.

## What gets installed

| Part | What it is |
|---|---|
| `uwccd.exe` | Windows service **uwccd** (LocalSystem, automatic start). Talks to the EC through the OEM driver `\\.\ACPIDriver` (UWACPIDriver.sys, the same IOCTLs as GCUService), listens to hot keys over WMI `AcpiTest_EventULong`, serves the API and UI on `127.0.0.1:47321`. |
| `ControlCenter.exe` | Tray application (GUI). **Starts with Windows, hidden in the notification area.** Left click / "Open" opens the window (Edge in app mode); the menu switches mode, Fan Boost, keyboard backlight, liquid cooler, language, autostart. Shows the OSD notifications. |
| `uwccctl.exe` | Console version: `uwccctl status`, `uwccctl mode gaming`, `uwccctl boost on`, `uwccctl lc mode auto`, … (same commands as on Linux). |

Data: `%ProgramData%\UWCC\data` (settings, profiles, fan tables), log: `%ProgramData%\UWCC\log\uwccd.log`,
API token: `%ProgramData%\UWCC\run\token` (readable by Users, so the tray and uwccctl work without elevation).

## Building

Requirements on the build machine (Windows 10/11 x64):

* Python 3.9–3.14 **64-bit** from python.org (not the Microsoft Store stub);
* optional: [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`) for `setup.exe`;
* optional: [innoextract](https://constexpr.org/innoextract/) to take the ACPI driver out of the original setup.

The OEM driver and the factory fan tables are taken from `proprietary\` of the repository (or from a
`ControlCenter_5.52.49.6_MBB` folder next to the project, or `-CC` / `-Driver`). Then:

```
.\build.cmd                                                       # in PowerShell (cmd.exe: build.cmd)
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Optional switches (type them without brackets): `-NoInstaller`, `-Clean`, `-Public` (no OEM driver and fan tables in the
package), `-CC "D:\ControlCenter_5.52.49.6_MBB"`, `-Driver "D:\folder\with\UWACPIDriver.inf"`,
e.g. `.\build.cmd -Clean -NoInstaller`. More, including debugging: [docs/BUILD.md](docs/BUILD.md).

Result in `dist\`:

* `ControlCenter\` — the program folder (three exe files, `driver\`, `install.ps1`, `uninstall.ps1`);
* `open-uniwill-cc-windows-<ver>-portable.zip`;
* `open-uniwill-cc-windows-<ver>-setup.exe` (if Inno Setup is installed).

## Installing

**setup.exe** — run it, keep the "Disable the original Control Center service" box ticked.

**portable zip** — unpack, right click `install.ps1` → *Run with PowerShell* (it asks for elevation), or:

```
powershell -ExecutionPolicy Bypass -File install.ps1            # to C:\Program Files\UWCC Control Center
powershell -ExecutionPolicy Bypass -File uninstall.ps1 [-RemoveData]
```

The installer: stops and disables GCUService, installs UWACPIDriver if it is missing (`pnputil /add-driver … /install`),
registers and starts the **uwccd** service, adds ControlCenter.exe to autostart (HKLM `Run`) and the Start menu.
Autostart can be switched off per user from the tray menu ("Start with Windows") or in Task Manager → Startup.

Uninstall gives fan control back to the EC (`uwccctl release`), removes the service and re-enables GCUService.

## Differences from Linux

* EC access: OEM driver `UWACPIDriver.sys` instead of the `uwcc` kernel module / acpi_call.
* CPU temperature: ACPI thermal zone (as GCUService does); GPU: `nvidia-smi`.
* Touchpad hot key: the tray sends Win+Ctrl+F24 (the Windows precision touchpad toggle).
* Webcam switch: `Disable-PnpDevice` on Camera/Image devices.
* Not available on Windows: Wi-Fi/Bluetooth rfkill switches, "who keeps the dGPU awake".
* "Follow mode with power profile" switches the Windows power mode (Best efficiency / Balanced / Best performance).
* Keyboard backlight timeout uses the tray's idle time (a service cannot see user input).

## Troubleshooting

* `uwccctl status` — "service not running": `sc query uwccd`, then look at `%ProgramData%\UWCC\log\uwccd.log`.
* the log says the EC cannot be opened (`\\.\ACPIDriver`): check Device Manager → System devices → "ACPIDriver"
  (hardware id `ACPI\INOU0000`), reinstall the driver from `driver\`.
* Debug log: `uwccctl debug on` (or Settings → Switches → *Debug logging*), reproduce, attach `uwccd.log`.
* Console debugging: `sc stop uwccd`, then `uwccd.exe run -v` in an elevated console;
  `uwccd.exe run --mock` starts with an emulated EC (no hardware access). Tray log: `%LOCALAPPDATA%\UWCC\tray.log`.
* Hot keys do nothing — make sure GCUService is stopped: `sc query GCUService`.

---

# open-uniwill-cc для Windows

Windows-сборка open-uniwill-cc: тот же код службы, веб-интерфейс и настройки, что и в Linux. Заменяет оригинальный Control Center (GCUService + UWP-приложение).

> Проверено на MAIBENBEN Tsunami Series (проект `0x10`), Windows 11 24H2. Держите установщик оригинального
> Control Center под рукой: деинсталлятор включает GCUService обратно.

**Состав:** служба `uwccd.exe` (EC через `\\.\ACPIDriver`, горячие клавиши через WMI, UI на `127.0.0.1:47321`),
трей-приложение `ControlCenter.exe` (GUI; **автозапуск, по умолчанию скрыто в трее**, окно — Edge в режиме приложения,
меню: режим, Fan Boost, подсветка, СЖО, язык, автозапуск) и консольная `uwccctl.exe` (те же команды, что в Linux).

**Сборка** (Windows 10/11 x64, Python 3.9–3.14 64-bit с python.org; по желанию Inno Setup 6 и innoextract).
Драйвер производителя и заводские таблицы вентиляторов берутся из `proprietary\` репозитория (или из папки
`ControlCenter_5.52.49.6_MBB` рядом с проектом, или `-CC` / `-Driver`), затем:

```
.\build.cmd                                                       # в PowerShell (в cmd.exe: build.cmd)
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Необязательные ключи (без квадратных скобок): `-NoInstaller`, `-Clean`, `-Public` (без драйвера и таблиц), `-CC "D:\папка CC"`, `-Driver "D:\папка с UWACPIDriver.inf"`,
например `.\build.cmd -Clean -NoInstaller`. Подробнее, включая отладку: [docs/BUILD.md](docs/BUILD.md).

В `dist\` появятся папка `ControlCenter\`, `open-uniwill-cc-windows-<ver>-portable.zip` и (если есть Inno Setup)
`open-uniwill-cc-windows-<ver>-setup.exe`.

**Установка:** `setup.exe` либо `install.ps1` из zip (сам запросит права администратора). Установщик останавливает и
отключает GCUService, ставит драйвер UWACPIDriver (если его нет), регистрирует и запускает службу **uwccd**,
добавляет ControlCenter.exe в автозагрузку и меню «Пуск». Удаление: через «Приложения» или `uninstall.ps1 [-RemoveData]`,
управление вентиляторами возвращается EC, GCUService включается обратно.

**Отличия от Linux:** доступ к EC через OEM-драйвер; температура CPU из ACPI thermal zone, GPU через `nvidia-smi`;
переключатели Wi-Fi/Bluetooth (rfkill) и список «кто держит dGPU» недоступны; синхронизация с профилем питания
переключает режим питания Windows; таймаут подсветки считается по простою из трей-приложения.

**Диагностика:** `uwccctl status`, `sc query uwccd`, лог `%ProgramData%\UWCC\log\uwccd.log`;
отладочный журнал: `uwccctl debug on` (или Настройки → Переключатели → «Отладочный журнал»);
отладка в консоли администратора: `sc stop uwccd` и `uwccd.exe run -v` (или `--mock` без доступа к железу);
журнал трея: `%LOCALAPPDATA%\UWCC\tray.log`.
