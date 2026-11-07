"""Persist host install version into Compose image build contexts.

Dashboard/controller images load ``raft`` via ``PYTHONPATH`` without
dist-info, so ``importlib.metadata`` cannot see the Release wheel version.
Template sync writes this stamp beside the copied package; the container
reads it as the operator-facing SoT. Git-ref installs also stamp after
``uv tool install`` so baked path installs keep commit identity.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


STAMP_FILENAME = "_install_stamp.json"


class InstallStamp:
    """Read/write ``_install_stamp.json`` next to the ``raft`` package root."""

    def write(
        self,
        package_dir: Path,
        *,
        package: str,
        detail: Optional[str],
        commit: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        payload: Dict[str, str] = {"package": package}
        if detail:
            payload["detail"] = detail
        if commit and commit.strip():
            payload["commit"] = commit.strip()
        if repo and repo.strip():
            payload["repo"] = repo.strip()
        path = package_dir / STAMP_FILENAME
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    def read(self, package_dir: Optional[Path] = None) -> Optional[Dict[str, str]]:
        path = (package_dir or self._package_dir()) / STAMP_FILENAME
        if not path.is_file():
            return None
        return self._parse(path.read_text(encoding="utf-8"))

    @staticmethod
    def _package_dir() -> Path:
        import raft

        return Path(raft.__file__).resolve().parent

    def _parse(self, raw: str) -> Optional[Dict[str, str]]:
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        package = data.get("package")
        if not isinstance(package, str) or not package.strip():
            return None
        out: Dict[str, str] = {"package": package.strip()}
        for key in ("detail", "commit", "repo"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                out[key] = value.strip()
        return out
