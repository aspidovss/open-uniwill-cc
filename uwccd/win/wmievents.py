"""Hot-key events on Windows: WMI class AcpiTest_EventULong in root\\WMI — the same source WMIEC uses in GCUService."""
import logging
import threading

log = logging.getLogger("uwccd.events")

WBEM_E_TIMED_OUT = -2147209215      # 0x80043001


class WmiHotkeyEvents(threading.Thread):
    def __init__(self, handler):
        super().__init__(daemon=True, name="hotkeys")
        self.handler = handler
        self.stop = threading.Event()
        self.available = True

    def run(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            svc = win32com.client.GetObject(r"winmgmts:{impersonationLevel=impersonate}!\\.\root\WMI")
            watcher = svc.ExecNotificationQuery("SELECT * FROM AcpiTest_EventULong")
        except Exception as e:  # noqa: BLE001
            log.warning("WMI hot-key events unavailable: %s", e)
            self.available = False
            return
        log.info("listening for AcpiTest_EventULong")
        while not self.stop.is_set():
            try:
                ev = watcher.NextEvent(1000)
            except Exception as e:  # noqa: BLE001
                if getattr(e, "excepinfo", None) and e.excepinfo and e.excepinfo[5] == WBEM_E_TIMED_OUT:
                    continue
                if getattr(e, "hresult", None) == WBEM_E_TIMED_OUT or "0x80043001" in str(e) or "timed out" in str(e).lower():
                    continue
                log.warning("WMI event: %s", e)
                self.stop.wait(2)
                continue
            try:
                code = int(ev.Properties_("ULong").Value)
            except Exception:  # noqa: BLE001
                continue
            log.info("WMI event 0x%02X", code)
            try:
                self.handler(code)
            except Exception:  # noqa: BLE001
                log.exception("event 0x%02X", code)
