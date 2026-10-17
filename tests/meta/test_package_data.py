"""Meta guard: setuptools package-data paths must exist under ``src/raft``."""

from __future__ import annotations

import subprocess
from typing import List, Tuple

import pytest

from tests.meta.scan import REPO_ROOT, SRC_RAFT

pytestmark = pytest.mark.meta

_SPA_DIR = SRC_RAFT / "core" / "platform" / "share" / "serve" / "spa"


class TestPackageData:
    """Installed wheels must ship ``core/platform/share`` templates."""

    def test_package_data_globs_resolve_under_src_raft(self) -> None:
        patterns = PackageDataPatterns().raft_globs()
        assert patterns, "expected [tool.setuptools.package-data].raft"
        missing = [p for p in patterns if not any(SRC_RAFT.glob(p))]
        assert not missing, (
            "package-data globs match nothing under src/raft "
            f"(broken uv tool install / raft update):\n  "
            + "\n  ".join(missing)
        )

    def test_bundled_share_root_is_package_data(self) -> None:
        patterns = PackageDataPatterns().raft_globs()
        assert any(p.startswith("core/platform/share/") for p in patterns), (
            "package-data must include core/platform/share/ (not legacy raft/share/)"
        )
        assert (SRC_RAFT / "core/platform/share/compose.yaml").is_file()
        assert (SRC_RAFT / "core/platform/share/nginx").is_dir()

    def test_spa_output_dir_keeps_gitkeep_only_in_git(self) -> None:
        keep = _SPA_DIR / ".gitkeep"
        assert keep.is_file(), f"expected {_SPA_DIR}/.gitkeep so the path exists in git"
        tracked = subprocess.run(
            ["git", "ls-files", "--", str(_SPA_DIR.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert tracked == ["src/raft/core/platform/share/serve/spa/.gitkeep"], tracked


class PackageDataPatterns:
    """Read ``raft`` package-data globs from pyproject.toml without tomllib."""

    def raft_globs(self) -> List[str]:
        lines = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
        return self._globs_in_section(lines)

    def _globs_in_section(self, lines: List[str]) -> List[str]:
        out: List[str] = []
        in_section = False
        in_raft_list = False
        for line in lines:
            stripped = line.strip()
            in_section, in_raft_list, done = self._advance(stripped, in_section, in_raft_list)
            if done:
                break
            if in_raft_list:
                out.extend(self._quoted(stripped))
        return out

    @staticmethod
    def _advance(stripped: str, in_section: bool, in_raft_list: bool) -> Tuple[bool, bool, bool]:
        if stripped == "[tool.setuptools.package-data]":
            return True, False, False
        if in_section and stripped.startswith("[") and stripped.endswith("]"):
            return in_section, in_raft_list, True
        if not in_section:
            return False, False, False
        if stripped.startswith("raft") and "[" in stripped:
            return True, True, False
        if in_raft_list and stripped == "]":
            return True, True, True
        return in_section, in_raft_list, False

    @staticmethod
    def _quoted(line: str) -> List[str]:
        if '"' not in line:
            return []
        start = line.find('"') + 1
        end = line.find('"', start)
        return [line[start:end]] if end > start else []
