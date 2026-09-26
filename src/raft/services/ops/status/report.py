"""Human and JSON renderers for ``raft status``."""

from __future__ import annotations

import json
import sys
import time
from io import StringIO
from typing import Callable, Optional, TextIO

from ....models import display_service_label
from ....ui import BOLD, CYAN, DIM, paint, want_color
from .formatters import StatusFormatters
from .models import ContainerStatus, HostStatus, StatusSnapshot

_DEFAULT_LIVE_INTERVAL = 1.0


class StatusReportWriter:
    """Render a ``StatusSnapshot`` as human text, JSON, or a live table."""

    def overwrite_block(self, stream: TextIO, text: str, prev_lines: int) -> int:
        """Replace the previous ``prev_lines`` of our output with ``text``."""
        if prev_lines > 0:
            stream.write(f"\033[{prev_lines}A\033[G\033[J")
        stream.write(text)
        stream.flush()
        return self._line_count(text)

    @staticmethod
    def _line_count(text: str) -> int:
        if not text:
            return 0
        return text.count("\n") if text.endswith("\n") else text.count("\n") + 1

    def write(
        self,
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
        self._write_host(stream, snapshot.host, color=use_color)
        self._write_containers(
            stream,
            snapshot.containers,
            color=use_color,
            live_footer=live_footer,
        )
        return 0

    def write_live(
        self,
        collect: Callable[[], StatusSnapshot],
        *,
        interval: float = _DEFAULT_LIVE_INTERVAL,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
        sleep: Callable[[float], None] = time.sleep,
        max_frames: Optional[int] = None,
    ) -> int:
        """Resample and overwrite only our previous lines until Ctrl+C."""
        stream = out if out is not None else sys.stdout
        try:
            self._live_loop(
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
        self,
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
            self.write(snapshot, as_json=False, out=buf, color=color, live_footer=True)
            prev_lines = self.overwrite_block(stream, buf.getvalue(), prev_lines)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
            sleep(interval)

    def _write_host(self, stream: TextIO, host: HostStatus, *, color: bool) -> None:
        title = paint("Host", BOLD, stream=stream, color=color)
        print(title, file=stream)
        cpus = str(host.cpus) if host.cpus is not None else "-"
        print(
            f"  CPUs: {cpus}   load: {StatusFormatters.load(host.loadavg)}",
            file=stream,
        )
        print(f"  {self._host_memory_line(host)}", file=stream)
        print(f"  {self._host_disk_line(host)}", file=stream)
        print(
            f"  Uptime: {StatusFormatters.uptime(host.uptime_seconds)}",
            file=stream,
        )
        print(file=stream)

    @staticmethod
    def _host_memory_line(host: HostStatus) -> str:
        mem_used = host.memory.used_bytes if host.memory else None
        pct = host.memory.used_percent if host.memory else None
        return (
            f"Memory: {StatusFormatters.bytes(mem_used)} / "
            f"{StatusFormatters.bytes(host.memory_total_bytes)}"
            f" ({StatusFormatters.percent(pct)})"
            f"  available {StatusFormatters.bytes(host.memory_available_bytes)}"
        )

    @staticmethod
    def _host_disk_line(host: HostStatus) -> str:
        disk_path = host.disk_path or "-"
        return (
            f"Disk ({disk_path}): {StatusFormatters.bytes(host.disk_used_bytes)} / "
            f"{StatusFormatters.bytes(host.disk_total_bytes)}"
            f" ({StatusFormatters.percent(host.disk_used_percent)})"
        )

    def _write_containers(
        self,
        stream: TextIO,
        containers: tuple[ContainerStatus, ...],
        *,
        color: bool,
        live_footer: bool = False,
    ) -> None:
        title = paint("Containers", BOLD, stream=stream, color=color)
        print(title, file=stream)
        self._print_table(stream, self._container_table_rows(containers), color=color)
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

    @staticmethod
    def _mem_cell(c: ContainerStatus) -> str:
        used = StatusFormatters.bytes(c.memory.used_bytes)
        if c.memory.limit_bytes is not None:
            limit = StatusFormatters.bytes(c.memory.limit_bytes)
        else:
            limit = c.allocated.memory_limit or "-"
        return f"{used} / {limit}"

    def _container_table_rows(
        self, containers: tuple[ContainerStatus, ...]
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
                    StatusFormatters.percent(c.cpu_percent),
                    self._mem_cell(c),
                    StatusFormatters.percent(c.memory.used_percent),
                    c.allocated.cpus_limit,
                    StatusFormatters.uptime(c.uptime_seconds),
                )
            )
        return rows

    @staticmethod
    def _print_table(stream: TextIO, rows: list[tuple[str, ...]], *, color: bool) -> None:
        widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
        for idx, row in enumerate(rows):
            line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
            if idx == 0:
                print(paint(f"  {line}", DIM, stream=stream, color=color), file=stream)
            else:
                print(f"  {line}", file=stream)
