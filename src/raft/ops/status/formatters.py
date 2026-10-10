"""Pure display helpers for human ``raft status`` tables."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from raft.adapters.docker.crash_loop import CrashLoopDetector
from .models import STATUS_CRASH_LOOPING, STATUS_STARTING, STATUS_UNHEALTHY


class StatusFormatters:
    """Format bytes / percent / uptime / started / loadavg for status tables."""

    @staticmethod
    def container_status(
        status: str,
        health: str = "none",
        *,
        restart_count: int = 0,
        uptime_seconds: Optional[float] = None,
        oom_killed: bool = False,
    ) -> str:
        """Map Docker State + restart facts into the STATUS column label."""
        if CrashLoopDetector.is_crash_looping(
            status=status,
            restart_count=restart_count,
            uptime_seconds=uptime_seconds,
            oom_killed=oom_killed,
        ):
            return STATUS_CRASH_LOOPING
        if status == "running" and health == "unhealthy":
            return STATUS_UNHEALTHY
        if status == "running" and health == "starting":
            return STATUS_STARTING
        return status or "unknown"

    @staticmethod
    def bytes(n: Optional[int]) -> str:
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

    @staticmethod
    def percent(n: Optional[float]) -> str:
        if n is None:
            return "-"
        return f"{n:.1f}%"

    @staticmethod
    def uptime(seconds: Optional[float]) -> str:
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

    @staticmethod
    def started(seconds: Optional[float], *, now: Optional[datetime] = None) -> str:
        """Wall-clock start from ``now - uptime_seconds`` (UTC, minute precision)."""
        if seconds is None:
            return "-"
        moment = now or datetime.now(timezone.utc)
        started_at = moment - timedelta(seconds=max(0, int(seconds)))
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def load(loadavg: Optional[tuple[float, float, float]]) -> str:
        if loadavg is None:
            return "-"
        return " ".join(f"{x:.2f}" for x in loadavg)
