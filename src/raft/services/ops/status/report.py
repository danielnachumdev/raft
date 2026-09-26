"""Human and JSON renderers for ``raft status``."""

from __future__ import annotations

import json
import sys
import time
from io import StringIO
from typing import Callable, Optional, TextIO

from ....models import display_service_label
from ....ui import BOLD, CYAN, DIM, paint, want_color
from .models import ContainerStatus, HostStatus, StatusSnapshot

_DEFAULT_LIVE_INTERVAL = 1.0


def _line_count(text: str) -> int:
    """Number of terminal lines occupied by ``text`` (trailing newline-aware)."""
    if not text:
        return 0
    return text.count("\n") if text.endswith("\n") else text.count("\n") + 1


def overwrite_block(stream: TextIO, text: str, prev_lines: int) -> int:
    """Replace the previous ``prev_lines`` of our output with ``text``.

    Collect/render first, then call this so the old frame stays visible until
    the new one is ready. Only the block we wrote is erased (cursor up + erase
    to end of screen), not the whole terminal.
    """
    if prev_lines > 0:
        # Move to the first column of the first line we previously wrote, then
        # erase downward so leftover lines from a taller previous frame vanish.
        stream.write(f"\033[{prev_lines}A\033[G\033[J")
    stream.write(text)
    stream.flush()
    return _line_count(text)


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


def _write_host(stream: TextIO, host: HostStatus, *, color: bool) -> None:
    title = paint("Host", BOLD, stream=stream, color=color)
    print(title, file=stream)
    cpus = str(host.cpus) if host.cpus is not None else "-"
    print(f"  CPUs: {cpus}   load: {_fmt_load(host.loadavg)}", file=stream)
    print(f"  {_host_memory_line(host)}", file=stream)
    print(f"  {_host_disk_line(host)}", file=stream)
    print(f"  Uptime: {_fmt_uptime(host.uptime_seconds)}", file=stream)
    print(file=stream)


def _host_memory_line(host: HostStatus) -> str:
    mem_used = host.memory.used_bytes if host.memory else None
    return (
        f"Memory: {_fmt_bytes(mem_used)} / {_fmt_bytes(host.memory_total_bytes)}"
        f" ({_fmt_percent(host.memory.used_percent if host.memory else None)})"
        f"  available {_fmt_bytes(host.memory_available_bytes)}"
    )


def _host_disk_line(host: HostStatus) -> str:
    disk_path = host.disk_path or "-"
    return (
        f"Disk ({disk_path}): {_fmt_bytes(host.disk_used_bytes)} / "
        f"{_fmt_bytes(host.disk_total_bytes)}"
        f" ({_fmt_percent(host.disk_used_percent)})"
    )


def _mem_cell(c: ContainerStatus) -> str:
    used = _fmt_bytes(c.memory.used_bytes)
    if c.memory.limit_bytes is not None:
        limit = _fmt_bytes(c.memory.limit_bytes)
    else:
        limit = c.allocated.memory_limit or "-"
    return f"{used} / {limit}"


def _write_containers(
    stream: TextIO,
    containers: tuple[ContainerStatus, ...],
    *,
    color: bool,
    live_footer: bool = False,
) -> None:
    title = paint("Containers", BOLD, stream=stream, color=color)
    print(title, file=stream)
    rows = _container_table_rows(containers)
    _print_table(stream, rows, color=color)
    hint = paint(
        "  Limits are Compose deploy limits; usage is a live docker stats sample.",
        CYAN,
        stream=stream,
        color=color,
    )
    print(file=stream)
    print(hint, file=stream)
    if live_footer:
        footer = paint("  Ctrl+C to exit", DIM, stream=stream, color=color)
        print(footer, file=stream)


def _container_table_rows(
    containers: tuple[ContainerStatus, ...],
) -> list[tuple[str, ...]]:
    headers = (
        "NAME",
        "GROUP",
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
                display_service_label(c.service, c.group),
                c.group or "-",
                c.status,
                _fmt_percent(c.cpu_percent),
                _mem_cell(c),
                _fmt_percent(c.memory.used_percent),
                c.allocated.cpus_limit,
                _fmt_uptime(c.uptime_seconds),
            )
        )
    return rows


def _print_table(stream: TextIO, rows: list[tuple[str, ...]], *, color: bool) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for idx, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        if idx == 0:
            print(paint(f"  {line}", DIM, stream=stream, color=color), file=stream)
        else:
            print(f"  {line}", file=stream)


def write_report(
    snapshot: StatusSnapshot,
    *,
    as_json: bool = False,
    out: Optional[TextIO] = None,
    color: Optional[bool] = None,
    live_footer: bool = False,
) -> int:
    stream = out if out is not None else sys.stdout
    if as_json:
        json.dump(snapshot.to_dict(), stream, indent=2, sort_keys=True)
        stream.write("\n")
        return 0
    use_color = want_color(stream, color)
    _write_host(stream, snapshot.host, color=use_color)
    _write_containers(
        stream,
        snapshot.containers,
        color=use_color,
        live_footer=live_footer,
    )
    return 0


def write_live_report(
    collect: Callable[[], StatusSnapshot],
    *,
    interval: float = _DEFAULT_LIVE_INTERVAL,
    out: Optional[TextIO] = None,
    color: Optional[bool] = None,
    sleep: Callable[[float], None] = time.sleep,
    max_frames: Optional[int] = None,
) -> int:
    """Resample and overwrite only our previous lines until Ctrl+C.

    Collects the next snapshot before rewriting so the last frame stays on
    screen (no blank flash). Pass ``max_frames`` in tests.
    """
    stream = out if out is not None else sys.stdout
    try:
        _live_loop(
            collect,
            stream=stream,
            interval=interval,
            color=color,
            sleep=sleep,
            max_frames=max_frames,
        )
    except KeyboardInterrupt:
        stream.write("\n")
        stream.flush()
    return 0


def _live_loop(
    collect: Callable[[], StatusSnapshot],
    *,
    stream: TextIO,
    interval: float,
    color: Optional[bool],
    sleep: Callable[[float], None],
    max_frames: Optional[int],
) -> None:
    frames = 0
    prev_lines = 0
    while True:
        snapshot = collect()
        buf = StringIO()
        write_report(snapshot, as_json=False, out=buf, color=color, live_footer=True)
        prev_lines = overwrite_block(stream, buf.getvalue(), prev_lines)
        frames += 1
        if max_frames is not None and frames >= max_frames:
            break
        sleep(interval)
