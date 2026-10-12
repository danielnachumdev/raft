"""Parse ``spec.resources`` into Compose CPU/memory strings."""

from pathlib import Path
from typing import Any


class AppResourceFields:
    """Parse App ``spec.resources`` limits and reservations."""

    @staticmethod
    def parse(spec: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
        limits, requests = AppResourceFields._resource_maps(spec, path)
        resources = spec.get("resources") or {}
        return (
            AppResourceFields._parse_cpu(
                limits.get("cpu", resources.get("cpus_limit")), default="0.50"
            ),
            AppResourceFields._parse_memory(
                limits.get("memory", resources.get("memory_limit")), default="128M"
            ),
            AppResourceFields._parse_cpu(
                requests.get("cpu", resources.get("cpus_reservation")), default="0.10"
            ),
            AppResourceFields._parse_memory(
                requests.get("memory", resources.get("memory_reservation")),
                default="32M",
            ),
        )

    @staticmethod
    def _resource_maps(
        spec: dict[str, Any], path: Path
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        resources = spec.get("resources")
        if resources is None:
            resources = {}
        if not isinstance(resources, dict):
            raise ValueError(f"{path}: resources must be an object")
        limits = resources.get("limits")
        if limits is None:
            limits = {}
        requests = resources.get("requests")
        if requests is None:
            requests = resources.get("reservations")
        if requests is None:
            requests = {}
        if not isinstance(limits, dict) or not isinstance(requests, dict):
            raise ValueError(f"{path}: resources.limits/requests must be objects")
        return limits, requests

    @staticmethod
    def _parse_cpu(value: Any, *, default: str) -> str:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).strip()
        if not text:
            return default
        if text.endswith("m") and text[:-1].replace(".", "", 1).isdigit():
            return f"{float(text[:-1]) / 1000.0:g}"
        return text

    @staticmethod
    def _parse_memory(value: Any, *, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        lower = text.lower()
        if lower.endswith("mi"):
            return f"{text[:-2]}M"
        if lower.endswith("gi"):
            return f"{text[:-2]}G"
        return text
