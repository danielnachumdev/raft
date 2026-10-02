"""Batch ``docker compose ps`` status (Service / State / Health)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ComposeServiceRow:
    """One Compose service row from batch ``ps`` output."""

    service: str
    state: str
    health: str


class ComposeStatusTable:
    """Parsed compose status map keyed by service name."""

    def __init__(self, rows: Mapping[str, ComposeServiceRow]) -> None:
        self._rows: Dict[str, ComposeServiceRow] = dict(rows)

    @classmethod
    def from_ps_stdout(cls, stdout: str) -> "ComposeStatusTable":
        rows: Dict[str, ComposeServiceRow] = {}
        for line in stdout.splitlines():
            row = cls._parse_line(line)
            if row is not None:
                rows[row.service] = row
        return cls(rows)

    @classmethod
    def from_runtime_map(
        cls, mapping: Mapping[str, Tuple[str, str]]
    ) -> "ComposeStatusTable":
        """Build a table from ``service -> (state, health)`` (tests / fixtures)."""
        return cls(
            {
                name: ComposeServiceRow(name, state, health or "none")
                for name, (state, health) in mapping.items()
            }
        )

    @staticmethod
    def _parse_line(line: str) -> Optional[ComposeServiceRow]:
        parts = line.strip().split()
        if len(parts) < 2:
            return None
        service, state = parts[0], parts[1].lower()
        health = parts[2].lower() if len(parts) > 2 else "none"
        return ComposeServiceRow(service=service, state=state, health=health)

    def get(self, service: str) -> Optional[ComposeServiceRow]:
        return self._rows.get(service)

    def running_names(self, candidates: Sequence[str]) -> list:
        return [name for name in candidates if self.is_running(name)]

    def is_running(self, service: str) -> bool:
        row = self._rows.get(service)
        return row is not None and row.state == "running"

    def runtime(self, service: str) -> Tuple[str, str]:
        row = self._rows.get(service)
        if row is None:
            return ("missing", "none")
        return (row.state, row.health)

    def services(self) -> Iterable[str]:
        return self._rows.keys()
