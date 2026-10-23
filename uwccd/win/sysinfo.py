"""Monitor for Windows: the same snapshot structure as the Linux monitor.

CPU temperature comes from the first ACPI thermal zone, exactly like CPUInfo.GetCPUTemperature in
GCUService ("Thermal Zone Information" counter, Kelvin); fan speeds still come from the EC.
"""
import os
import platform
import shutil
import subprocess
import time

import psutil

from ..monitor import Monitor, _num
from . import winapi, winplat
from .pdhpower import EnergyMeterPower

NVSMI = [r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]


class WinMonitor(Monitor):
    def __init__(self, ec, platform_):
        super().__init__(ec, platform_)
        self.cpu_model = winplat.cpu_model()
        self._temp_cache = (0.0, None)
        self._bat_cache = (0.0, {})
        psutil.cpu_percent(None)
        self.rapl = EnergyMeterPower()        # CPU package power (W) for the sampler, like Rapl on Linux

    def cpu_temp(self):
        t, v = self._temp_cache
        if time.time() - t < 2:
            return v
        v = None
        rows = winplat.wmi_query("SELECT Name, Temperature, HighPrecisionTemperature FROM "
                                 "Win32_PerfFormattedData_Counters_ThermalZoneInformation")
        for r in rows:
            k = (r.HighPrecisionTemperature or 0) / 10.0 or (r.Temperature or 0)
            if k > 200:
                v = round(k - 273.2)
                break
        if v is None:
            for r in winplat.wmi_query("SELECT CurrentTemperature FROM MSAcpi_ThermalZoneTemperature", r"root\WMI"):
                if r.CurrentTemperature:
                    v = round(r.CurrentTemperature / 10.0 - 273.2)
                    break
        self._temp_cache = (time.time(), v)
        return v

    def cpu_usage(self):
        return round(psutil.cpu_percent(None))

    def cpu_freq(self):
        f = psutil.cpu_freq()
        return round(f.current) if f and f.current else None

    def nvidia(self):
        t, val = self._nv_cache
        if time.time() - t < 3:
            return val
        exe = next((p for p in NVSMI if os.path.exists(p)), None) or shutil.which("nvidia-smi")
        val = None
        if exe:
            try:
                out = subprocess.run([exe, "--query-gpu=name,temperature.gpu,utilization.gpu,clocks.gr,clocks.mem,"
                                      "pstate,memory.total,power.draw,power.limit", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=4, check=False,
                                     creationflags=winplat.CREATE_NO_WINDOW).stdout.strip().splitlines()
                if out:
                    p = [x.strip() for x in out[0].split(",")]
                    val = {"name": p[0], "temp": _num(p[1]), "usage": _num(p[2]), "core_mhz": _num(p[3]),
                           "mem_mhz": _num(p[4]), "pstate": p[5], "vram_mb": _num(p[6]), "power_w": _num(p[7]),
                           "power_limit_w": _num(p[8]) if len(p) > 8 else None}
            except (OSError, subprocess.SubprocessError):
                val = None
        self._nv_cache = (time.time(), val)
        return val

    @staticmethod
    def memory():
        m = psutil.virtual_memory()
        return {"total_mb": m.total // 2**20, "used_mb": (m.total - m.available) // 2**20, "usage": round(m.percent)}

    def battery(self):
        b = psutil.sensors_battery()
        if b is None:
            return {"present": False}
        t, extra = self._bat_cache
        if time.time() - t > 60:
            extra = {}
            design = full = None
            for r in winplat.wmi_query("SELECT DesignedCapacity FROM BatteryStaticData", r"root\WMI"):
                design = r.DesignedCapacity
            for r in winplat.wmi_query("SELECT FullChargedCapacity FROM BatteryFullChargedCapacity", r"root\WMI"):
                full = r.FullChargedCapacity
            for r in winplat.wmi_query("SELECT CycleCount FROM BatteryCycleCount", r"root\WMI"):
                extra["cycle_count"] = r.CycleCount
            if design and full:
                extra["health"] = round(100 * full / design)
            self._bat_cache = (time.time(), extra)
        status = "Charging" if b.power_plugged and b.percent < 100 else ("Full" if b.power_plugged else "Discharging")
        remaining = b.secsleft // 60 if isinstance(b.secsleft, int) and b.secsleft > 0 else None
        return {"present": True, "status": status, "percent": round(b.percent), "health": extra.get("health"),
                "remaining_min": remaining if status == "Discharging" else None, "model": None, "vendor": None,
                "cycle_count": extra.get("cycle_count"), "power_w": self.battery_power()}

    def battery_power(self):
        """W drawn from / charged into the battery (WMI BatteryStatus, mW), cached 4 s."""
        t, v = getattr(self, "_bp_cache", (0.0, None))
        if time.time() - t < 4:
            return v
        v = None
        for r in winplat.wmi_query("SELECT DischargeRate, ChargeRate, Discharging FROM BatteryStatus", r"root\WMI"):
            rate = r.DischargeRate if r.Discharging else r.ChargeRate
            if rate and 0 < rate < 1_000_000:
                v = round(rate / 1000.0, 1)
            break
        self._bp_cache = (time.time(), v)
        return v

    @staticmethod
    def ac_online():
        s = winapi.power_status()
        return True if s is None else s.ACLineStatus == 1

    def network(self):
        c = psutil.net_io_counters()
        now = time.time()
        prev, self._net_prev = self._net_prev, (now, c.bytes_recv, c.bytes_sent)
        if not prev or now == prev[0]:
            return {"down_kbs": 0, "up_kbs": 0}
        dt = now - prev[0]
        return {"down_kbs": round((c.bytes_recv - prev[1]) / dt / 1024), "up_kbs": round((c.bytes_sent - prev[2]) / dt / 1024)}

    @staticmethod
    def disks():
        # MSFT_PhysicalDisk knows SSD/HDD (MediaType 3 = HDD, 4 = SSD) and NVMe (BusType 17);
        # Win32_DiskDrive reports every internal drive as "Fixed hard disk media".
        kind = {}
        for r in winplat.wmi_query("SELECT DeviceId, MediaType, BusType FROM MSFT_PhysicalDisk",
                                   r"root\Microsoft\Windows\Storage"):
            try:
                kind[int(r.DeviceId)] = (int(r.MediaType or 0), int(r.BusType or 0))
            except (TypeError, ValueError):
                pass
        out = []
        for r in winplat.wmi_query("SELECT Index, Model, Size, MediaType FROM Win32_DiskDrive"):
            size = int(r.Size or 0)
            if size < 1e9:
                continue
            media, bus = kind.get(int(r.Index), (0, 0))
            model = (r.Model or "").strip()
            if media in (3, 4):
                rotational = media == 3
            else:
                rotational = bus != 17 and not any(k in model.upper() for k in ("SSD", "NVME", "SN7", "SN8", "PC3", "PC4"))
            out.append({"name": f"Disk {r.Index}", "model": model, "size_gb": round(size / 1e9), "temp": None,
                        "rotational": rotational})
        out.sort(key=lambda d: d["name"])
        try:
            usage = round(psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\").percent)
        except OSError:
            usage = None
        return {"devices": out, "root_usage": usage}

    def info(self):
        d = super().info()
        d["kernel"] = f"Windows {platform.release()} ({platform.version()})"
        return d

