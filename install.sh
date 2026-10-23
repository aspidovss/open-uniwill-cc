#!/usr/bin/env bash
# Control Center for Linux — installer for Ubuntu 22.04 / 24.04 (and Debian-based distributions)
# Usage:  sudo bash install.sh [--cc /path/to/ControlCenter_5.52.49.6_MBB] [--no-module] [--no-bluetooth]
set -euo pipefail

VERSION=1.0.0   # DKMS module version (kernel code unchanged since 1.0.0)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX=/opt/uwcc
CC_DIR=""
WITH_MODULE=1
WITH_BT=1

while [ $# -gt 0 ]; do
  case "$1" in
    --cc) CC_DIR="$2"; shift 2 ;;
    --no-module) WITH_MODULE=0; shift ;;
    --no-bluetooth) WITH_BT=0; shift ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo bash install.sh"; exit 1; }
TARGET_USER="${SUDO_USER:-}"

# --- 1. packages -------------------------------------------------------------
say "Installing dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq || true
PKGS="python3 libnotify-bin rfkill"
[ "$WITH_MODULE" = 1 ] && PKGS="$PKGS dkms build-essential linux-headers-$(uname -r)"
apt-get install -y -qq $PKGS
apt-get install -y -qq acpi-call-dkms >/dev/null 2>&1 || warn "acpi-call-dkms is not available (only needed as a fallback)"
apt-get install -y -qq gir1.2-webkit2-4.1 python3-gi >/dev/null 2>&1 || true
if [ "$WITH_BT" = 1 ]; then
  # liquid cooler (XMG Oasis / LCT21001 / LCT22002) over Bluetooth LE
  if apt-get install -y -qq bluez python3-bleak >/dev/null 2>&1; then
    systemctl enable --now bluetooth.service 2>/dev/null || true
  else
    apt-get install -y -qq bluez python3-pip >/dev/null 2>&1 || true
    pip3 install --break-system-packages -q bleak 2>/dev/null \
      || warn "python3-bleak could not be installed — the liquid cooling page will be unavailable"
    systemctl enable --now bluetooth.service 2>/dev/null || true
  fi
fi

# --- 2. conflicting software ---------------------------------------------------
if systemctl list-unit-files 2>/dev/null | grep -q '^tccd.service'; then
  warn "TUXEDO Control Center found — it also drives the EC. Stopping tccd."
  systemctl disable --now tccd.service tccd-sleep.service 2>/dev/null || true
fi

# --- 3. files -----------------------------------------------------------------
say "Copying files to $PREFIX"
systemctl stop uwccd.service 2>/dev/null || true
rm -rf "$PREFIX"
mkdir -p "$PREFIX"
cp -r "$HERE/uwccd" "$HERE/bin" "$PREFIX/"
find "$PREFIX" -name '__pycache__' -prune -exec rm -rf {} +
chmod 755 "$PREFIX"/bin/*

# factory per-project fan tables: proprietary/ of this repository, or the Windows Control Center package
if [ -z "$CC_DIR" ]; then
  for c in "$HERE"/proprietary "$HERE"/../ControlCenter_* "$HERE"/ControlCenter_*; do
    [ -d "$c/UserFanTables" ] && CC_DIR="$c" && break
  done
fi
mkdir -p "$PREFIX/uwccd/data/UserFanTables"
if [ -n "$CC_DIR" ] && [ -d "$CC_DIR/UserFanTables" ]; then
  say "Factory fan tables: $CC_DIR/UserFanTables"
  cp -r "$CC_DIR/UserFanTables/." "$PREFIX/uwccd/data/UserFanTables/"
elif [ -d "$HERE/data/UserFanTables" ]; then
  cp -r "$HERE/data/UserFanTables/." "$PREFIX/uwccd/data/UserFanTables/"
else
  warn "ControlCenter_*/UserFanTables not found — fan tables will be read from the EC"
fi

ln -sf "$PREFIX/bin/uwcc" /usr/local/bin/uwcc
ln -sf "$PREFIX/bin/uwccctl" /usr/local/bin/uwccctl
ln -sf "$PREFIX/bin/uwcc-agent" /usr/local/bin/uwcc-agent
install -Dm644 "$HERE/packaging/uwcc.desktop" /usr/share/applications/uwcc.desktop
install -Dm644 "$HERE/packaging/uwcc-agent.desktop" /etc/xdg/autostart/uwcc-agent.desktop
install -Dm644 "$HERE/uwccd/web/icon.svg" /usr/share/icons/hicolor/scalable/apps/uwcc.svg
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
install -Dm755 "$HERE/packaging/system-sleep-uwcc" /usr/lib/systemd/system-sleep/uwcc

# --- 4. kernel module (DKMS) -----------------------------------------------------
if [ "$WITH_MODULE" = 1 ]; then
  say "Building the uwcc kernel module with DKMS"
  dkms remove -m uwcc -v "$VERSION" --all >/dev/null 2>&1 || true
  rm -rf "/usr/src/uwcc-$VERSION"
  cp -r "$HERE/kernel" "/usr/src/uwcc-$VERSION"
  if dkms add -m uwcc -v "$VERSION" && dkms build -m uwcc -v "$VERSION" && dkms install -m uwcc -v "$VERSION"; then
    install -Dm644 "$HERE/packaging/uwcc.modules-load.conf" /etc/modules-load.d/uwcc.conf
    modprobe -r uwcc 2>/dev/null || true          # an older build may still be loaded (service is stopped)
    if ! modprobe uwcc 2>/tmp/uwcc-modprobe.err; then
      if grep -qi "key was rejected\|Required key not available" /tmp/uwcc-modprobe.err; then
        warn "Secure Boot rejected the module. Enroll the DKMS key: sudo mokutil --import /var/lib/shim-signed/mok/MOK.der"
        warn "and reboot (choose Enroll MOK in the blue MOK screen). Until then the service uses acpi_call."
      else
        warn "modprobe uwcc: $(cat /tmp/uwcc-modprobe.err)"
      fi
    fi
  else
    warn "The module did not build — the service will use acpi_call (no hotkey events)"
  fi
fi
modprobe acpi_call 2>/dev/null || true

# --- 5. group, service ------------------------------------------------------------
groupadd -f uwcc
if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != root ]; then
  usermod -aG uwcc "$TARGET_USER"
fi
install -Dm644 "$HERE/packaging/uwccd.service" /etc/systemd/system/uwccd.service
systemctl daemon-reload
systemctl enable --now uwccd.service

sleep 3
if systemctl is-active --quiet uwccd.service; then
  say "uwccd service is running"
else
  warn "The service did not start: journalctl -u uwccd -b"
fi

cat <<EOF

Done. Control Center is installed.
  • Open "Control Center" from the application menu (or run: uwcc)
  • Console:  uwccctl status      Liquid cooler:  uwccctl lc scan
  • Log:      journalctl -u uwccd -f
  • Language: English by default; switch with EN/RU in the window or: uwccctl lang ru
User ${TARGET_USER:-<yours>} was added to the uwcc group — log out and back in.
EOF
