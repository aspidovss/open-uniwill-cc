import argparse
import logging
import signal
import sys
import threading

from . import __version__
from .api import serve
from .service import Service


def main():
    ap = argparse.ArgumentParser(prog="uwccd", description="Control Center service for Uniwill/Tongfang laptops")
    ap.add_argument("--backend", choices=["module", "acpi_call", "mock"], default=None,
                    help="EC access backend (default: kernel module, then acpi_call)")
    ap.add_argument("--mock", action="store_true", help="simulate the hardware (development)")
    ap.add_argument("--port", type=int, default=47321)
    ap.add_argument("--token", help="fixed API token (default: random, written to /run/uwcc/token)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    mock = a.mock or a.backend == "mock"
    svc = Service(backend=a.backend, mock=mock)
    svc.start()
    httpd = serve(svc, a.port, a.token)
    done = threading.Event()

    def stop(*_):
        done.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    done.wait()
    logging.info("stopping")
    httpd.shutdown()
    svc.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
