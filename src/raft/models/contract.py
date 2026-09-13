"""Kubernetes-shaped App manifests (service-owned) and on-VPS registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from .app import App

CONTRACT_API_VERSION = "raft/v1"
CONTRACT_KINDS = frozenset({"App", "Service"})
CONTRACT_REL_CANDIDATES = (
    Path(".raft") / "app.yaml",
    Path(".raft") / "service.yaml",
)
CONTRACT_REL_PATH = CONTRACT_REL_CANDIDATES[0]
REGISTRY_DIR = Path("state") / "apps"

@dataclass(frozen=True)
class ServiceContract:
    port: int = 80
    www: bool = True
    extra_hosts: tuple[str, ...] = ()
    build_context: Optional[str] = None
    dockerfile: Optional[str] = None
    probe_path: str = "/"
    cpus_limit: str = "0.50"
    memory_limit: str = "128M"
    cpus_reservation: str = "0.10"
    memory_reservation: str = "32M"
    metadata_name: Optional[str] = None

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

def contract_path(checkout: Path) -> Path:
    for rel in CONTRACT_REL_CANDIDATES:
        path = checkout / rel
        if path.is_file():
            return path
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

def _port_from_spec(spec: dict[str, Any], path: Path) -> int:
    if "port" in spec and "ports" not in spec:
        port = int(spec["port"])
        if port < 1 or port > 65535:
            raise ValueError(f"{path}: spec.port out of range: {port}")
        return port
    ports = spec.get("ports")
    if ports is None:
        return 80
    if not isinstance(ports, list) or not ports:
        raise ValueError(f"{path}: spec.ports must be a non-empty list when set")
    first = ports[0]
    if not isinstance(first, dict):
        raise ValueError(f"{path}: spec.ports[] entries must be objects")
    raw = first.get("containerPort", first.get("port", 80))
    port = int(raw)
    if port < 1 or port > 65535:
        raise ValueError(f"{path}: containerPort out of range: {port}")
    return port

def _extra_hosts(spec: dict[str, Any], path: Path) -> tuple[str, ...]:
    extra_raw = spec.get("extraHosts", spec.get("extra_hosts")) or []
    if isinstance(extra_raw, str):
        return (extra_raw.strip(),) if extra_raw.strip() else ()
    if isinstance(extra_raw, list):
        return tuple(str(x).strip() for x in extra_raw if str(x).strip())
    raise ValueError(f"{path}: spec.extraHosts must be a string or array")

def _probe_path(spec: dict[str, Any], path: Path) -> str:
    probe = spec.get("readinessProbe") or spec.get("probe") or {}
    if not isinstance(probe, dict):
        raise ValueError(f"{path}: readinessProbe must be an object")
    http_get = probe.get("httpGet") or probe
    if not isinstance(http_get, dict):
        raise ValueError(f"{path}: readinessProbe.httpGet must be an object")
    return str(http_get.get("path", "/")).strip() or "/"

def _resources(spec: dict[str, Any], path: Path) -> tuple[str, str, str, str]:
    resources = spec.get("resources") or {}
    if not isinstance(resources, dict):
        raise ValueError(f"{path}: resources must be an object")
    limits = resources.get("limits") or {}
    requests = resources.get("requests") or resources.get("reservations") or {}
    if not isinstance(limits, dict) or not isinstance(requests, dict):
        raise ValueError(f"{path}: resources.limits/requests must be objects")
    return (
        _parse_cpu(limits.get("cpu", resources.get("cpus_limit")), default="0.50"),
        _parse_memory(
            limits.get("memory", resources.get("memory_limit")), default="128M"
        ),
        _parse_cpu(
            requests.get("cpu", resources.get("cpus_reservation")), default="0.10"
        ),
        _parse_memory(
            requests.get("memory", resources.get("memory_reservation")), default="32M"
        ),
    )

def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: document must be a mapping")
    return data

def parse_app_document(
    data: dict[str, Any],
    *,
    path: Path,
    expect_name: Optional[str] = None,
) -> tuple[App, ServiceContract]:
    api = str(data.get("apiVersion", "")).strip()
    kind = str(data.get("kind", "")).strip()
    if api != CONTRACT_API_VERSION:
        raise ValueError(
            f"{path}: apiVersion must be {CONTRACT_API_VERSION!r}, got {api!r}"
        )
    if kind not in CONTRACT_KINDS:
        raise ValueError(
            f"{path}: kind must be one of {sorted(CONTRACT_KINDS)}, got {kind!r}"
        )

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

    spec = data.get("spec")
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise ValueError(f"{path}: spec must be an object")

    public_host = str(
        spec.get("publicHost", spec.get("public_host", ""))
    ).strip()
    if not public_host:
        raise ValueError(f"{path}: spec.publicHost is required")

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

    port = _port_from_spec(spec, path)
    www = bool(spec.get("www", True))
    extra_hosts = _extra_hosts(spec, path)

    build = spec.get("build") or {}
    if not isinstance(build, dict):
        raise ValueError(f"{path}: spec.build must be an object")
    context = build.get("context")
    build_context = str(context).strip() if context is not None else None
    if build_context == "":
        build_context = None
    dockerfile = build.get("dockerfile")
    dockerfile_s = str(dockerfile).strip() if dockerfile is not None else None
    if dockerfile_s == "":
        dockerfile_s = None

    probe_path = _probe_path(spec, path)
    cpus_limit, memory_limit, cpus_reservation, memory_reservation = _resources(
        spec, path
    )

    contract = ServiceContract(
        port=port,
        www=www,
        extra_hosts=extra_hosts,
        build_context=build_context,
        dockerfile=dockerfile_s,
        probe_path=probe_path,
        cpus_limit=cpus_limit,
        memory_limit=memory_limit,
        cpus_reservation=cpus_reservation,
        memory_reservation=memory_reservation,
        metadata_name=name,
    )
    return app, contract

def load_app_file(
    path: Path,
    *,
    expect_name: Optional[str] = None,
) -> tuple[App, ServiceContract]:
    data = _load_yaml_mapping(path)
    return parse_app_document(data, path=path, expect_name=expect_name)

def load_contract(
    checkout: Path,
    *,
    expect_name: Optional[str] = None,
) -> ServiceContract:
    path = contract_path(checkout)
    if not path.is_file():
        raise FileNotFoundError(
            f"missing service contract: {path} "
            f"(add {CONTRACT_REL_PATH.as_posix()} to the service repo)"
        )
    _, contract = load_app_file(path, expect_name=expect_name)
    return contract

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
    hosts = [a.public_host.lower() for a in apps]
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
        if other_app.public_host.lower() == app.public_host.lower():
            raise ValueError(
                f"publicHost {app.public_host!r} already used by applied app "
                f"{other_app.name!r}"
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
