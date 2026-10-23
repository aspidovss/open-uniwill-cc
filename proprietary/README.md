# proprietary/

**Not MIT.** Files from the OEM "Control Center 5.52.49.6" package, included unmodified for interoperability.
All rights belong to their owners — see [LICENSE](LICENSE).

| Folder | What | Used by |
|---|---|---|
| `driver/` | `UWACPIDriver` — ACPI driver for device `ACPI\INOU0000` (Windows) | `build_windows.ps1` → `driver\` of the Windows package, installed by `install.ps1` / setup.exe when missing |
| `UserFanTables/<Project>/` | factory fan tables `M1T1…M2T3` per project | `install.sh`, `build_windows.ps1` (otherwise the tables are read from the EC) |

open-uniwill-cc works without this folder; `build_windows.ps1 -Public` builds a package without it.

---

**Не MIT.** Файлы из пакета производителя «Control Center 5.52.49.6», без изменений, для совместимости.
Все права принадлежат их владельцам — см. [LICENSE](LICENSE). Программа работает и без этой папки.
