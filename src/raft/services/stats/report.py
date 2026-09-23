"""Human and JSON renderers for ``raft stats``."""

from __future__ import annotations

import json
import sys
from typing import Optional, TextIO

from ...ui import BOLD, CYAN, DIM, paint, want_color
from .models import ContainerStats, HostStats, StatsSnapshot


def _fmt_bytes(n: Optional[int]) -> str:
    if n is None or n < 0:
        return "-"
    value = float(n)
    for unit, factor in (
        ("TiB", 1024.0**4),
        ("GiB", 1024.0**3),
        ("MiB", 1024.0**2),
        ("KiB", 1024.0),
    ):
        if value >= factor:
            return f"{value / factor:.1f}{unit}"
    return f"{int(value)}B"


def _fmt_percent(n: Optional[float]) -> str:
    if n is None:
        return "-"
    return f"{n:.1f}%"


def _fmt_uptime(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _fmt_load(loadavg: Optional[tuple[float, float, float]]) -> str:
    if loadavg is None:
        return "-"
    return " ".join(f"{x:.2f}" for x in loadavg)


def _write_host(stream: TextIO, host: HostStats, *, color: bool) -> None:
    title = paint("Host", BOLD, stream=stream, color=color)
    print(title, file=stream)
    cpus = str(host.cpus) if host.cpus is not None else "-"
    print(
        f"  CPUs: {cpus}   load: {_fmt_load(host.loadavg)}",
        file=stream,
    )
    mem_used = host.memory.used_bytes if host.memory else None
    mem_line = (
        f"  Memory: {_fmt_bytes(mem_used)} / {_fmt_bytes(host.memory_total_bytes)}"
        f" ({_fmt_percent(host.memory.used_percent if host.memory else None)})"
        f"  available {_fmt_bytes(host.memory_available_bytes)}"
    )
    print(mem_line, file=stream)
    disk_path = host.disk_path or "-"
    print(
        f"  Disk ({disk_path}): {_fmt_bytes(host.disk_used_bytes)} / "
        f"{_fmt_bytes(host.disk_total_bytes)}"
        f" ({_fmt_percent(host.disk_used_percent)})",
        file=stream,
    )
    print(f"  Uptime: {_fmt_uptime(host.uptime_seconds)}", file=stream)
    print(file=stream)


def _mem_cell(c: ContainerStats) -> str:
    used = _fmt_bytes(c.memory.used_bytes)
    if c.memory.limit_bytes is not None:
        limit = _fmt_bytes(c.memory.limit_bytes)
    else:
        limit = c.allocated.memory_limit or "-"
    return f"{used} / {limit}"


def _write_containers(
    stream: TextIO,
    containers: tuple[ContainerStats, ...],
    *,
    color: bool,
) -> None:
    title = paint("Containers", BOLD, stream=stream, color=color)
    print(title, file=stream)
    headers = (
        "SERVICE",
        "STATUS",
        "CPU",
        "MEM USED / LIMIT",
        "MEM%",
        "ALLOC CPU",
        "UPTIME",
    )
    rows: list[tuple[str, ...]] = [headers]
    for c in containers:
        rows.append(
            (
                c.service,
                c.status,
                _fmt_percent(c.cpu_percent),
                _mem_cell(c),
                _fmt_percent(c.memory.used_percent),
                c.allocated.cpus_limit,
                _fmt_uptime(c.uptime_seconds),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    for idx, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        if idx == 0:
            print(paint(f"  {line}", DIM, stream=stream, color=color), file=stream)
        else:
            print(f"  {line}", file=stream)
    hint = paint(
        "  Limits are Compose deploy limits; usage is a live docker stats sample.",
        CYAN,
        stream=stream,
        color=color,
    )
    print(file=stream)
    print(hint, file=stream)


def write_report(
    snapshot: StatsSnapshot,
    *,
    as_json: bool = False,
    out: Optional[TextIO] = None,
    color: Optional[bool] = None,
) -> int:
    stream = out if out is not None else sys.stdout
    if as_json:
        json.dump(snapshot.to_dict(), stream, indent=2, sort_keys=True)
        stream.write("\n")
        return 0
    use_color = want_color(stream, color)
    _write_host(stream, snapshot.host, color=use_color)
    _write_containers(stream, snapshot.containers, color=use_color)
    return 0
