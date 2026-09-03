"""One-shot status line for Omarchy's bar `type: command` module.

Deliberately doesn't import gi/Gtk or the Sampler — this runs as a fresh,
short-lived process every `interval` seconds (invoked by the bar itself),
so it just takes one instantaneous reading and prints Waybar-style JSON.
"""

from __future__ import annotations

import json
import time

import psutil

from .metrics import DISK_PATH, GPUReader, _read_cpu_temp, format_rate, format_temp


def main() -> None:
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage(DISK_PATH).percent

    tooltip_lines = [f"CPU {cpu:.0f}%", f"Memory {ram:.0f}%", f"Disk {disk:.0f}%"]

    temp = _read_cpu_temp()
    if temp is not None:
        tooltip_lines.append(f"Temp {format_temp(temp)}")

    gpu_reader = GPUReader()
    if gpu_reader.available:
        reading = gpu_reader.read()
        if reading is not None:
            tooltip_lines.append(f"GPU {reading.usage:.0f}%")

    net_before = psutil.net_io_counters()
    time.sleep(0.2)
    net_after = psutil.net_io_counters()
    down = max(0, (net_after.bytes_recv - net_before.bytes_recv) * 5)  # 0.2s sample -> per-second
    up = max(0, (net_after.bytes_sent - net_before.bytes_sent) * 5)
    tooltip_lines.append(f"Net ↓{format_rate(down)}/s ↑{format_rate(up)}/s")

    output = {
        "text": f"CPU {cpu:.0f}% · MEM {ram:.0f}%",
        "tooltip": "\n".join(tooltip_lines),
        "class": "resmon",
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
