"""Shared manifest writer for AppSpec tests."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

from ...base import RaftTestCase


class ManifestTestCase(RaftTestCase):
    def write_manifest(
        self,
        checkout: Path,
        *,
        name: str = "web",
        context: Optional[str] = ".",
        www: bool = True,
        port: int = 80,
        dockerfile: Optional[str] = None,
        extra_hosts: Optional[Union[str, Sequence[str]]] = None,
        probe: str = "/",
        resources: bool = False,
        source: str = "local",
        public_host: Optional[str] = None,
        repo: Optional[str] = None,
        image: Optional[str] = None,
        tls: str = "off",
        registry_root=None,
    ) -> None:
        lines = self._header_lines(name, public_host, source, tls, www)
        lines.extend(self._optional_lines(repo, image, extra_hosts))
        lines.extend(self._ports_build_ready(port, context, dockerfile, probe, resources))
        path = checkout / ".raft" / "app.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if registry_root is not None:
            reg = Path(registry_root) / "state" / "apps" / f"{name}.yaml"
            reg.parent.mkdir(parents=True, exist_ok=True)
            reg.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    def _header_lines(self, name, public_host, source, tls, www) -> List[str]:
        return [
            "apiVersion: raft/v1",
            "kind: App",
            "metadata:",
            f"  name: {name}",
            "spec:",
            f"  publicHost: {public_host or f'{name}.test'}",
            f"  source: {source}",
            f"  path: apps/{name}",
            f"  tls: {tls}",
            f"  www: {'true' if www else 'false'}",
        ]

    def _optional_lines(self, repo, image, extra_hosts) -> List[str]:
        lines: List[str] = []
        if repo:
            lines.append(f"  repo: {repo}")
        if image:
            lines.append(f"  image: {image}")
        if extra_hosts is None:
            return lines
        if isinstance(extra_hosts, str):
            lines.append(f'  extraHosts: "{extra_hosts}"')
        else:
            lines.append("  extraHosts:")
            lines.extend(f"    - {h}" for h in extra_hosts)
        return lines

    def _ports_build_ready(self, port, context, dockerfile, probe, resources) -> List[str]:
        lines = [
            "  ports:",
            "    - name: http",
            f"      containerPort: {port}",
            "      expose: http",
        ]
        if context is not None:
            lines.extend(["  build:", f"    context: {context}"])
            if dockerfile:
                lines.append(f"    dockerfile: {dockerfile}")
        lines.extend([
            "  readiness:", "    type: http", "    port: http", f"    path: {probe}",
        ])
        if resources:
            lines.extend([
                "  resources:", "    limits:", '      cpu: "250m"', "      memory: 64Mi",
                "    requests:", '      cpu: "50m"', "      memory: 16Mi",
            ])
        return lines
