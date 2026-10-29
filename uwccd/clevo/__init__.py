"""Control Center 3.0 / Clevo — experimental, separate module.

Clevo laptops (and Uniwill-less chassis sold with Control Center 3.x from the Microsoft Store) are not driven through
the Uniwill EC of the rest of this program but through Clevo "DCHU" commands: ACPI _DSM
93f224e4-fbdc-4bbf-add6-db71bdc0afad of device CLV0001 (function = command, argument = buffer), or the older WMI
method ABBC0F6D-8EA1-11D1-00A0-C90629100000.

    Windows : the driver installed with Control Center 3 (device interface {86994C74-AD43-4812-B7E7-0C420B5C5FD7},
              IOCTL 0x322400), called directly — no vendor DLL.
    Linux   : our kernel module (kernel/uwcc.c, ioctl UWCC_IOC_CLEVO).

The command numbers are interface facts, the same as in TUXEDO clevo_acpi / clevo_wmi (GPL) and in the Control
Center 3 driver interface; no vendor code is used. See docs/CLEVO.md.
"""
from .manager import ClevoManager  # noqa: F401
