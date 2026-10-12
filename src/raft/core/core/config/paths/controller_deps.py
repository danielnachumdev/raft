"""Synthesize controller ``pyproject.toml`` from the installed raft distribution."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import requires as distribution_requires
from pathlib import Path
from typing import Optional

from .constants import CONTROLLER_PYPROJECT


class ControllerDepsPyproject:
    """Locate or synthesize ``pyproject.toml`` for the controller image build."""

    def find_raft_pyproject(self, package_root: Path) -> Optional[Path]:
        for directory in (package_root, *package_root.parents):
            candidate = directory / CONTROLLER_PYPROJECT
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8")
            if 'name = "raft"' in text or "name = 'raft'" in text:
                return candidate
        return None

    def write_from_installed(self, dest: Path) -> None:
        try:
            reqs = distribution_requires("raft")
        except PackageNotFoundError as exc:
            raise FileNotFoundError(
                "controller build needs pyproject.toml (checkout) or an installed "
                "raft distribution to read dependencies"
            ) from exc
        deps = self._main_deps_from_requires(reqs)
        if not deps:
            raise FileNotFoundError(
                "installed raft distribution has no main dependencies for controller"
            )
        dest.write_text(self._controller_pyproject_text(deps), encoding="utf-8")

    def _main_deps_from_requires(self, reqs) -> list:
        if not reqs:
            raise FileNotFoundError(
                "installed raft distribution has no requires; cannot build controller deps"
            )
        deps: list = []
        for raw in reqs:
            if ";" in raw:
                name_part, marker = raw.split(";", 1)
                if "extra" in marker:
                    continue
                deps.append(name_part.strip())
            else:
                deps.append(raw.strip())
        return deps

    @staticmethod
    def _controller_pyproject_text(deps: list) -> str:
        lines = [
            "[project]",
            'name = "raft-controller-deps"',
            'version = "0"',
            'requires-python = ">=3.9"',
            "dependencies = [",
        ]
        for dep in deps:
            escaped = dep.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  "{escaped}",')
        lines.append("]")
        return "\n".join(lines) + "\n"
