"""Kubernetes-shaped App manifests (service-owned) and on-VPS registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import re

import yaml

from raft.errors import OperatorError

from .app import App
from .ports import PortSpec, parse_ports
from .readiness import ReadinessSpec, parse_readiness

CONTRACT_API_VERSION = "raft/v1"
CONTRACT_KIND = "App"
CONTRACT_REL_PATH = Path(".raft") / "app.yaml"
REGISTRY_DIR = Path("state") / "apps"
TLS_MODES = frozenset({"off", "origin"})
_GROUP_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class VolumeSpec:
    host_path: str
    container_path: str
    read_only: bool = False
    name: Optional[str] = None


@dataclass(frozen=True)
class AppSpec:
    ports: tuple[PortSpec, ...]
    tls: str = "off"
    readiness: ReadinessSpec = ReadinessSpec()
    www: bool = True
    extra_hosts: tuple[str, ...] = ()
    build_context: Optional[str] = None
    dockerfile: Optional[str] = None
    cpus_limit: str = "0.50"
    memory_limit: str = "128M"
    cpus_reservation: str = "0.10"
    memory_reservation: str = "32M"
    metadata_name: Optional[str] = None
    groups: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    env_file: Optional[str] = None
    env: tuple[tuple[str, str], ...] = ()
    volumes: tuple[VolumeSpec, ...] = ()

    def server_names(self, public_host: str) -> tuple[str, ...]:
        names: list[str] = [public_host]
        if self.www:
            names.append(f"www.{public_host}")
        for host in self.extra_hosts:
            h = host.strip()
            if h:
                names.append(h)
        seen: set[str] = set()
        out: list[str] = []
        for name in names:
            if name not in seen:
                seen.add(name)
                out.append(name)
        return tuple(out)

    def http_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "http")

    def stream_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "stream")

    def host_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "host")

    def none_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "none")


def contract_path(checkout: Path) -> Path:
    return checkout / CONTRACT_REL_PATH


def registry_dir(root: Path) -> Path:
    return root / REGISTRY_DIR


def registry_path(root: Path, name: str) -> Path:
    return registry_dir(root) / f"{name}.yaml"


def _parse_cpu(value: Any, *, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).strip()
    if not text:
        return default
    if text.endswith("m") and text[:-1].replace(".", "", 1).isdigit():
        millis = float(text[:-1])
        return f"{millis / 1000.0:g}"
    return text


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


def _extra_hosts(spec: dict[str, Any], path: Path) -> tuple[str, ...]:
    extra_raw = spec.get("extraHosts", spec.get("extra_hosts"))
    if extra_raw is None:
        return ()
    if isinstance(extra_raw, str):
        return (extra_raw.strip(),) if extra_raw.strip() else ()
    if isinstance(extra_raw, list):
        return tuple(str(x).strip() for x in extra_raw if str(x).strip())
    raise ValueError(f"{path}: spec.extraHosts must be a string or array")


def _parse_name_list(
    raw: Any,
    *,
    path: Path,
    label: str,
    pattern: Any = None,
) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        items = [raw.strip()] if raw.strip() else []
    elif isinstance(raw, list):
        items = [str(x).strip() for x in raw if str(x).strip()]
    else:
        raise ValueError(f"{path}: {label} must be a string or array")
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if pattern is not None and not pattern.match(item):
            raise ValueError(
                f"{path}: {label} entry {item!r} must match {pattern.pattern}"
            )
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def _parse_env_file(spec: dict[str, Any], path: Path) -> Optional[str]:
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


def _parse_env(spec: dict[str, Any], path: Path) -> tuple[tuple[str, str], ...]:
    raw = spec.get("env")
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: spec.env must be an object")
    out: list[tuple[str, str]] = []
    for key, value in raw.items():
        k = str(key).strip()
        if not k:
            raise ValueError(f"{path}: spec.env keys must be non-empty strings")
        if value is None:
            raise ValueError(f"{path}: spec.env[{k!r}] must not be null")
        out.append((k, str(value)))
    return tuple(out)


def _parse_volumes(spec: dict[str, Any], path: Path) -> tuple[VolumeSpec, ...]:
    raw = spec.get("volumes")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"{path}: spec.volumes must be a list")
    volumes: list[VolumeSpec] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: spec.volumes[{index}] must be an object")
        host = entry.get("hostPath", entry.get("host_path"))
        container = entry.get("containerPath", entry.get("container_path"))
        if host is None or not str(host).strip():
            raise ValueError(f"{path}: spec.volumes[{index}].hostPath is required")
        if container is None or not str(container).strip():
            raise ValueError(f"{path}: spec.volumes[{index}].containerPath is required")
        host_s = str(host).strip()
        container_s = str(container).strip()
        if ".." in Path(host_s).parts:
            raise ValueError(
                f"{path}: spec.volumes[{index}].hostPath must not contain '..'"
            )
        if not container_s.startswith("/"):
            raise ValueError(
                f"{path}: spec.volumes[{index}].containerPath must be absolute"
            )
        read_only = entry.get("readOnly", entry.get("read_only", False))
        if not isinstance(read_only, bool):
            raise ValueError(
                f"{path}: spec.volumes[{index}].readOnly must be a boolean"
            )
        name_raw = entry.get("name")
        name = str(name_raw).strip() if name_raw is not None else None
        if name == "":
            name = None
        volumes.append(
            VolumeSpec(
                host_path=host_s,
                container_path=container_s,
                read_only=read_only,
                name=name,
            )
        )
    return tuple(volumes)


def _resources(spec: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
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
    return (
        _parse_cpu(limits.get("cpu", resources.get("cpus_limit")), default="0.50"),
        _parse_memory(limits.get("memory", resources.get("memory_limit")), default="128M"),
        _parse_cpu(requests.get("cpu", resources.get("cpus_reservation")), default="0.10"),
        _parse_memory(requests.get("memory", resources.get("memory_reservation")), default="32M"),
    )


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


def parse_app_document(
    data: dict[str, Any],
    *,
    path: Path,
    expect_name: Optional[str] = None,
) -> tuple[App, AppSpec]:
    api = str(data.get("apiVersion", "")).strip()
    kind = str(data.get("kind", "")).strip()
    if api != CONTRACT_API_VERSION:
        raise ValueError(f"{path}: apiVersion must be {CONTRACT_API_VERSION!r}, got {api!r}")
    if kind != CONTRACT_KIND:
        raise ValueError(f"{path}: kind must be {CONTRACT_KIND!r}, got {kind!r}")

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: metadata must be an object")
    meta_name = metadata.get("name")
    name = str(meta_name).strip() if meta_name is not None else ""
    if not name:
        raise ValueError(f"{path}: metadata.name is required")
    if expect_name and name != expect_name:
        raise ValueError(f"{path}: metadata.name {name!r} does not match expected {expect_name!r}")

    spec = data.get("spec")
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise ValueError(f"{path}: spec must be an object")

    ports = parse_ports(spec, path)
    needs_host = any(p.expose == "http" for p in ports)
    public_host = str(spec.get("publicHost", spec.get("public_host", ""))).strip()
    if needs_host and not public_host:
        raise ValueError(f"{path}: spec.publicHost is required when any port uses expose=http")

    raw_tls = spec.get("tls", "off")
    if isinstance(raw_tls, bool):
        if raw_tls:
            raise ValueError(
                f"{path}: spec.tls must be one of {sorted(TLS_MODES)} "
                f"(YAML true is not valid; use 'origin')"
            )
        tls = "off"
    else:
        tls = str(raw_tls).strip().lower() or "off"
    if tls not in TLS_MODES:
        raise ValueError(f"{path}: spec.tls must be one of {sorted(TLS_MODES)}, got {tls!r}")
    if tls == "origin" and not public_host:
        raise ValueError(f"{path}: spec.tls=origin requires spec.publicHost")

    source = str(spec.get("source", "git")).strip().lower()
    if source not in {"local", "git", "docker"}:
        raise ValueError(
            f"{path}: spec.source must be 'local', 'git', or 'docker' (got {source!r})"
        )

    ref = str(spec.get("ref", "main")).strip() or "main"
    rel_path = str(spec.get("path", f"apps/{name}")).strip() or f"apps/{name}"

    repo_raw = spec.get("repo")
    image_raw = spec.get("image")
    repo: Optional[str] = None
    image: Optional[str] = None

    if source == "git":
        if not repo_raw or not str(repo_raw).strip():
            raise ValueError(f"{path}: spec.repo is required when source=git")
        repo = str(repo_raw).strip()
    elif source == "docker":
        if not image_raw or not str(image_raw).strip():
            raise ValueError(f"{path}: spec.image is required when source=docker")
        image = str(image_raw).strip()
        if ":" in image.split("/")[-1]:
            raise ValueError(
                f"{path}: spec.image must be registry/repo without a tag "
                f"(put the tag in spec.ref); got {image!r}"
            )
        if repo_raw and str(repo_raw).strip():
            repo = str(repo_raw).strip()
    else:
        repo = str(repo_raw).strip() if repo_raw and str(repo_raw).strip() else None

    app = App(
        name=name,
        public_host=public_host,
        source=source,
        path=rel_path,
        repo=repo,
        ref=ref,
        image=image,
    )

    www_raw = spec.get("www", True)
    if not isinstance(www_raw, bool):
        raise OperatorError(
            f"{path}: spec.www must be a boolean, got {www_raw!r}.\n"
            f"Fix: use `www: true` or `www: false` (unquoted) in .raft/app.yaml"
        )
    www = www_raw
    extra_hosts = _extra_hosts(spec, path)

    build = spec.get("build")
    if build is None:
        build = {}
    if not isinstance(build, dict):
        raise ValueError(f"{path}: spec.build must be an object")
    context = build.get("context")
    if context is not None and not isinstance(context, str):
        raise OperatorError(
            f"{path}: spec.build.context must be a string path, got {type(context).__name__}.\n"
            f"Fix: set build.context to `.` or a relative directory under the app checkout"
        )
    build_context = context.strip() if context is not None else None
    if build_context == "":
        build_context = None
    dockerfile = build.get("dockerfile")
    if dockerfile is not None and not isinstance(dockerfile, str):
        raise OperatorError(
            f"{path}: spec.build.dockerfile must be a string, got {type(dockerfile).__name__}.\n"
            f"Fix: set build.dockerfile to a filename (e.g. Dockerfile) in .raft/app.yaml"
        )
    dockerfile_s = dockerfile.strip() if dockerfile is not None else None
    if dockerfile_s == "":
        dockerfile_s = None

    readiness = parse_readiness(spec, ports, path)
    cpus_limit, memory_limit, cpus_reservation, memory_reservation = _resources(spec, path)
    groups = _parse_name_list(
        spec.get("groups"), path=path, label="spec.groups", pattern=_GROUP_NAME
    )
    depends_on = _parse_name_list(
        spec.get("dependsOn", spec.get("depends_on")),
        path=path,
        label="spec.dependsOn",
    )
    env_file = _parse_env_file(spec, path)
    env = _parse_env(spec, path)
    volumes = _parse_volumes(spec, path)

    app_spec = AppSpec(
        ports=ports,
        tls=tls,
        readiness=readiness,
        www=www,
        extra_hosts=extra_hosts,
        build_context=build_context,
        dockerfile=dockerfile_s,
        cpus_limit=cpus_limit,
        memory_limit=memory_limit,
        cpus_reservation=cpus_reservation,
        memory_reservation=memory_reservation,
        metadata_name=name,
        groups=groups,
        depends_on=depends_on,
        env_file=env_file,
        env=env,
        volumes=volumes,
    )
    return app, app_spec


def load_app_file(
    path: Path,
    *,
    expect_name: Optional[str] = None,
) -> tuple[App, AppSpec]:
    if not path.is_file():
        raise OperatorError(
            f"missing applied App manifest: {path}\n"
            f"Fix: re-apply the app (`raft apply …`) or restore the file under ~/.raft/state/apps/"
        )
    data = _load_yaml_mapping(path)
    return parse_app_document(data, path=path, expect_name=expect_name)


def load_contract(
    checkout: Path,
    *,
    expect_name: Optional[str] = None,
) -> AppSpec:
    path = contract_path(checkout)
    if not path.is_file():
        raise FileNotFoundError(
            f"missing App manifest: {path} "
            f"(add {CONTRACT_REL_PATH.as_posix()} to the service repo)"
        )
    _, app_spec = load_app_file(path, expect_name=expect_name)
    return app_spec


def load_registry(root: Path) -> tuple[App, ...]:
    directory = registry_dir(root)
    if not directory.is_dir():
        return ()
    apps: list[App] = []
    for path in sorted(directory.glob("*.yaml")):
        app, _ = load_app_file(path)
        if path.stem != app.name:
            raise ValueError(
                f"{path}: filename stem {path.stem!r} must match metadata.name {app.name!r}"
            )
        apps.append(app)
    hosts = [a.public_host.lower() for a in apps if a.public_host]
    if len(hosts) != len(set(hosts)):
        raise ValueError("registry: publicHost values must be unique across applied apps")
    return tuple(apps)


def write_registry_app(root: Path, document: dict[str, Any]) -> Path:
    path_hint = Path("<apply>")
    app, _ = parse_app_document(document, path=path_hint)
    directory = registry_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    dest = registry_path(root, app.name)
    for other in directory.glob("*.yaml"):
        if other.stem == app.name:
            continue
        other_app, _ = load_app_file(other)
        if (
            app.public_host
            and other_app.public_host
            and other_app.public_host.lower() == app.public_host.lower()
        ):
            raise ValueError(
                f"publicHost {app.public_host!r} already used by applied app " f"{other_app.name!r}"
            )
    text = yaml.safe_dump(document, sort_keys=False, default_flow_style=False)
    dest.write_text(text, encoding="utf-8")
    return dest


def delete_registry_app(root: Path, name: str) -> bool:
    path = registry_path(root, name)
    if not path.is_file():
        return False
    path.unlink()
    return True
