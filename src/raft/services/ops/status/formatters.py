"""Pure display helpers for human ``raft status`` tables."""

from __future__ import annotations

from typing import Optional


class StatusFormatters:
    """Format bytes / percent / uptime / loadavg for the status CLI."""

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
    def load(loadavg: Optional[tuple[float, float, float]]) -> str:
        if loadavg is None:
            return "-"
        return " ".join(f"{x:.2f}" for x in loadavg)
