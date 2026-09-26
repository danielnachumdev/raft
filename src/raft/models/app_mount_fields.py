"""Env / volume field parsing for App manifest ``spec`` objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .manifest import VolumeSpec


class AppMountFields:
    """Parse ``spec.env`` / ``spec.envFile`` / ``spec.volumes``."""

    @staticmethod
    def parse_env_file(spec: dict[str, Any], path: Path) -> Optional[str]:
        raw = spec.get("envFile", spec.get("env_file"))
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise ValueError(f"{path}: spec.envFile must be a string path")
        text = raw.strip()
        if not text:
            return None
        if ".." in Path(text).parts:
            raise ValueError(f"{path}: spec.envFile must not contain '..'")
        return text

    @staticmethod
    def parse_env(spec: dict[str, Any], path: Path) -> tuple[tuple[str, str], ...]:
        raw = spec.get("env")
        if raw is None:
            return ()
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: spec.env must be an object")
        return tuple(
            AppMountFields._env_pair(key, value, path) for key, value in raw.items()
        )

    @staticmethod
    def _env_pair(key: Any, value: Any, path: Path) -> tuple[str, str]:
        k = str(key).strip()
        if not k:
            raise ValueError(f"{path}: spec.env keys must be non-empty strings")
        if value is None:
            raise ValueError(f"{path}: spec.env[{k!r}] must not be null")
        return (k, str(value))

    @staticmethod
    def parse_volumes(spec: dict[str, Any], path: Path) -> tuple[VolumeSpec, ...]:
        raw = spec.get("volumes")
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise ValueError(f"{path}: spec.volumes must be a list")
        return tuple(
            AppMountFields._volume_entry(entry, index, path)
            for index, entry in enumerate(raw)
        )

    @staticmethod
    def _volume_entry(entry: Any, index: int, path: Path) -> VolumeSpec:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: spec.volumes[{index}] must be an object")
        host_s, container_s = AppMountFields._volume_paths(entry, index, path)
        read_only = entry.get("readOnly", entry.get("read_only", False))
        if not isinstance(read_only, bool):
            raise ValueError(
                f"{path}: spec.volumes[{index}].readOnly must be a boolean"
            )
        name_raw = entry.get("name")
        name = str(name_raw).strip() if name_raw is not None else None
        return VolumeSpec(
            host_path=host_s,
            container_path=container_s,
            read_only=read_only,
            name=None if name == "" else name,
        )

    @staticmethod
    def _volume_paths(
        entry: dict[str, Any], index: int, path: Path
    ) -> tuple[str, str]:
        host = entry.get("hostPath", entry.get("host_path"))
        container = entry.get("containerPath", entry.get("container_path"))
        host_s = AppMountFields._required_host(host, index, path)
        container_s = AppMountFields._required_container(container, index, path)
        return host_s, container_s

    @staticmethod
    def _required_host(host: Any, index: int, path: Path) -> str:
        if host is None or not str(host).strip():
            raise ValueError(f"{path}: spec.volumes[{index}].hostPath is required")
        host_s = str(host).strip()
        if ".." in Path(host_s).parts:
            raise ValueError(
                f"{path}: spec.volumes[{index}].hostPath must not contain '..'"
            )
        return host_s

    @staticmethod
    def _required_container(container: Any, index: int, path: Path) -> str:
        if container is None or not str(container).strip():
            raise ValueError(
                f"{path}: spec.volumes[{index}].containerPath is required"
            )
        container_s = str(container).strip()
        if not container_s.startswith("/"):
            raise ValueError(
                f"{path}: spec.volumes[{index}].containerPath must be absolute"
            )
        return container_s
