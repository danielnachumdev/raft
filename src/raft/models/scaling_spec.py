"""Per-app scale-to-zero contract (``spec.scaling``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .ports import PortSpec

_REQUIRED_KEYS = (
    ("idleSeconds", "idle_seconds"),
    ("wakeTimeoutSeconds", "wake_timeout_seconds"),
    ("minUpSeconds", "min_up_seconds"),
)


@dataclass(frozen=True)
class ScalingSpec:
    """Idle stop + wake; all fields required when ``spec.scaling`` is present."""

    idle_seconds: float
    wake_timeout_seconds: float
    min_up_seconds: float


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
        return ScalingSpec(
            idle_seconds=cls._positive(raw, "idleSeconds", path),
            wake_timeout_seconds=cls._positive(raw, "wakeTimeoutSeconds", path),
            min_up_seconds=cls._positive(raw, "minUpSeconds", path),
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
    def _positive(cls, raw: dict[str, Any], camel: str, path: Path) -> float:
        snake = cls._snake_for(camel)
        if camel not in raw and snake not in raw:
            raise ValueError(
                f"{path}: spec.scaling.{camel} is required "
                f"(idleSeconds, wakeTimeoutSeconds, minUpSeconds — no defaults)"
            )
        value = raw.get(camel, raw.get(snake))
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
        for cam, snake in _REQUIRED_KEYS:
            if cam == camel:
                return snake
        raise AssertionError(f"unknown scaling field {camel!r}")  # pragma: no cover
