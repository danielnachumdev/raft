"""Field-level parsing for App manifest ``spec`` objects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from raft.errors.cta import OperatorError

from .manifest import TLS_MODES
from .ports import PortSpec

_GROUP_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# Keys read by AppDocument / field parsers. Legacy aliases and keys that only
# exist to emit a specific Fix CTA (port, readinessProbe, groups) stay listed.
_KNOWN_SPEC_KEYS = frozenset(
    {
        "source",
        "repo",
        "image",
        "ref",
        "path",
        "publicHost",
        "public_host",
        "ports",
        "port",
        "tls",
        "readiness",
        "readinessProbe",
        "extraHosts",
        "extra_hosts",
        "build",
        "scaling",
        "resources",
        "dependsOn",
        "depends_on",
        "envFile",
        "env_file",
        "env",
        "volumes",
        "group",
        "groups",
    }
)


class AppSpecFields:
    """Parse individual AppSpec fields from a raw ``spec`` mapping."""

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

    @staticmethod
    def _extra_hosts(spec: dict[str, Any], path: Path) -> tuple[str, ...]:
        extra_raw = spec.get("extraHosts", spec.get("extra_hosts"))
        if extra_raw is None:
            return ()
        if isinstance(extra_raw, str):
            return (extra_raw.strip(),) if extra_raw.strip() else ()
        if isinstance(extra_raw, list):
            return tuple(str(x).strip() for x in extra_raw if str(x).strip())
        raise ValueError(f"{path}: spec.extraHosts must be a string or array")

    @staticmethod
    def _parse_group(spec: dict[str, Any], path: Path) -> Optional[str]:
        if "groups" in spec and spec.get("groups") is not None:
            raise ValueError(f"{path}: use spec.group (a single string), not spec.groups")
        raw = spec.get("group")
        if raw is None:
            return None
        if isinstance(raw, list):
            raise ValueError(f"{path}: spec.group must be a string (at most one group), not a list")
        if not isinstance(raw, str):
            raise ValueError(f"{path}: spec.group must be a string")
        return AppSpecFields._validated_group_name(raw.strip(), path)

    @staticmethod
    def _validated_group_name(text: str, path: Path) -> Optional[str]:
        if not text:
            return None
        if not _GROUP_NAME.match(text):
            raise ValueError(f"{path}: spec.group {text!r} must match {_GROUP_NAME.pattern}")
        return text

    @staticmethod
    def _resources(spec: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
        limits, requests = AppSpecFields._resource_maps(spec, path)
        resources = spec.get("resources") or {}
        return (
            AppSpecFields._parse_cpu(
                limits.get("cpu", resources.get("cpus_limit")), default="0.50"
            ),
            AppSpecFields._parse_memory(
                limits.get("memory", resources.get("memory_limit")), default="128M"
            ),
            AppSpecFields._parse_cpu(
                requests.get("cpu", resources.get("cpus_reservation")), default="0.10"
            ),
            AppSpecFields._parse_memory(
                requests.get("memory", resources.get("memory_reservation")),
                default="32M",
            ),
        )

    @staticmethod
    def _resource_maps(spec: dict[str, Any], path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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
    def _parse_tls(
        spec: dict[str, Any],
        path: Path,
        *,
        public_host: str,
        ports: tuple[PortSpec, ...],
    ) -> str:
        tls = AppSpecFields._normalize_tls(spec.get("tls", "off"), path)
        if tls not in TLS_MODES:
            raise ValueError(f"{path}: spec.tls must be one of {sorted(TLS_MODES)}, got {tls!r}")
        AppSpecFields._require_tls_host(tls, public_host, path)
        AppSpecFields._require_tls_http_port(tls, ports, path)
        return tls

    @staticmethod
    def _require_tls_host(tls: str, public_host: str, path: Path) -> None:
        if tls in {"origin", "acme"} and not public_host:
            raise ValueError(f"{path}: spec.tls={tls} requires spec.publicHost")

    @staticmethod
    def _require_tls_http_port(tls: str, ports: tuple[PortSpec, ...], path: Path) -> None:
        if tls not in {"origin", "acme"}:
            return
        if not ports:
            raise ValueError(
                f"{path}: spec.tls={tls} requires at least one port "
                f"(worker Apps with empty ports use tls: off only)"
            )
        if tls != "acme":
            return
        if any(p.expose == "http" for p in ports):
            return
        raise ValueError(
            f"{path}: spec.tls=acme requires at least one port with expose: http "
            f"(and publicHost). Stream/host/none-only apps cannot use ACME."
        )

    @staticmethod
    def _normalize_tls(raw_tls: Any, path: Path) -> str:
        if isinstance(raw_tls, bool):
            if raw_tls:
                raise ValueError(
                    f"{path}: spec.tls must be one of {sorted(TLS_MODES)} "
                    f"(YAML true is not valid; use 'origin' or 'acme')"
                )
            return "off"
        return str(raw_tls).strip().lower() or "off"

    @staticmethod
    def _parse_source(
        spec: dict[str, Any], path: Path, *, name: str
    ) -> tuple[str, Optional[str], Optional[str], str, str]:
        source = AppSpecFields._resolve_source(spec)
        if source not in {"local", "git", "docker"}:
            raise ValueError(
                f"{path}: spec.source must be 'local', 'git', or 'docker' " f"(got {source!r})"
            )
        ref = str(spec.get("ref", "main")).strip() or "main"
        rel_path = str(spec.get("path", f"apps/{name}")).strip() or f"apps/{name}"
        repo, image = AppSpecFields._source_repo_image(source, spec, path)
        return source, repo, image, ref, rel_path

    @staticmethod
    def _resolve_source(spec: dict[str, Any]) -> str:
        raw = spec.get("source")
        if raw is not None and str(raw).strip():
            return str(raw).strip().lower()
        # Bare/empty specs (e.g. worker with omitted ports) default to local;
        # a repo without source still implies git (historical omit-source shape).
        if spec.get("repo") and str(spec.get("repo")).strip():
            return "git"
        return "local"

    @staticmethod
    def _source_repo_image(
        source: str, spec: dict[str, Any], path: Path
    ) -> tuple[Optional[str], Optional[str]]:
        repo_raw = spec.get("repo")
        image_raw = spec.get("image")
        if source == "git":
            if not repo_raw or not str(repo_raw).strip():
                raise ValueError(f"{path}: spec.repo is required when source=git")
            return str(repo_raw).strip(), None
        if source == "docker":
            return AppSpecFields._docker_repo_image(repo_raw, image_raw, path)
        repo = str(repo_raw).strip() if repo_raw and str(repo_raw).strip() else None
        return repo, None

    @staticmethod
    def _docker_repo_image(repo_raw: Any, image_raw: Any, path: Path) -> tuple[Optional[str], str]:
        if not image_raw or not str(image_raw).strip():
            raise ValueError(f"{path}: spec.image is required when source=docker")
        image = str(image_raw).strip()
        if ":" in image.split("/")[-1]:
            raise ValueError(
                f"{path}: spec.image must be registry/repo without a tag "
                f"(put the tag in spec.ref); got {image!r}"
            )
        repo = str(repo_raw).strip() if repo_raw and str(repo_raw).strip() else None
        return repo, image

    @staticmethod
    def _reject_unknown(spec: dict[str, Any], path: Path) -> None:
        unknown = sorted(set(spec) - _KNOWN_SPEC_KEYS)
        if not unknown:
            return
        keys = ", ".join(unknown)
        raise OperatorError(
            f"{path}: unsupported spec field(s): {keys}\n"
            f"Fix: remove unknown keys from spec "
            f"(see docs/app-manifest.md for supported fields)"
        )

    @staticmethod
    def _parse_build(spec: dict[str, Any], path: Path) -> tuple[Optional[str], Optional[str]]:
        build = spec.get("build")
        if build is None:
            build = {}
        if not isinstance(build, dict):
            raise ValueError(f"{path}: spec.build must be an object")
        context = AppSpecFields._optional_build_str(
            build.get("context"), path, label="spec.build.context"
        )
        dockerfile = AppSpecFields._optional_build_str(
            build.get("dockerfile"), path, label="spec.build.dockerfile"
        )
        return context, dockerfile

    @staticmethod
    def _optional_build_str(value: Any, path: Path, *, label: str) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            hint = (
                "`.` or a relative directory under the app checkout"
                if label.endswith("context")
                else "a filename (e.g. Dockerfile) in .raft/app.yaml"
            )
            short = label.replace("spec.", "")
            raise OperatorError(
                f"{path}: {label} must be a string path, "
                f"got {type(value).__name__}.\n"
                f"Fix: set {short} to {hint}"
            )
        text = value.strip()
        return text or None
