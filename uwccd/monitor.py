"""System monitor (MySystemManager): fans from EC, everything else from Linux interfaces."""
import glob
import platform as platform_mod
import os
import shutil
import subprocess
import time

from . import regs as R
from .hw import dmi


def _read(p, default=None):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return default


def _hwmon():
    out = {}
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        name = _read(os.path.join(d, "name"), "")
        out.setdefault(name, []).append(d)
    return out


def nvidia_pci():
    """sysfs directory of the NVIDIA display controller, or None."""
    for d in glob.glob("/sys/bus/pci/devices/*"):
        if _read(os.path.join(d, "vendor"), "").lower() == "0x10de" and \
                _read(os.path.join(d, "class"), "").startswith("0x03"):
            return d
    return None


def dgpu_state():
    """'active' | 'suspended' | ... (runtime PM) — reading it never wakes the GPU."""
    d = nvidia_pci()
    if not d:
        return None
    return _read(os.path.join(d, "power", "runtime_status"), "unknown")


def dgpu_users():
    """Processes holding /dev/nvidia* open (what keeps the discrete GPU awake)."""
    out = []
    for pdir in glob.glob("/proc/[0-9]*"):
        try:
            fds = os.listdir(os.path.join(pdir, "fd"))
        except OSError:
            continue
        hit = False
        for fd in fds:
            try:
                tgt = os.readlink(os.path.join(pdir, "fd", fd))
            except OSError:
                continue
            if tgt.startswith("/dev/nvidia") and tgt not in ("/dev/nvidiactl", "/dev/nvidia-modeset"):
                hit = True
                break
        if hit:
            pid = int(os.path.basename(pdir))
            name = _read(os.path.join(pdir, "comm"), "?")
            cmd = (_read(os.path.join(pdir, "cmdline"), "") or "").replace("\0", " ").strip()
            out.append({"pid": pid, "name": name, "cmd": cmd[:160]})
    return sorted(out, key=lambda x: x["pid"])


class Rapl:
    """CPU package power from the powercap energy counter (Intel RAPL; AMD on recent kernels)."""

    def __init__(self):
        self.path = None
        for d in sorted(glob.glob("/sys/class/powercap/*")):
            if _read(os.path.join(d, "name"), "") == "package-0" and os.path.exists(os.path.join(d, "energy_uj")):
                self.path = d
                break
        self.prev = None

    def watts(self):
        if not self.path:
            return None
        e = _read(os.path.join(self.path, "energy_uj"))
        if e is None:
            return None
        now, e = time.monotonic(), int(e)
        prev, self.prev = self.prev, (now, e)
        if not prev or now <= prev[0]:
            return None
        de = e - prev[1]
        if de < 0:
            de += int(_read(os.path.join(self.path, "max_energy_range_uj"), "0") or 0)
        return round(de / 1e6 / (now - prev[0]), 1)


