"""Parse ``spec.dependsOn`` string / object entries into ``DependsOnSpec``."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .depends import DependsOnSpec

__all__ = ["DependsOnFields"]


class DependsOnFields:
    """Field-level parsing for App ``dependsOn`` (names + ``scaleWithParent``)."""

    @staticmethod
    def parse(raw: Any, *, path: Path) -> tuple[DependsOnSpec, ...]:
        items = DependsOnFields._coerce_items(raw, path=path)
        return DependsOnFields._unique(items)

    @staticmethod
    def _coerce_items(raw: Any, *, path: Path) -> list[DependsOnSpec]:
        if raw is None:
            return []
        if isinstance(raw, str):
            return DependsOnFields._from_string(raw)
        if isinstance(raw, list):
            return DependsOnFields._from_list(raw, path=path)
        raise ValueError(f"{path}: spec.dependsOn must be a string or array")

    @staticmethod
    def _from_string(raw: str) -> list[DependsOnSpec]:
        name = raw.strip()
        return [DependsOnSpec(name=name)] if name else []

    @staticmethod
    def _from_list(raw: list[Any], *, path: Path) -> list[DependsOnSpec]:
        out: list[DependsOnSpec] = []
        for item in raw:
            entry = DependsOnFields._entry(item, path=path)
            if entry is not None:
                out.append(entry)
        return out

    @staticmethod
    def _entry(raw: Any, *, path: Path) -> Optional[DependsOnSpec]:
        if isinstance(raw, str):
            name = raw.strip()
            return DependsOnSpec(name=name) if name else None
        if isinstance(raw, dict):
            return DependsOnFields._from_mapping(raw, path=path)
        raise ValueError(
            f"{path}: spec.dependsOn entries must be strings or objects with name"
        )

    @staticmethod
    def _from_mapping(raw: dict[str, Any], *, path: Path) -> DependsOnSpec:
        unknown = set(raw) - {"name", "scaleWithParent", "scale_with_parent"}
        if unknown:
            keys = ", ".join(sorted(unknown))
            raise ValueError(f"{path}: spec.dependsOn unknown keys: {keys}")
        name = DependsOnFields._mapping_name(raw, path=path)
        return DependsOnSpec(
            name=name,
            scale_with_parent=DependsOnFields._scale_flag(raw, path=path),
        )

    @staticmethod
    def _mapping_name(raw: dict[str, Any], *, path: Path) -> str:
        if "name" not in raw:
            raise ValueError(f"{path}: spec.dependsOn object requires name")
        name = str(raw["name"]).strip()
        if not name:
            raise ValueError(f"{path}: spec.dependsOn name must be a non-empty string")
        return name

    @staticmethod
    def _scale_flag(raw: dict[str, Any], *, path: Path) -> bool:
        if "scaleWithParent" in raw:
            value = raw["scaleWithParent"]
        elif "scale_with_parent" in raw:
            value = raw["scale_with_parent"]
        else:
            return True
        if not isinstance(value, bool):
            raise ValueError(f"{path}: spec.dependsOn.scaleWithParent must be a boolean")
        return value

    @staticmethod
    def _unique(items: list[DependsOnSpec]) -> tuple[DependsOnSpec, ...]:
        out: list[DependsOnSpec] = []
        seen: set[str] = set()
        for item in items:
            if item.name in seen:
                continue
            seen.add(item.name)
            out.append(item)
        return tuple(out)
