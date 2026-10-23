"""Windows service host for uwccd (pywin32).

  uwccd.exe                     started by the Service Control Manager
  uwccd.exe --startup auto install | remove | start | stop | restart    (pywin32 HandleCommandLine)
  uwccd.exe debug               run in the console (as administrator), Ctrl+C to stop
  uwccd.exe run [--mock]        same as `python -m uwccd` (console, no SCM)
"""
import logging
import logging.handlers
import os
import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil

SERVICE_NAME = "uwccd"
DISPLAY_NAME = "UWCC Control Center service"
DESCRIPTION = ("Performance modes, fan curves, keyboard lighting, battery protection and the Bluetooth liquid cooler "
               "for Uniwill/Tongfang laptops (open re-implementation of GCUService).")


def setup_logging():
    from .winplat import data_root
    d = os.path.join(data_root(), "log")
    os.makedirs(d, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(os.path.join(d, "uwccd.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)


class UwccService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = DISPLAY_NAME
    _svc_description_ = DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.done = threading.Event()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.done.set()
        win32event.SetEvent(self.stop_event)

    def SvcShutdown(self):
        self.SvcStop()

    def SvcDoRun(self):
        setup_logging()
        log = logging.getLogger("uwccd")
        servicemanager.LogInfoMsg(f"{SERVICE_NAME} starting")
        try:
            from ..api import serve
            from ..service import Service
            svc = Service()
            svc.start()
            httpd = serve(svc, int(os.environ.get("UWCC_PORT", "47321")))
        except Exception as e:  # noqa: BLE001
            log.exception("start failed")
            servicemanager.LogErrorMsg(f"{SERVICE_NAME} failed to start: {e}")
            return
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        log.info("stopping")
        try:
            httpd.shutdown()
            svc.stop()
        except Exception:  # noqa: BLE001
            log.exception("stop")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from ..__main__ import main as console_main
        sys.exit(console_main())
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(UwccService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(UwccService)


if __name__ == "__main__":
    main()
