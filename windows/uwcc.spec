# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Windows build of UWCC Control Center.
#   pyinstaller --noconfirm --distpath dist --workpath build windows\uwcc.spec
# Produces dist\ControlCenter\ with three executables that share one runtime:
#   uwccd.exe          service host (console subsystem; pywin32 service)
#   ControlCenter.exe  tray application (GUI subsystem)
#   uwccctl.exe        command line tool (console subsystem)
import os
import shutil

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
WIN = os.path.join(ROOT, "windows")
ICON = os.path.join(WIN, "icon.ico")

# uwccctl has no .py extension in bin/; give PyInstaller a .py copy
ctl_py = os.path.join(workpath, "uwccctl.py")
os.makedirs(workpath, exist_ok=True)
shutil.copyfile(os.path.join(ROOT, "bin", "uwccctl"), ctl_py)

datas = [(os.path.join(ROOT, "uwccd", "web"), os.path.join("uwccd", "web")),
         (os.path.join(ROOT, "uwccd", "platforms"), os.path.join("uwccd", "platforms")),
         (os.path.join(ROOT, "docs", "*.md"), "docs"),                 # built-in help
         (os.path.join(ROOT, "docs", "EC", "*.md"), os.path.join("docs", "EC"))]
if os.path.isdir(os.path.join(ROOT, "uwccd", "data")):
    datas.append((os.path.join(ROOT, "uwccd", "data"), os.path.join("uwccd", "data")))

pkg = collect_submodules("uwccd", filter=lambda m: ".tests" not in m)
hidden = pkg + ["win32timezone", "servicemanager", "win32serviceutil", "win32service", "win32event",
                "pythoncom", "pywintypes", "win32com.client", "pystray._win32", "bleak.backends.winrt"]
excludes = ["tkinter", "unittest", "pydoc_data", "test"]


def analysis(script, extra_hidden=()):
    return Analysis([script], pathex=[ROOT], datas=datas, hiddenimports=hidden + list(extra_hidden),
                    excludes=excludes, noarchive=False)


a_svc = analysis(os.path.join(WIN, "entry_service.py"))
a_tray = analysis(os.path.join(WIN, "entry_tray.py"))
a_ctl = analysis(ctl_py)

# one COLLECT below: shared binaries/datas are de-duplicated into a single _internal folder


def exe(a, name, console):
    pyz = PYZ(a.pure)
    return EXE(pyz, a.scripts, [], exclude_binaries=True, name=name, console=console, icon=ICON,
               upx=False, uac_admin=False)


e_svc = exe(a_svc, "uwccd", True)
e_tray = exe(a_tray, "ControlCenter", False)
e_ctl = exe(a_ctl, "uwccctl", True)

coll = COLLECT(e_svc, a_svc.binaries, a_svc.datas,
               e_tray, a_tray.binaries, a_tray.datas,
               e_ctl, a_ctl.binaries, a_ctl.datas,
               strip=False, upx=False, name="ControlCenter")
