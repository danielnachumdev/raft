"""Stream ``resources.jsonl`` (+ sealed archives) newest-first."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

from raft.config.log_rotation import LogArchiveNames


class MetricsJsonlReader:
    """Parse controller metrics JSONL; reverse-read active then archives."""

    def __init__(self, path: Path, *, chunk_size: int = 65536) -> None:
        self.path = path
        self.chunk_size = chunk_size

    def samples_in_window(
        self,
        *,
        from_ts: datetime,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Chronological samples with ``ts >= from_ts`` (and ``> since``)."""
        newest_first = list(self.iter_newest_first(from_ts=from_ts, since=since))
        newest_first.reverse()
        return newest_first

    def iter_newest_first(
        self,
        *,
        from_ts: datetime,
        since: Optional[datetime] = None,
    ) -> Iterator[Dict[str, Any]]:
        for sample in self._iter_parsed_newest_first():
            ts = self.parse_ts(sample.get("ts"))
            if ts is None:
                continue
            if since is not None and ts <= since:
                return
            if ts < from_ts:
                return
            yield sample

    def _iter_parsed_newest_first(self) -> Iterator[Dict[str, Any]]:
        for path in self._sources_newest_first():
            with path.open("rb") as handle:
                for raw in self._reverse_lines(handle):
                    sample = self._parse_line(raw)
                    if sample is not None:
                        yield sample

    def _sources_newest_first(self) -> List[Path]:
        names = LogArchiveNames(self.path)
        parent = self.path.parent
        if not parent.is_dir():
            return [self.path] if self.path.is_file() else []
        keyed: List[Tuple[date, int, Path]] = []
        for path in parent.iterdir():
            entry = self._archive_entry(names, path)
            if entry is not None:
                keyed.append(entry)
        keyed.sort(key=lambda item: (item[0], item[1]), reverse=True)
        out = [self.path] if self.path.is_file() else []
        out.extend(path for _, _, path in keyed)
        return out

    @staticmethod
    def _archive_entry(
        names: LogArchiveNames, path: Path
    ) -> Optional[Tuple[date, int, Path]]:
        if not path.is_file():
            return None
        day = names.parse_day(path)
        if day is None:
            return None
        part = names.parse_part(path)
        return None if part is None else (day, part, path)

    def _reverse_lines(self, handle: BinaryIO) -> Iterator[str]:
        handle.seek(0, 2)
        position = handle.tell()
        remainder = b""
        while position > 0:
            read_size = min(self.chunk_size, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size) + remainder
            parts = chunk.split(b"\n")
            remainder = parts[0]
            for raw in reversed(parts[1:]):
                if raw.strip():
                    yield raw.decode("utf-8", errors="replace")
        if remainder.strip():
            yield remainder.decode("utf-8", errors="replace")

    @staticmethod
    def _parse_line(raw: str) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def parse_ts(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
