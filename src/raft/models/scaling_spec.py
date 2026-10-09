"""Per-app scale-to-zero contract (``spec.scaling``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .ports import PortSpec

DEFAULT_WAKE_TIMEOUT_SECONDS = 60.0

_FIELD_KEYS = (
    ("idleSeconds", "idle_seconds"),
    ("wakeTimeoutSeconds", "wake_timeout_seconds"),
    ("minUpSeconds", "min_up_seconds"),
    ("holdingPage", "holding_page"),
)


@dataclass(frozen=True)
class ScalingSpec:
    """Idle stop + wake. ``idleSeconds`` / ``minUpSeconds`` required; wake timeout defaults to 60."""

    idle_seconds: float
    wake_timeout_seconds: float
    min_up_seconds: float
    holding_page: Optional[str] = None


class ScalingSpecParser:
    """Parse and validate ``spec.scaling`` from an App manifest."""

    @classmethod
    def parse(
        cls,
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
    ) -> Optional[ScalingSpec]:
        raw = spec.get("scaling")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: spec.scaling must be an object")
        cls._require_http_eligible(ports, path)
        cls._reject_unknown(raw, path)
        return cls._build(raw, path)

    @classmethod
    def _build(cls, raw: dict[str, Any], path: Path) -> ScalingSpec:
        return ScalingSpec(
            idle_seconds=cls._positive(raw, "idleSeconds", path),
            wake_timeout_seconds=cls._positive(
                raw,
                "wakeTimeoutSeconds",
                path,
                default=DEFAULT_WAKE_TIMEOUT_SECONDS,
            ),
            min_up_seconds=cls._positive(raw, "minUpSeconds", path),
            holding_page=cls._holding_page(raw, path),
        )

    @staticmethod
    def _require_http_eligible(ports: tuple[PortSpec, ...], path: Path) -> None:
        if any(p.expose == "http" for p in ports):
            return
        raise ValueError(
            f"{path}: spec.scaling requires at least one port with expose: http "
            f"(and publicHost). Non-HTTP expose modes are not scale-to-zero eligible."
        )

    @classmethod
    def _holding_page(cls, raw: dict[str, Any], path: Path) -> Optional[str]:
        if "holdingPage" not in raw and "holding_page" not in raw:
            return None
        value = raw.get("holdingPage", raw.get("holding_page"))
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{path}: spec.scaling.holdingPage must be a non-empty string "
                f"(path relative to the app root)"
            )
        return cls._relative_app_path(value.strip(), path)

    @staticmethod
    def _relative_app_path(rel: str, path: Path) -> str:
        normalized = rel.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("~"):
            raise ValueError(
                f"{path}: spec.scaling.holdingPage must be relative to the app root, "
                f"got {rel!r}"
            )
        parts = Path(normalized).parts
        if not parts or ".." in parts:
            raise ValueError(
                f"{path}: spec.scaling.holdingPage must be a relative path with no "
                f"'..' segments, got {rel!r}"
            )
        return normalized

    @classmethod
    def _reject_unknown(cls, raw: dict[str, Any], path: Path) -> None:
        known = {cam for cam, snake in _FIELD_KEYS} | {snake for cam, snake in _FIELD_KEYS}
        unknown = sorted(set(raw) - known)
        if not unknown:
            return
        keys = ", ".join(unknown)
        raise ValueError(
            f"{path}: spec.scaling unknown keys: {keys}. "
            f"Fix: remove unknown keys from scaling "
            f"(idleSeconds, wakeTimeoutSeconds, minUpSeconds, holdingPage)"
        )

    @classmethod
    def _positive(
        cls,
        raw: dict[str, Any],
        camel: str,
        path: Path,
        default: Optional[float] = None,
    ) -> float:
        snake = cls._snake_for(camel)
        if camel not in raw and snake not in raw:
            if default is not None:
                return float(default)
            raise ValueError(
                f"{path}: spec.scaling.{camel} is required "
                f"(idleSeconds and minUpSeconds — wakeTimeoutSeconds defaults to 60)"
            )
        return cls._parse_positive(raw.get(camel, raw.get(snake)), camel, path)

    @staticmethod
    def _parse_positive(value: Any, camel: str, path: Path) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{path}: spec.scaling.{camel} must be a positive number, got {value!r}"
            ) from exc
        if number <= 0:
            raise ValueError(
                f"{path}: spec.scaling.{camel} must be a positive number, got {number}"
            )
        return number

    @staticmethod
    def _snake_for(camel: str) -> str:
        for cam, snake in _FIELD_KEYS:
            if cam == camel:
                return snake
        raise AssertionError(f"unknown scaling field {camel!r}")  # pragma: no cover
