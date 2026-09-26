"""Parse and load Kubernetes-shaped App manifest documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.errors import OperatorError

from .app import App
from .app_mount_fields import AppMountFields
from .app_spec_fields import AppSpecFields
from .manifest import (
    CONTRACT_API_VERSION,
    CONTRACT_KIND,
    CONTRACT_REL_PATH,
    AppSpec,
)
from .ports import PortSpec, parse_ports
from .readiness_parser import parse_readiness
from .scaling_spec import ScalingSpecParser


class AppDocument:
    """Parse YAML App documents into ``App`` + ``AppSpec``."""

    @staticmethod
    def contract_path(checkout: Path) -> Path:
        return checkout / CONTRACT_REL_PATH

    @classmethod
    def parse(
        cls,
        data: dict[str, Any],
        *,
        path: Path,
        expect_name: Optional[str] = None,
    ) -> tuple[App, AppSpec]:
        cls._require_api_kind(data, path)
        name = cls._metadata_name(data, path, expect_name=expect_name)
        spec = cls._spec_mapping(data, path)
        ports = parse_ports(spec, path)
        public_host = cls._require_public_host(spec, ports, path)
        return cls._assemble(name, public_host, spec, ports, path)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        expect_name: Optional[str] = None,
    ) -> tuple[App, AppSpec]:
        if not path.is_file():
            raise OperatorError(
                f"missing applied App manifest: {path}\n"
                f"Fix: re-apply the app (`raft apply …`) or restore the file under "
                f"~/.raft/state/apps/"
            )
        return cls.parse(cls._load_yaml_mapping(path), path=path, expect_name=expect_name)

    @classmethod
    def load_contract(
        cls,
        checkout: Path,
        *,
        expect_name: Optional[str] = None,
    ) -> AppSpec:
        path = cls.contract_path(checkout)
        if not path.is_file():
            raise FileNotFoundError(
                f"missing App manifest: {path} "
                f"(add {CONTRACT_REL_PATH.as_posix()} to the service repo)"
            )
        _, app_spec = cls.load(path, expect_name=expect_name)
        return app_spec

    @staticmethod
    def _require_api_kind(data: dict[str, Any], path: Path) -> None:
        api = str(data.get("apiVersion", "")).strip()
        kind = str(data.get("kind", "")).strip()
        if api != CONTRACT_API_VERSION:
            raise ValueError(
                f"{path}: apiVersion must be {CONTRACT_API_VERSION!r}, got {api!r}"
            )
        if kind != CONTRACT_KIND:
            raise ValueError(f"{path}: kind must be {CONTRACT_KIND!r}, got {kind!r}")

    @staticmethod
    def _metadata_name(
        data: dict[str, Any],
        path: Path,
        *,
        expect_name: Optional[str],
    ) -> str:
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"{path}: metadata must be an object")
        meta_name = metadata.get("name")
        name = str(meta_name).strip() if meta_name is not None else ""
        if not name:
            raise ValueError(f"{path}: metadata.name is required")
        if expect_name and name != expect_name:
            raise ValueError(
                f"{path}: metadata.name {name!r} does not match expected {expect_name!r}"
            )
        return name

    @staticmethod
    def _spec_mapping(data: dict[str, Any], path: Path) -> dict[str, Any]:
        spec = data.get("spec")
        if spec is None:
            return {}
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: spec must be an object")
        return spec

    @staticmethod
    def _require_public_host(
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
    ) -> str:
        public_host = str(spec.get("publicHost", spec.get("public_host", ""))).strip()
        if any(p.expose == "http" for p in ports) and not public_host:
            raise ValueError(
                f"{path}: spec.publicHost is required when any port uses expose=http"
            )
        return public_host

    @classmethod
    def _assemble(
        cls,
        name: str,
        public_host: str,
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
    ) -> tuple[App, AppSpec]:
        source, repo, image, ref, rel_path = AppSpecFields._parse_source(
            spec, path, name=name
        )
        group = AppSpecFields._parse_group(spec, path)
        app = App(
            name=name, public_host=public_host, source=source, path=rel_path,
            repo=repo, image=image, ref=ref, group=group,
        )
        return app, cls._app_spec(name, public_host, spec, ports, path, group=group)

    @staticmethod
    def _app_spec(
        name: str,
        public_host: str,
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
        *,
        group: Optional[str],
    ) -> AppSpec:
        return AppSpec(
            **AppDocument._core_spec_kwargs(name, public_host, spec, ports, path, group),
            **AppDocument._resource_kwargs(spec, path),
            **AppDocument._mount_kwargs(spec, path),
        )

    @staticmethod
    def _core_spec_kwargs(
        name: str,
        public_host: str,
        spec: dict[str, Any],
        ports: tuple[PortSpec, ...],
        path: Path,
        group: Optional[str],
    ) -> dict[str, Any]:
        fields = AppSpecFields
        context, dockerfile = fields._parse_build(spec, path)
        return {
            "ports": ports,
            "tls": fields._parse_tls(spec, path, public_host=public_host),
            "readiness": parse_readiness(spec, ports, path),
            "www": fields._parse_www(spec, path),
            "extra_hosts": fields._extra_hosts(spec, path),
            "build_context": context, "dockerfile": dockerfile,
            "metadata_name": name, "group": group,
            "scaling": ScalingSpecParser.parse(spec, ports, path),
        }

    @staticmethod
    def _resource_kwargs(spec: dict[str, Any], path: Path) -> dict[str, Any]:
        cpus_l, mem_l, cpus_r, mem_r = AppSpecFields._resources(spec, path)
        return {
            "cpus_limit": cpus_l,
            "memory_limit": mem_l,
            "cpus_reservation": cpus_r,
            "memory_reservation": mem_r,
        }

    @staticmethod
    def _mount_kwargs(spec: dict[str, Any], path: Path) -> dict[str, Any]:
        return {
            "depends_on": AppSpecFields._parse_name_list(
                spec.get("dependsOn", spec.get("depends_on")),
                path=path,
                label="spec.dependsOn",
            ),
            "env_file": AppMountFields.parse_env_file(spec, path),
            "env": AppMountFields.parse_env(spec, path),
            "volumes": AppMountFields.parse_volumes(spec, path),
        }

    @staticmethod
    def _load_yaml_mapping(path: Path) -> dict[str, Any]:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise OperatorError(
                f"cannot read App manifest: {path}\n"
                f"Fix: check permissions and UTF-8 encoding — ls -l {path}"
            ) from exc
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"{path}: invalid YAML: {exc}\n"
                f"Fix: repair the App manifest YAML"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: document must be a mapping")
        return data
