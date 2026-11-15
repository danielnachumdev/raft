"""Stream ``resources.jsonl`` (+ sealed archives) newest-first."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

from raft.core.core.utils import LogArchiveNames
from .buckets import MetricsSampleBuckets

_TS_KEY = '"ts":"'


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
        to_ts: Optional[datetime] = None,
        bucket_seconds: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Chronological samples with ``from_ts <= ts`` (and ``<= to_ts``, ``> since``).

        ``bucket_seconds > 0`` keeps only the newest sample per bucket and skips
        JSON-parsing the rest, so wide windows stay cheap in time and memory.
        """
        newest_first = list(
            self.iter_newest_first(
                from_ts=from_ts,
                since=since,
                to_ts=to_ts,
                bucket_seconds=bucket_seconds,
            )
        )
        newest_first.reverse()
        return newest_first

    def earliest_ts(self) -> Optional[datetime]:
        """Oldest parseable sample timestamp, or ``None`` if the store is empty."""
        for path in reversed(self._sources_newest_first()):
            ts = self._first_sample_ts(path)
            if ts is not None:
                return ts
        return None

    def latest_sample(self) -> Optional[Dict[str, Any]]:
        """Newest parseable sample, or ``None`` if the store is empty."""
        for sample in self._iter_parsed_newest_first():
            return sample
        return None

    def iter_newest_first(
        self,
        *,
        from_ts: datetime,
        since: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        bucket_seconds: float = 0.0,
    ) -> Iterator[Dict[str, Any]]:
        buckets = MetricsSampleBuckets(from_ts, bucket_seconds)
        for ts, raw, sample in self._iter_stamped_newest_first():
            if to_ts is not None and ts > to_ts:
                continue
            if since is not None and ts <= since:
                return
            if ts < from_ts:
                return
            if buckets.is_taken(ts):
                continue
            parsed = sample if sample is not None else self._parse_line(raw)
            if parsed is None:
                continue
            buckets.claim(ts)
            yield parsed

    def _iter_parsed_newest_first(self) -> Iterator[Dict[str, Any]]:
        for path in self._sources_newest_first():
            with path.open("rb") as handle:
                for raw in self._reverse_lines(handle):
                    sample = self._parse_line(raw)
                    if sample is not None:
                        yield sample

    def _iter_stamped_newest_first(
        self,
    ) -> Iterator[Tuple[datetime, str, Optional[Dict[str, Any]]]]:
        """``(ts, raw, parsed-or-None)``; parsed only when ``ts`` is not trailing."""
        for path in self._sources_newest_first():
            with path.open("rb") as handle:
                for raw in self._reverse_lines(handle):
                    stamped = self._stamp(raw)
                    if stamped is not None:
                        yield stamped

    def _stamp(
        self, raw: str
    ) -> Optional[Tuple[datetime, str, Optional[Dict[str, Any]]]]:
        ts = self.parse_ts(self.trailing_ts(raw))
        if ts is not None:
            return ts, raw, None
        sample = self._parse_line(raw)
        if sample is None:
            return None
        ts = self.parse_ts(sample.get("ts"))
        return None if ts is None else (ts, raw, sample)

    @staticmethod
    def trailing_ts(raw: str) -> Optional[str]:
        """Top-level ``ts`` when it is the line's last key (controller writer order)."""
        line = raw.rstrip()
        if not line.endswith('"}'):
            return None
        start = line.rfind(_TS_KEY)
        if start < 0:
            return None
        value = line[start + len(_TS_KEY) : -2]
        return None if '"' in value or "\\" in value else value

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

    def _first_sample_ts(self, path: Path) -> Optional[datetime]:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for raw in handle:
                    sample = self._parse_line(raw)
                    if sample is None:
                        continue
                    ts = self.parse_ts(sample.get("ts"))
                    if ts is not None:
                        return ts
        except OSError:
            return None
        return None

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
