# Как получить OEM-драйвер

[English](OEM-driver.md) · **Русский**

ACPI-драйвер производителя `UWACPIDriver` (файлы `UWACPIDriver.inf`, `UWACPIDriver.sys`, `uwacpidriver.cat`) даёт
программе полную скорость и два метода прошивки, недоступных через WMI (`PWUP`, `SMRW`) — см.
[WMI-vs-Driver.ru.md](WMI-vs-Driver.ru.md).

- В **несвободной** сборке он уже есть.
- **Свободная** сборка его не содержит и распространяется полностью свободно; пока драйвера нет, она работает через WMI.

Драйвер **не под MIT**: используйте его, только если у вас есть на это право (например, ноутбук продавался с
Control Center производителя). Устанавливая его, вы это подтверждаете.

## 1. С этого ноутбука — одна кнопка

Если Control Center производителя установлен или был установлен, Windows хранит драйвер в хранилище драйверов.

*Менеджер EC → Взять драйвер из системы* копирует три файла в `C:\ProgramData\UWCC\driver`
(командная строка: `uwccctl ec fetch-driver` от имени администратора). Затем *Установить OEM-драйвер*.

## 2. Из репозитория

[`proprietary/driver`](https://github.com/aspidovss/open-uniwill-cc/tree/main/proprietary/driver) — версия
17.53.43.609 из Control Center 5.52.49.6, без изменений ([лицензия](https://github.com/aspidovss/open-uniwill-cc/blob/main/proprietary/LICENSE)).
Скачайте три файла в `C:\ProgramData\UWCC\driver`, затем *Менеджер EC → Установить OEM-драйвер*.

## 3. Вручную

PowerShell от имени администратора. Каждую команду вставляйте **одной строкой** — некоторые консоли переставляют
строки при многострочной вставке.

Есть ли драйвер в хранилище?

```powershell
pnputil /enum-drivers | Select-String -Context 1,4 uwacpidriver
```

Скопировать его оттуда:

```powershell
$src = Get-ChildItem C:\Windows\System32\DriverStore\FileRepository -Directory -Filter "uwacpidriver.inf_amd64_*" | Sort-Object LastWriteTime | Select-Object -Last 1; if (-not $src) { throw "uwacpidriver not found in the driver store" }; New-Item -ItemType Directory -Force C:\ProgramData\UWCC\driver | Out-Null; Copy-Item "$($src.FullName)\uwacpidriver.*" C:\ProgramData\UWCC\driver\; Get-ChildItem C:\ProgramData\UWCC\driver
```

Или достать из установщика Control Center производителя (`ControlCenter_*.exe` со страницы поддержки ноутбука) с
помощью [innoextract](https://constexpr.org/innoextract/):

```powershell
innoextract -d cc -I ZipFiles/UWACPIDriver.zip .\ControlCenter_5.52.49.6_MBB.exe
```

```powershell
$zip = Get-ChildItem cc -Recurse -Filter UWACPIDriver.zip | Select-Object -First 1; if (-not $zip) { throw "UWACPIDriver.zip not found" }; Expand-Archive $zip.FullName cc\drv -Force; New-Item -ItemType Directory -Force C:\ProgramData\UWCC\driver | Out-Null; Get-ChildItem cc\drv -Recurse -Include *.inf,*.sys,*.cat | Copy-Item -Destination C:\ProgramData\UWCC\driver\; Get-ChildItem C:\ProgramData\UWCC\driver
```

## Проверка перед установкой

Перед тем как `pnputil` установит драйвер, программа проверяет пакет — в менеджере EC, установщике, `install.ps1` и
самопроверке; вручную: `uwccctl ec check-driver` или `uwccctl driver-verify ПАПКА` (служба не нужна).

| Проверка | Проблема → результат |
|---|---|
| все три файла на месте, размеры правдоподобные | нет файлов → **не устанавливается** |
| INF — это `UWACPIDriver` для `ACPI\INOU0000`, amd64 | другое устройство → **не устанавливается** |
| подписи каталога и драйвера действительны (Windows) | недействительны / не проверены → нужна галочка *Я всё равно хочу использовать этот драйвер и понимаю риск* |
| SHA-256 — известная версия (17.53.43.609) | неизвестная версия → предупреждение, нужна та же галочка |

В командной строке то же подтверждение — `uwccctl ec install-driver --accept-risks`. Коды выхода `driver-verify`:
0 — всё хорошо, 10 — неизвестная версия, 11 — проблема с подписью, 12 — пакет непригоден.
