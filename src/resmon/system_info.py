"""Static/slow-changing system info for the System Info page."""

from __future__ import annotations

import platform
import socket
import time
from dataclasses import dataclass
from pathlib import Path

import psutil


def _distro_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _primary_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "—"


def _format_uptime(seconds: float) -> str:
    total = int(seconds)
    days, total = divmod(total, 86400)
    hours, total = divmod(total, 3600)
    minutes, _ = divmod(total, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _format_bytes(n: float) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.uname().processor or "Unknown"


@dataclass(frozen=True)
class SystemInfo:
    hostname: str
    distro: str
    kernel: str
    architecture: str
    cpu_model: str
    cpu_cores: str
    total_ram: str
    total_disk: str
    ip_address: str
    uptime: str
    boot_time: str


def gather() -> SystemInfo:
    uname = platform.uname()
    boot_ts = psutil.boot_time()
    disk = psutil.disk_usage("/")
    physical = psutil.cpu_count(logical=False) or 0
    logical = psutil.cpu_count(logical=True) or 0

    return SystemInfo(
        hostname=socket.gethostname(),
        distro=_distro_name(),
        kernel=uname.release,
        architecture=uname.machine,
        cpu_model=_cpu_model(),
        cpu_cores=f"{physical} cores / {logical} threads" if physical else f"{logical} threads",
        total_ram=_format_bytes(psutil.virtual_memory().total),
        total_disk=_format_bytes(disk.total),
        ip_address=_primary_ip(),
        uptime=_format_uptime(time.time() - boot_ts),
        boot_time=time.strftime("%Y-%m-%d %H:%M", time.localtime(boot_ts)),
    )
