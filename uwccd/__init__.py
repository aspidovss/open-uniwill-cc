"""uwccd — Linux re-implementation of the Uniwill/Tongfang "Control Center" (5.52.x, MBB build).

Hardware protocol reconstructed from GCUService.exe (interoperability analysis):
EC RAM is accessed through the firmware ACPI methods ECRR(addr) / ECRW(addr, data)
of the ACPI device INOU0000, exactly like the Windows UWACPIDriver.sys does.
"""
__version__ = "1.3.1"
