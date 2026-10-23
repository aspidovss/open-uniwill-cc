"""Windows backends of the Control Center service.

On Windows the hardware is reached the same way GCUService reaches it:
  * EC and the Smart APC table through the OEM driver UWACPIDriver.sys (device \\\\.\\ACPIDriver,
    IOCTLs 0x9C40A488 / 0x9C40A48C / 0x9C40A500);
  * hot-key events through WMI (root\\WMI, AcpiTest_EventULong);
  * the UEFI variable UniWillVariable through Get/SetFirmwareEnvironmentVariableExW;
  * the ITE keyboard through hid.dll feature / output reports.
"""
