"""Write applied App YAML under a temporary raft data home."""

from pathlib import Path
from typing import Any, Optional

import yaml

from .orchestrator_root import OrchestratorRoot


class AppliedInventory(OrchestratorRoot):
    @classmethod
    def write_applied_app(
        cls,
        root: Path,
        name: str,
        *,
        public_host: Optional[str] = None,
        source: str = "local",
        path: Optional[str] = None,
        repo: Optional[str] = None,
        ref: str = "main",
        image: Optional[str] = None,
        build_context: Optional[str] = ".",
        port: int = 80,
        tls: str = "off",
        extra: Optional[dict[str, Any]] = None,
    ) -> Path:
        cls.ensure_orchestrator_root(root)
        spec = cls._applied_app_spec(
            name,
            public_host=public_host,
            source=source,
            path=path,
            repo=repo,
            ref=ref,
            image=image,
            build_context=build_context,
            port=port,
            tls=tls,
            extra=extra,
        )
        return cls._write_app_yaml(root, name, spec)

    @classmethod
    def _write_app_yaml(cls, root: Path, name: str, spec: dict[str, Any]) -> Path:
        doc = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": name},
            "spec": spec,
        }
        dest = root / "services" / name / "app.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        return dest

    @classmethod
    def write_inventory(cls, root: Path, body: str) -> None:
        cls.ensure_orchestrator_root(root)
        data = yaml.safe_load(body) or {}
        services = data.get("services") or {}
        for name, raw in services.items():
            if not isinstance(raw, dict):
                raise ValueError(f"services.{name} must be a mapping")
            default_path = f"services/{name}/checkout"
            cls.write_applied_app(
                root,
                name,
                public_host=(str(raw["public_host"]) if "public_host" in raw else None),
                source=str(raw.get("source", "local")),
                path=str(raw.get("path", default_path)),
                repo=raw.get("repo"),
                ref=str(raw.get("ref", "main")),
                image=raw.get("image"),
                build_context="." if str(raw.get("source", "local")) != "docker" else None,
            )

    @classmethod
    def write_demo_inventory(cls, root: Path) -> Path:
        cls.write_applied_app(root, "app", public_host="app.test", source="local")
        cls.write_applied_app(root, "other", public_host="other.test", source="local")
        cls.ensure_app_checkouts(root, "app", "other")
        return root

    @classmethod
    def _applied_app_spec(
        cls,
        name: str,
        *,
        public_host: Optional[str],
        source: str,
        path: Optional[str],
        repo: Optional[str],
        ref: str,
        image: Optional[str],
        build_context: Optional[str],
        port: int,
        tls: str,
        extra: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "publicHost": f"{name}.test" if public_host is None else public_host,
            "source": source,
            "ref": ref,
            "path": path or f"services/{name}/checkout",
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
