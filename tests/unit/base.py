"""Shared test factories and base classes for raft unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence
from unittest.mock import MagicMock

import pytest
import yaml

from raft.models import App, Stack
from raft.models.stack import load_stack
from raft.services.render import StackRenderer


def make_app(
    name: str = "app",
    *,
    public_host: Optional[str] = None,
    source: str = "local",
    path: Optional[str] = None,
    repo: Optional[str] = None,
    ref: str = "main",
    image: Optional[str] = None,
    group: Optional[str] = None,
) -> App:
    return App(
        name=name,
        public_host=public_host or f"{name}.test",
        source=source,
        path=path or f"apps/{name}",
        repo=repo,
        ref=ref,
        image=image,
        group=group,
    )


def make_stack(
    root: Path,
    apps: Optional[Sequence[App]] = None,
    **kwargs,
) -> Stack:
    if apps is None:
        apps = (make_app(),)
    return Stack(root=root, apps=tuple(apps), **kwargs)


def make_local_stack(root: Path, *names: str, **kwargs) -> Stack:
    names = names or ("app",)
    return make_stack(root, tuple(make_app(n) for n in names), **kwargs)


def make_git_app(
    name: str = "svc",
    *,
    repo: str = "git@github.com:org/svc.git",
    public_host: str = "svc.test",
    path: Optional[str] = None,
    ref: str = "main",
) -> App:
    return make_app(
        name,
        public_host=public_host,
        source="git",
        path=path or f"apps/{name}",
        repo=repo,
        ref=ref,
    )


def make_git_stack(
    root: Path,
    *,
    repo: str = "git@github.com:org/svc.git",
    with_local: bool = True,
) -> Stack:
    apps = [make_git_app(repo=repo)]
    if with_local:
        apps.append(make_app("localapp", public_host="local.test"))
    return make_stack(root, apps)


def ensure_orchestrator_root(root: Path) -> None:
    if not (root / "settings.yaml").is_file():
        (root / "settings.yaml").write_text(
            "logging:\n  level: INFO\n" "edge:\n  http: 80\n  https: 443\n",
            encoding="utf-8",
        )
    (root / "state" / "apps").mkdir(parents=True, exist_ok=True)
    (root / "generated").mkdir(parents=True, exist_ok=True)
    (root / "deploy").mkdir(parents=True, exist_ok=True)
    (root / "certs").mkdir(parents=True, exist_ok=True)
    (root / "apps").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)


def ensure_app_checkouts(root: Path, *names: str) -> None:
    for name in names:
        (root / "apps" / name).mkdir(parents=True, exist_ok=True)


def render_stack(root: Path, *, edge: Any = None) -> Path:
    """Ensure checkouts for applied apps, then ``StackRenderer.render()``."""
    stack = load_stack(root)
    ensure_app_checkouts(root, *(app.name for app in stack.apps))
    kwargs: dict[str, Any] = {}
    if edge is not None:
        kwargs["edge"] = edge
    StackRenderer(stack, **kwargs).render()
    return root / "generated"


def _applied_app_spec(
    name: str,
    *,
    public_host: Optional[str],
    source: str,
    path: Optional[str],
    repo: Optional[str],
    ref: str,
    image: Optional[str],
    www: bool,
    build_context: Optional[str],
    port: int,
    tls: str,
    extra: Optional[dict[str, Any]],
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "publicHost": f"{name}.test" if public_host is None else public_host,
        "source": source,
        "ref": ref,
        "path": path or f"apps/{name}",
        "www": www,
        "tls": tls,
        "ports": [{"name": "http", "containerPort": port, "expose": "http"}],
        "readiness": {"type": "http", "port": "http", "path": "/"},
    }
    if repo:
        spec["repo"] = repo
    if image:
        spec["image"] = image
    if source in {"git", "local"} and build_context is not None:
        spec["build"] = {"context": build_context}
    if extra:
        spec.update(extra)
    return spec


def write_applied_app(
    root: Path,
    name: str,
    *,
    public_host: Optional[str] = None,
    source: str = "local",
    path: Optional[str] = None,
    repo: Optional[str] = None,
    ref: str = "main",
    image: Optional[str] = None,
    www: bool = True,
    build_context: Optional[str] = ".",
    port: int = 80,
    tls: str = "off",
    extra: Optional[dict[str, Any]] = None,
) -> Path:
    ensure_orchestrator_root(root)
    spec = _applied_app_spec(
        name,
        public_host=public_host,
        source=source,
        path=path,
        repo=repo,
        ref=ref,
        image=image,
        www=www,
        build_context=build_context,
        port=port,
        tls=tls,
        extra=extra,
    )
    doc = {"apiVersion": "raft/v1", "kind": "App", "metadata": {"name": name}, "spec": spec}
    dest = root / "state" / "apps" / f"{name}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return dest


def write_inventory(root: Path, body: str) -> None:
    ensure_orchestrator_root(root)
    data = yaml.safe_load(body) or {}
    services = data.get("services") or {}
    for name, raw in services.items():
        if not isinstance(raw, dict):
            raise ValueError(f"services.{name} must be a mapping")
        write_applied_app(
            root,
            name,
            public_host=(str(raw["public_host"]) if "public_host" in raw else None),
            source=str(raw.get("source", "local")),
            path=str(raw.get("path", f"apps/{name}")),
            repo=raw.get("repo"),
            ref=str(raw.get("ref", "main")),
            image=raw.get("image"),
            build_context="." if str(raw.get("source", "local")) != "docker" else None,
        )


def write_demo_inventory(root: Path) -> Path:
    write_applied_app(root, "app", public_host="app.test", source="local")
    write_applied_app(root, "other", public_host="other.test", source="local")
    (root / "apps" / "app").mkdir(parents=True, exist_ok=True)
    (root / "apps" / "other").mkdir(parents=True, exist_ok=True)
    return root


def completed(
    stdout: str = "",
    returncode: int = 0,
    stderr: str = "",
) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    m.stderr = stderr
    return m


def git_call_args(shell: MagicMock) -> list[tuple]:
    return [c.args for c in shell.git.call_args_list]


class RaftTestCase:
    @pytest.fixture(autouse=True)
    def _raft_base(self, tmp_path: Path, isolated_raft_ssh_dir: Path) -> None:
        self.tmp_path = tmp_path
        self.ssh_dir = isolated_raft_ssh_dir
        ensure_orchestrator_root(tmp_path)

    def local_stack(self, *names: str, **kwargs) -> Stack:
        return make_local_stack(self.tmp_path, *names, **kwargs)

    def git_stack(self, **kwargs) -> Stack:
        return make_git_stack(self.tmp_path, **kwargs)

    def demo_repo(self) -> Path:
        return write_demo_inventory(self.tmp_path)

    def ensure_checkouts(self, *names: str) -> None:
        ensure_app_checkouts(self.tmp_path, *names)

    def render_applied(self, *, edge: Any = None) -> Path:
        return render_stack(self.tmp_path, edge=edge)
