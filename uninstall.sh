#!/usr/bin/env bash
# Remove Control Center for Linux and give fan control back to the embedded controller.
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo bash uninstall.sh"; exit 1; }
VERSION=1.5.0

systemctl disable --now uwccd.service 2>/dev/null
/usr/local/bin/uwccctl release 2>/dev/null || true
rm -f /etc/systemd/system/uwccd.service /usr/lib/systemd/system-sleep/uwcc /etc/polkit-1/rules.d/50-uwcc.rules
systemctl daemon-reload
modprobe -r uwcc 2>/dev/null
for v in $(dkms status -m uwcc 2>/dev/null | sed -n 's|^uwcc/\([^,: ]*\).*|\1|p' | sort -u) "$VERSION"; do
  dkms remove -m uwcc -v "$v" --all 2>/dev/null; rm -rf "/usr/src/uwcc-$v"
done
rm -f /etc/modules-load.d/uwcc.conf
rm -f /usr/local/bin/uwcc /usr/local/bin/uwccctl /usr/local/bin/uwcc-agent
rm -f /usr/share/applications/uwcc.desktop /etc/xdg/autostart/uwcc-agent.desktop /usr/share/icons/hicolor/scalable/apps/uwcc.svg
rm -rf /opt/uwcc
if [ "${1:-}" = "--purge" ]; then rm -rf /var/lib/uwcc; groupdel uwcc 2>/dev/null; fi
echo "Removed. Settings are kept in /var/lib/uwcc (remove them with: sudo bash uninstall.sh --purge)."
