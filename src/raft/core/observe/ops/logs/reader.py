"""Tail retained service-log text across active + sealed archives."""

from datetime import date
from pathlib import Path
from typing import BinaryIO, Iterator, List, Optional, Tuple

from raft.core.core.utils import LogArchiveNames

from .store import CURRENT_LOG_NAME, ServiceLogsStore


class ServiceLogsReader:
    """Newest-first reverse line read, then chronological tail of ``n`` lines."""

    def __init__(self, store: ServiceLogsStore, *, chunk_size: int = 65536) -> None:
        self._store = store
        self.chunk_size = chunk_size

    def tail(self, key: str, *, lines: int) -> str:
        if lines < 1:
            return ""
        collected = list(self._iter_newest_first(key))
        if not collected:
            return ""
        kept = collected[:lines]
        kept.reverse()
        return "\n".join(kept)

    def _iter_newest_first(self, key: str) -> Iterator[str]:
        for path in self._sources_newest_first(key):
            try:
                with path.open("rb") as handle:
                    yield from self._reverse_lines(handle)
            except OSError:
                continue

    def _sources_newest_first(self, key: str) -> List[Path]:
        active = self._store.active_path(key)
        names = LogArchiveNames(active)
        parent = active.parent
        if not parent.is_dir():
            return [active] if active.is_file() else []
        keyed: List[Tuple[date, int, Path]] = []
        for path in parent.iterdir():
            entry = self._archive_entry(names, path)
            if entry is not None:
                keyed.append(entry)
        keyed.sort(key=lambda item: (item[0], item[1]), reverse=True)
        out = [active] if active.is_file() else []
        out.extend(path for _, _, path in keyed)
        return out

    @staticmethod
    def _archive_entry(
        names: LogArchiveNames, path: Path
    ) -> Optional[Tuple[date, int, Path]]:
        if not path.is_file() or path.name == CURRENT_LOG_NAME:
            return None
        if path.name == "meta.json":
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
