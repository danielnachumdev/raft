"""Normalize ``raft logs`` argv so Fire does not treat service names as flag values.

Fire maps ``logs -f router`` to ``follow='router'``. Peel ``-f`` / ``--follow`` /
``--tail`` first, then re-emit them after service names.
"""

from __future__ import annotations

from typing import Optional, Sequence


class LogsArgvNormalizer:
    """Rewrite ``logs`` argv into Fire-safe order: services, then flags."""

    def normalize(self, argv: Sequence[str]) -> list[str]:
        if not argv or argv[0] != "logs":
            return list(argv)
        follow, tail, services, other = self._scan(argv[1:])
        return self._rebuild(follow=follow, tail=tail, services=services, other=other)

    def _scan(
        self, args: Sequence[str]
    ) -> tuple[bool, Optional[int], list[str], list[str]]:
        follow = False
        tail: Optional[int] = None
        services: list[str] = []
        other: list[str] = []
        i = 0
        while i < len(args):
            consumed = self._try_flag(args, i, follow=follow, tail=tail)
            if consumed is not None:
                follow, tail, next_i = consumed
                i = next_i
                continue
            arg = args[i]
            if arg.startswith("-"):
                other.append(arg)
            else:
                services.append(arg)
            i += 1
        return follow, tail, services, other

    def _try_flag(
        self,
        args: Sequence[str],
        i: int,
        *,
        follow: bool,
        tail: Optional[int],
    ) -> Optional[tuple[bool, Optional[int], int]]:
        arg = args[i]
        if arg in ("-f", "--follow"):
            return True, tail, i + 1
        if arg.startswith("--follow="):
            return self._parse_bool(arg.split("=", 1)[1]), tail, i + 1
        if arg == "--tail":
            if i + 1 >= len(args):
                return None
            return follow, int(args[i + 1]), i + 2
        if arg.startswith("--tail="):
            return follow, int(arg.split("=", 1)[1]), i + 1
        return None

    @staticmethod
    def _parse_bool(raw: str) -> bool:
        return raw.strip().lower() in ("1", "true", "yes", "y")

    @staticmethod
    def _rebuild(
        *,
        follow: bool,
        tail: Optional[int],
        services: list[str],
        other: list[str],
    ) -> list[str]:
        out: list[str] = ["logs", *services]
        if follow:
            out.append("--follow")
        if tail is not None:
            out.extend(["--tail", str(tail)])
        out.extend(other)
        return out
