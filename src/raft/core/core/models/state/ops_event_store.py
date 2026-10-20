"""Append-only ops event JSONL under ``~/.raft/host/events/ops.jsonl``."""

import json
import logging
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Set, Tuple

from .ops_event import OpsEvent
from .ops_event_kinds import (
    DEFAULT_OPS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_OPS_RETENTION_MAX_BYTES,
)
from .ops_event_records import OpsEventRecords

logger = logging.getLogger(__name__)

EVENTS_STATE_DIR = Path("host") / "events"
OPS_EVENTS_FILENAME = "ops.jsonl"


class OpsEventStore(OpsEventRecords):
    """Durable operator event log (JSONL + sealed archives; size/age retention)."""

    def __init__(
        self,
        home: Path,
        *,
        max_age_days: int = DEFAULT_OPS_RETENTION_MAX_AGE_DAYS,
        max_bytes: int = DEFAULT_OPS_RETENTION_MAX_BYTES,
    ) -> None:
        self.home = home
        self.path = home / EVENTS_STATE_DIR / OPS_EVENTS_FILENAME
        self._lock = threading.Lock()
        self._max_age_days = max_age_days
        self._max_bytes = max_bytes
        self._rotation = None

    def ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: OpsEvent) -> OpsEvent:
        """Append one event; assigns ``id`` when missing. Returns stored event."""
        stored = self._with_id(event)
        line = json.dumps(stored.to_mapping(), separators=(",", ":")) + "\n"
        with self._lock:
            self.ensure_dir()
            self._rotation_bootstrap().prepare(self.path)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return stored

    def _rotation_bootstrap(self):
        if self._rotation is None:
            from raft.core.core.utils.logging.rotation_bootstrap import (
                LogRotationBootstrap,
            )

            self._rotation = LogRotationBootstrap(
                max_age_days=self._max_age_days, max_bytes=self._max_bytes
            )
        return self._rotation

    def events_in_window(
        self,
        *,
        from_ts: datetime,
        to_ts: Optional[datetime] = None,
        services: Optional[Sequence[str]] = None,
        kinds: Optional[Sequence[str]] = None,
    ) -> List[OpsEvent]:
        """Chronological events in ``[from_ts, to_ts]`` with optional filters."""
        wanted_svc = set(services) if services is not None else None
        wanted_kinds = set(kinds) if kinds is not None else None
        out: List[OpsEvent] = []
        for event in self._iter_parsed():
            if not self._in_window(event, from_ts=from_ts, to_ts=to_ts):
                continue
            if not self._service_wanted(event, wanted_svc):
                continue
            if not self._kind_wanted(event, wanted_kinds):
                continue
            out.append(event)
        return out

    def _iter_parsed(self) -> Iterator[OpsEvent]:
        for path in self._sources_oldest_first():
            yield from self._iter_file(path)

    def _iter_file(self, path: Path) -> Iterator[OpsEvent]:
        if not path.is_file():
            return
        try:
            with path.open(encoding="utf-8") as handle:
                for raw in handle:
                    event = self._parse_line(raw)
                    if event is not None:
                        yield event
        except OSError:
            logger.warning("ops events read failed path=%s", path, exc_info=True)

    def _sources_oldest_first(self) -> List[Path]:
        from raft.core.core.utils.logging.archive_names import LogArchiveNames

        names = LogArchiveNames(self.path)
        parent = self.path.parent
        if not parent.is_dir():
            return [self.path] if self.path.is_file() else []
        keyed: List[Tuple[date, int, Path]] = []
        for path in parent.iterdir():
            entry = self._archive_entry(names, path)
            if entry is not None:
                keyed.append(entry)
        keyed.sort(key=lambda item: (item[0], item[1]))
        out = [path for _, _, path in keyed]
        if self.path.is_file():
            out.append(self.path)
        return out

    @staticmethod
    def _archive_entry(names, path: Path) -> Optional[Tuple[date, int, Path]]:
        if not path.is_file() or path == names.active:
            return None
        day = names.parse_day(path)
        if day is None:
            return None
        part = names.parse_part(path)
        return None if part is None else (day, part, path)

    @staticmethod
    def _parse_line(raw: str) -> Optional[OpsEvent]:
        line = raw.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return OpsEvent.from_mapping(payload)

    @staticmethod
    def _in_window(
        event: OpsEvent, *, from_ts: datetime, to_ts: Optional[datetime]
    ) -> bool:
        ts = OpsEventStore._parse_ts(event.ts)
        if ts is None:
            return False
        if ts < from_ts:
            return False
        if to_ts is not None and ts > to_ts:
            return False
        return True

    @staticmethod
    def _service_wanted(event: OpsEvent, wanted: Optional[Set[str]]) -> bool:
        if wanted is None:
            return True
        if event.service is None:
            return True
        return event.service in wanted

    @staticmethod
    def _kind_wanted(event: OpsEvent, wanted: Optional[Set[str]]) -> bool:
        if wanted is None:
            return True
        return event.kind in wanted

    @staticmethod
    def _parse_ts(value: str) -> Optional[datetime]:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _with_id(event: OpsEvent) -> OpsEvent:
        if event.id:
            return event
        return OpsEvent(
            kind=event.kind,
            ts=event.ts,
            summary=event.summary,
            service=event.service,
            metadata=dict(event.metadata),
            id=str(uuid.uuid4()),
        )
