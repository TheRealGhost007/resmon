"""Sampling of live system metrics via psutil, with rolling history buffers."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import psutil

HISTORY_LEN = 60
DISK_PATH = "/"

# GPU/temperature are only actually re-queried every Nth call to sample().
_SLOW_METRIC_EVERY = 5

# Network graph normalization: an adaptive ceiling that tracks recent peak
# throughput so the bar graph stays readable at both idle and burst traffic.
_NET_SCALE_FLOOR = 64 * 1024  # never normalize against less than 64 KB/s
_NET_SCALE_DECAY = 0.98

# Preferred sensor keys/labels for a representative CPU package temperature,
# across common drivers (Intel coretemp, AMD k10temp, ARM SoCs, generic ACPI).
_TEMP_SENSOR_PRIORITY = ("coretemp", "k10temp", "cpu_thermal", "acpitz")
_TEMP_LABEL_PRIORITY = ("Package id 0", "Tdie", "Tctl", "")


@dataclass(frozen=True)
class Snapshot:
    cpu: float
    ram: float
    disk: float
    net_up: float
    net_down: float
    net_norm: float
    disk_read: float
    disk_write: float
    disk_io_norm: float
    gpu: float | None
    temp: float | None


def format_rate(bytes_per_sec: float) -> str:
    value = float(bytes_per_sec)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def format_temp(celsius: float) -> str:
    return f"{celsius:.0f}°C"


def _read_cpu_temp() -> float | None:
    try:
        groups = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None

    for key in _TEMP_SENSOR_PRIORITY:
        entries = groups.get(key)
        if not entries:
            continue
        for label in _TEMP_LABEL_PRIORITY:
            for entry in entries:
                if entry.label == label:
                    return entry.current
        return entries[0].current

    for entries in groups.values():
        if entries:
            return entries[0].current
    return None


@dataclass(frozen=True)
class GPUReading:
    usage: float
    mem_percent: float


class GPUReader:
    """Best-effort GPU usage reader. NVIDIA via `nvidia-smi`, AMD via sysfs.

    Intel iGPUs don't expose a simple usage percentage without elevated
    perf-event permissions, so they're treated as unavailable for now.
    """

    def __init__(self) -> None:
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._amd_device_dir = self._find_amd_device_dir()
        self.available = bool(self._nvidia_smi or self._amd_device_dir)

    @staticmethod
    def _find_amd_device_dir() -> Path | None:
        drm = Path("/sys/class/drm")
        if not drm.exists():
            return None
        for card in sorted(drm.glob("card[0-9]*")):
            device_dir = card / "device"
            if (device_dir / "gpu_busy_percent").exists():
                return device_dir
        return None

    def read(self) -> GPUReading | None:
        if self._nvidia_smi:
            return self._read_nvidia()
        if self._amd_device_dir:
            return self._read_amd()
        return None

    def _read_nvidia(self) -> GPUReading | None:
        try:
            out = subprocess.run(
                [
                    self._nvidia_smi,
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1,
                check=True,
            )
            usage_s, used_s, total_s = (p.strip() for p in out.stdout.strip().splitlines()[0].split(","))
            used, total = float(used_s), float(total_s)
            mem_percent = (used / total * 100) if total else 0.0
            return GPUReading(usage=float(usage_s), mem_percent=mem_percent)
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return None

    def _read_amd(self) -> GPUReading | None:
        assert self._amd_device_dir is not None
        try:
            busy = float((self._amd_device_dir / "gpu_busy_percent").read_text().strip())
            used = float((self._amd_device_dir / "mem_info_vram_used").read_text().strip())
            total = float((self._amd_device_dir / "mem_info_vram_total").read_text().strip())
            mem_percent = (used / total * 100) if total else 0.0
            return GPUReading(usage=busy, mem_percent=mem_percent)
        except (OSError, ValueError):
            return None


class Sampler:
    """Pulls fresh metrics on each `sample()` call and keeps bounded history."""

    def __init__(self, history_len: int = HISTORY_LEN):
        # Seed history with one real reading (a brief blocking call, paid
        # once at startup) rather than zeros, so the graphs read as a
        # resting baseline immediately instead of an empty ramp-up. The
        # aggregate and per-core cpu_percent calls keep independent internal
        # baselines in psutil, so both need their own priming call.
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)
        time.sleep(0.1)
        initial_cpu = psutil.cpu_percent(interval=None)
        initial_percpu = psutil.cpu_percent(interval=None, percpu=True)
        initial_ram = psutil.virtual_memory().percent
        initial_disk = psutil.disk_usage(DISK_PATH).percent

        self._gpu_reader = GPUReader()
        self.gpu_available = self._gpu_reader.available
        initial_gpu_reading = self._gpu_reader.read() if self.gpu_available else None
        initial_gpu = initial_gpu_reading.usage if initial_gpu_reading else 0.0
        self._last_gpu: float | None = initial_gpu

        initial_temp = _read_cpu_temp()
        self.temp_available = initial_temp is not None
        self._last_temp: float | None = initial_temp
        self._tick_count = 0

        self.cpu_history: deque[float] = deque([initial_cpu] * history_len, maxlen=history_len)
        self.ram_history: deque[float] = deque([initial_ram] * history_len, maxlen=history_len)
        self.disk_history: deque[float] = deque([initial_disk] * history_len, maxlen=history_len)
        self.net_history: deque[float] = deque([0.0] * history_len, maxlen=history_len)
        self.diskio_history: deque[float] = deque([0.0] * history_len, maxlen=history_len)
        self.gpu_history: deque[float] = deque([initial_gpu] * history_len, maxlen=history_len)
        self.temp_history: deque[float] = deque([initial_temp or 0.0] * history_len, maxlen=history_len)
        self.cpu_percpu: list[float] = initial_percpu

        self._last_net = psutil.net_io_counters()
        self._net_scale = float(_NET_SCALE_FLOOR)

        self._last_diskio = psutil.disk_io_counters()
        self._diskio_scale = float(_NET_SCALE_FLOOR)

    def sample(self) -> Snapshot:
        cpu = psutil.cpu_percent(interval=None)
        self.cpu_percpu = psutil.cpu_percent(interval=None, percpu=True)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage(DISK_PATH).percent

        net = psutil.net_io_counters()
        up = max(0, net.bytes_sent - self._last_net.bytes_sent)
        down = max(0, net.bytes_recv - self._last_net.bytes_recv)
        self._last_net = net

        total = up + down
        self._net_scale = max(self._net_scale * _NET_SCALE_DECAY, total, _NET_SCALE_FLOOR)
        net_norm = min(100.0, (total / self._net_scale) * 100)

        diskio = psutil.disk_io_counters()
        if diskio is not None and self._last_diskio is not None:
            disk_read = max(0, diskio.read_bytes - self._last_diskio.read_bytes)
            disk_write = max(0, diskio.write_bytes - self._last_diskio.write_bytes)
        else:
            disk_read = disk_write = 0
        self._last_diskio = diskio

        diskio_total = disk_read + disk_write
        self._diskio_scale = max(self._diskio_scale * _NET_SCALE_DECAY, diskio_total, _NET_SCALE_FLOOR)
        disk_io_norm = min(100.0, (diskio_total / self._diskio_scale) * 100)

        # GPU (subprocess spawn for NVIDIA) and temperature (multi-file sensor
        # enumeration) are the most expensive reads here and barely change
        # second to second, so they're only re-queried every Nth tick; the
        # graph still gets a fresh point every tick, just repeating the last
        # known value in between.
        self._tick_count += 1
        if self.gpu_available and self._tick_count % _SLOW_METRIC_EVERY == 0:
            reading = self._gpu_reader.read()
            self._last_gpu = reading.usage if reading else None
        gpu = self._last_gpu if self.gpu_available else None

        if self.temp_available and self._tick_count % _SLOW_METRIC_EVERY == 0:
            self._last_temp = _read_cpu_temp()
        temp = self._last_temp if self.temp_available else None

        self.cpu_history.append(cpu)
        self.ram_history.append(ram)
        self.disk_history.append(disk)
        self.net_history.append(net_norm)
        self.diskio_history.append(disk_io_norm)
        self.gpu_history.append(gpu if gpu is not None else 0.0)
        self.temp_history.append(temp if temp is not None else 0.0)

        return Snapshot(
            cpu=cpu,
            ram=ram,
            disk=disk,
            net_up=up,
            net_down=down,
            net_norm=net_norm,
            disk_read=disk_read,
            disk_write=disk_write,
            disk_io_norm=disk_io_norm,
            gpu=gpu,
            temp=temp,
        )