class Monitor:
    def __init__(self, ec, platform):
        self.ec = ec
        self.pf = platform
        self._cpu_prev = None
        self._net_prev = None
        self._nv_cache = (0, None)
        self.rapl = Rapl()
        self.cpu_model = ""
        for ln in (_read("/proc/cpuinfo", "") or "").splitlines():
            if ln.startswith("model name"):
                self.cpu_model = ln.split(":", 1)[1].strip()
                break

    # -- CPU -------------------------------------------------------------------------
    def cpu_temp(self):
        hw = _hwmon()
        for name in ("coretemp", "k10temp", "zenpower"):
            for d in hw.get(name, []):
                best, first = None, None
                for f in sorted(glob.glob(os.path.join(d, "temp*_input"))):
                    v = _read(f)
                    if not v:
                        continue
                    t = int(v) / 1000
                    first = t if first is None else first
                    if _read(f.replace("_input", "_label"), "").startswith(("Package", "Tctl", "Tdie")):
                        best = t
                if best is not None or first is not None:
                    return round(best if best is not None else first)
        for z in glob.glob("/sys/class/thermal/thermal_zone*"):
            if _read(os.path.join(z, "type"), "") in ("x86_pkg_temp", "acpitz"):
                v = _read(os.path.join(z, "temp"))
                if v:
                    return round(int(v) / 1000)
        return None

    def cpu_usage(self):
        ln = (_read("/proc/stat", "") or "").splitlines()[0].split()[1:]
        vals = list(map(int, ln))
        idle, total = vals[3] + vals[4], sum(vals)
        prev, self._cpu_prev = self._cpu_prev, (idle, total)
        if not prev or total == prev[1]:
            return 0
        return round(100 * (1 - (idle - prev[0]) / (total - prev[1])))

    def cpu_freq(self):
        fs = [int(_read(f, "0")) for f in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")]
        return round(sum(fs) / len(fs) / 1000) if fs else None

    # -- GPU (NVIDIA through nvidia-smi, cached 2 s) ------------------------------------------
    def nvidia(self):
        t, val = self._nv_cache
        if time.time() - t < 2:
            return val
        val = None
        state = dgpu_state()
        if state and state != "active":
            # nvidia-smi would wake the GPU from runtime suspend and keep it powered — don't touch it
            val = {"asleep": True, "state": state}
        elif shutil.which("nvidia-smi"):
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,clocks.gr,clocks.mem,"
                     "pstate,memory.total,power.draw,power.limit", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3, check=False).stdout.strip().splitlines()
                if out:
                    p = [x.strip() for x in out[0].split(",")]
                    val = {"name": p[0], "temp": _num(p[1]), "usage": _num(p[2]), "core_mhz": _num(p[3]),
                           "mem_mhz": _num(p[4]), "pstate": p[5], "vram_mb": _num(p[6]), "power_w": _num(p[7]),
                           "power_limit_w": _num(p[8]) if len(p) > 8 else None}
            except (OSError, subprocess.SubprocessError):
                val = None
        self._nv_cache = (time.time(), val)
        return val

    # -- memory / battery / net / disks ------------------------------------------------------------
    @staticmethod
    def memory():
        m = {}
        for ln in (_read("/proc/meminfo", "") or "").splitlines():
            k, v = ln.split(":", 1)
            m[k] = int(v.split()[0])
        tot, avail = m.get("MemTotal", 0), m.get("MemAvailable", 0)
        return {"total_mb": tot // 1024, "used_mb": (tot - avail) // 1024,
                "usage": round(100 * (tot - avail) / tot) if tot else 0}

    @staticmethod
    def battery():
        for b in glob.glob("/sys/class/power_supply/BAT*"):
            d = {k: _read(os.path.join(b, k)) for k in ("status", "capacity", "energy_now", "energy_full",
                                                         "energy_full_design", "charge_now", "charge_full",
                                                         "charge_full_design", "power_now", "current_now",
                                                         "voltage_now", "cycle_count", "model_name", "manufacturer")}
            cap = int(d["capacity"]) if d["capacity"] else None
            full = d["energy_full"] or d["charge_full"]
            design = d["energy_full_design"] or d["charge_full_design"]
            health = round(100 * int(full) / int(design)) if full and design and int(design) else None
            remaining = None
            try:
                if d["status"] == "Discharging" and d["power_now"] and d["energy_now"] and int(d["power_now"]):
                    remaining = int(int(d["energy_now"]) / int(d["power_now"]) * 60)
                elif d["status"] == "Discharging" and d["current_now"] and d["charge_now"] and int(d["current_now"]):
                    remaining = int(int(d["charge_now"]) / int(d["current_now"]) * 60)
            except ValueError:
                pass
            power = None                      # W drawn from (or charged into) the battery
            try:
                if d["power_now"]:
                    power = int(d["power_now"]) / 1e6
                elif d["current_now"] and d["voltage_now"]:
                    power = int(d["current_now"]) * int(d["voltage_now"]) / 1e12
            except ValueError:
                pass
            return {"present": True, "status": d["status"], "percent": cap, "health": health,
                    "remaining_min": remaining, "model": d["model_name"], "vendor": d["manufacturer"],
                    "cycle_count": _num(d["cycle_count"]),
                    "power_w": round(abs(power), 1) if power is not None else None}
        return {"present": False}

    @staticmethod
    def ac_online():
        for p in glob.glob("/sys/class/power_supply/*"):
            if _read(os.path.join(p, "type")) == "Mains":
                return _read(os.path.join(p, "online")) == "1"
        return True

    def network(self):
        rx = tx = 0
        for ln in (_read("/proc/net/dev", "") or "").splitlines()[2:]:
            name, data = ln.split(":", 1)
            if name.strip() == "lo":
                continue
            f = data.split()
            rx += int(f[0])
            tx += int(f[8])
        now = time.time()
        prev, self._net_prev = self._net_prev, (now, rx, tx)
        if not prev or now == prev[0]:
            return {"down_kbs": 0, "up_kbs": 0}
        dt = now - prev[0]
        return {"down_kbs": round((rx - prev[1]) / dt / 1024), "up_kbs": round((tx - prev[2]) / dt / 1024)}

    @staticmethod
    def disks():
        out = []
        for d in sorted(glob.glob("/sys/block/*")):
            n = os.path.basename(d)
            if n.startswith(("loop", "ram", "zram", "dm-", "sr")):
                continue
            size = int(_read(os.path.join(d, "size"), "0")) * 512
            if size < 1e9:
                continue
            temp = None
            for t in glob.glob(os.path.join(d, "device", "hwmon*", "temp1_input")) + \
                    glob.glob(os.path.join(d, "device", "device", "hwmon*", "temp1_input")):
                temp = round(int(_read(t, "0")) / 1000)
                break
            out.append({"name": n, "model": _read(os.path.join(d, "device", "model"), ""),
                        "size_gb": round(size / 1e9), "temp": temp,
                        "rotational": _read(os.path.join(d, "queue", "rotational")) == "1"})
        try:
            st = os.statvfs("/")
            usage = round(100 * (1 - st.f_bavail / st.f_blocks))
        except OSError:
            usage = None
        return {"devices": out, "root_usage": usage}

    # -- EC fans --------------------------------------------------------------------------------
    def fans(self):
        cpu_duty = self.ec.read(R.CPU_FAN_DUTY) // 2
        cpu_rpm = (self.ec.read(R.CPU_FAN_RPM_H) << 8) | self.ec.read(R.CPU_FAN_RPM_H + 1)
        d = {"cpu_duty": cpu_duty, "cpu_rpm": cpu_rpm}
        if self.pf.nv_gpu:
            d["gpu_duty"] = self.ec.read(R.GPU_FAN_DUTY) // 2
            d["gpu_rpm"] = (self.ec.read(R.GPU_FAN_RPM_L + 1) << 8) | self.ec.read(R.GPU_FAN_RPM_L)
        return d

    def snapshot(self):
        nv = self.nvidia() if self.pf.nv_gpu else None
        return {"t": time.time(), "cpu": {"temp": self.cpu_temp(), "usage": self.cpu_usage(), "mhz": self.cpu_freq()},
                "gpu": nv, "fans": self.fans(), "memory": self.memory(), "battery": self.battery(),
                "net": self.network(), "ac": self.ac_online()}

    def info(self):
        return {"vendor": dmi("sys_vendor"), "product": dmi("product_name"), "board": dmi("board_name"),
                "bios": dmi("bios_version"), "bios_date": dmi("bios_date"), "ec": dmi("ec_firmware_release"),
                "cpu": self.cpu_model, "memory": self.memory(), "disks": self.disks(),
                "kernel": platform_mod.release(), "project": self.pf.project_name}


def _num(s):
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None
