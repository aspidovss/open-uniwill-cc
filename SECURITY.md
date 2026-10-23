# Security

- The service (`uwccd`) runs as root (Linux) / LocalSystem (Windows) because it writes to the embedded controller.
- Its HTTP API listens on **127.0.0.1:47321 only**, rejects foreign `Host` headers (DNS rebinding) and every API
  request must carry a random token that is regenerated
  on each start: `/run/uwcc/token` (readable by group `uwcc`) or `%ProgramData%\UWCC\run\token` (readable by local users).
- Only the EC registers that the original Control Center service writes can be written; values are validated.

Please report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/aspidovss/open-uniwill-cc/security/advisories/new)
or by e-mail to **OUCC@aspidov.ru**, not in public issues.

Update installation (Windows): the tray app, running as the user, downloads the installer of the latest GitHub release
to the user's Downloads folder, checks it against `SHA256SUMS.txt` of the same release and starts it; Windows asks for
administrator rights (UAC). The service itself does not download or start programs.

---

Служба работает с правами root / LocalSystem, API слушает только `127.0.0.1:47321` и требует случайный ключ,
который создаётся заново при каждом запуске. Об уязвимостях сообщайте приватно через
[GitHub Security Advisories](https://github.com/aspidovss/open-uniwill-cc/security/advisories/new) или по почте
**OUCC@aspidov.ru**.
