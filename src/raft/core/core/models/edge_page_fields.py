"""Parse and validate top-level edge HTML page overrides on App ``spec``."""

from pathlib import Path
from typing import Any, Optional

from raft.core.core.errors.cta import OperatorError

_FIELD_KEYS = (
    ("unavailablePage", "unavailable_page"),
    ("forbiddenPage", "forbidden_page"),
    ("maintenancePage", "maintenance_page"),
)


class AppEdgePageFields:
    """Parse edge HTML page fields (each requires ``publicHost``)."""

    @classmethod
    def parse(
        cls,
        spec: dict[str, Any],
        path: Path,
        *,
        public_host: str,
    ) -> dict[str, Optional[str]]:
        return {
            snake: cls._optional_page(
                spec, path, public_host=public_host, camel=camel
            )
            for camel, snake in _FIELD_KEYS
        }

    @classmethod
    def _optional_page(
        cls,
        spec: dict[str, Any],
        path: Path,
        *,
        public_host: str,
        camel: str,
    ) -> Optional[str]:
        snake = cls._snake_for(camel)
        if camel not in spec and snake not in spec:
            return None
        value = spec.get(camel, spec.get(snake))
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{path}: spec.{camel} must be a non-empty string "
                f"(path relative to the app root)"
            )
        rel = cls._relative_app_path(value.strip(), path, camel=camel)
        cls._require_public_host(public_host, path, camel=camel)
        return rel

    @staticmethod
    def _require_public_host(public_host: str, path: Path, *, camel: str) -> None:
        if public_host.strip():
            return
        raise OperatorError(
            f"{path}: spec.{camel} requires spec.publicHost "
            f"(edge HTML pages are served on Host-routed public traffic).\n"
            f"Fix: set publicHost, or omit {camel}"
        )

    @staticmethod
    def _relative_app_path(rel: str, path: Path, *, camel: str) -> str:
        normalized = rel.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("~"):
            raise ValueError(
                f"{path}: spec.{camel} must be relative to the app root, "
                f"got {rel!r}"
            )
        parts = Path(normalized).parts
        if not parts or ".." in parts:
            raise ValueError(
                f"{path}: spec.{camel} must be a relative path with no "
                f"'..' segments, got {rel!r}"
            )
        return normalized

    @staticmethod
    def _snake_for(camel: str) -> str:
        for cam, snake in _FIELD_KEYS:
            if cam == camel:
                return snake
        raise AssertionError(f"unknown edge page field {camel!r}")  # pragma: no cover
