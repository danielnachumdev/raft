"""Crash-loop detection from Docker Engine inspect facts (not logs).

Heuristic (point-in-time, reusable for any Compose service):

* ``State.Status == restarting``, or
* ``State.OOMKilled`` is true on the current generation, or
* ``RestartCount >= MIN_RESTARTS`` and uptime since ``StartedAt`` is under
  ``WINDOW_SECONDS``.

A high ``RestartCount`` with long uptime is treated as recovered (no fire).
``OOMKilled`` alone is rare after a successful restart (Docker clears it), so
the RestartCount + short-uptime branch is the primary signal for churn that
still looks ``running``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class CrashLoopDetector:
    """Decide crash-loop from Engine status / RestartCount / OOM / uptime."""

    MIN_RESTARTS = 3
    WINDOW_SECONDS = 600  # 10 minutes

    @classmethod
    def is_crash_looping(
        cls,
        *,
        status: str,
        restart_count: int,
        uptime_seconds: Optional[float],
        oom_killed: bool,
    ) -> bool:
        if (status or "").strip().lower() == "restarting":
            return True
        if oom_killed:
            return True
        if restart_count < cls.MIN_RESTARTS:
            return False
        if uptime_seconds is None:
            return False
        return uptime_seconds < cls.WINDOW_SECONDS

    @classmethod
    def uptime_seconds(
        cls, started_at: str, *, now: Optional[datetime] = None
    ) -> Optional[float]:
        """Seconds since Engine ``StartedAt``; None when absent/unparseable."""
        text = (started_at or "").strip()
        if not text or text.startswith("0001-01-01"):
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            started = datetime.fromisoformat(text)
        except ValueError:
            return None
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        moment = now or datetime.now(timezone.utc)
        return max(0.0, (moment - started).total_seconds())

    @classmethod
    def detail(
        cls,
        *,
        restart_count: int,
        uptime_seconds: Optional[float],
        oom_killed: bool,
    ) -> str:
        """Operator-facing reason string (doctor detail / footnotes)."""
        window_m = cls.WINDOW_SECONDS // 60
        if oom_killed:
            return (
                f"crash-looping (OOMKilled; RestartCount={restart_count}; "
                f"heuristic: ≥{cls.MIN_RESTARTS} restarts with uptime<{window_m}m)"
            )
        uptime = "unknown" if uptime_seconds is None else f"{int(uptime_seconds)}s"
        return (
            f"crash-looping (RestartCount={restart_count}, uptime={uptime}; "
            f"heuristic: ≥{cls.MIN_RESTARTS} restarts with uptime<{window_m}m "
            f"or OOMKilled/restarting)"
        )

    @classmethod
    def fix_cta(cls, service: str) -> str:
        window_m = cls.WINDOW_SECONDS // 60
        return (
            f"Engine RestartCount/StartedAt show crash-loop "
            f"(≥{cls.MIN_RESTARTS} restarts with uptime<{window_m}m, or OOMKilled); "
            f"docker compose -f ~/.raft/compose.yaml logs --tail=40 {service}"
        )
