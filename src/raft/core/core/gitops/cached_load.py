"""In-process YAML text cache for GitOps reads (#317).

Cache key includes mtime/size so on-disk writes are visible without an
explicit clear. Process restart also drops the cache.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.errors.cta import OperatorError


@lru_cache(maxsize=128)
def _cached_text(path_key: str, mtime_ns: int, size: int) -> str:
    del mtime_ns, size
    return Path(path_key).read_text(encoding="utf-8")


class CachedYamlLoad:
    """Load YAML mappings with ``@lru_cache`` on file text."""

    def mapping(self, path: Path, *, label: str) -> Optional[dict[str, Any]]:
        if not path.is_file():
            return None
        raw = self._load_raw(path, label=label)
        return self._as_mapping(raw, label=label)

    def clear(self) -> None:
        _cached_text.cache_clear()

    def cache_info(self) -> Any:
        return _cached_text.cache_info()

    def _load_raw(self, path: Path, *, label: str) -> Any:
        try:
            resolved = path.resolve()
            stat = resolved.stat()
            return yaml.safe_load(
                _cached_text(str(resolved), stat.st_mtime_ns, stat.st_size)
            )
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid YAML in {label}: {exc}\n"
                f"Fix: repair the document or replace it from a known-good copy",
                has_fix=False,
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise OperatorError(
                f"cannot read {label}: {exc}.\n"
                f"Fix: repair the document or replace it from a known-good copy",
                has_fix=False,
            ) from exc

    @staticmethod
    def _as_mapping(raw: Any, *, label: str) -> dict[str, Any]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise OperatorError(
                f"{label} must be a YAML mapping.\n"
                f"Fix: use a YAML object at the document root",
                has_fix=False,
            )
        return raw
