"""Build and run the fresh-install Docker smoke image."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "tests" / "e2e" / "fresh_install" / "Dockerfile"
DEFAULT_REF = "workspace"
# E2E CI job is Py 3.9 only; run the image build once there.
_CI_ONCE_PY = (3, 9)


class FreshInstallRef:
    """``RAFT_E2E_REF`` when set, else ``workspace`` (packaging from build context)."""

    def resolve(self) -> str:
        explicit = (os.environ.get("RAFT_E2E_REF") or "").strip()
        if explicit:
            return explicit
        return DEFAULT_REF


class FreshInstallGate:
    """Whether this pytest worker should run the fresh-install image build."""

    def should_run(self) -> bool:
        flag = (os.environ.get("RAFT_E2E_FRESH_INSTALL") or "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            return False
        if flag in ("1", "true", "yes", "on"):
            return True
        if os.environ.get("CI"):
            return sys.version_info[:2] == _CI_ONCE_PY
        return True


class FreshInstallSpaBake:
    def ensure(self, repo_root: Path) -> None:
        index = repo_root / "src/raft/core/platform/share/serve/spa/index.html"
        if index.is_file():
            return
        spa = repo_root / "src" / "spa"
        for args in (["npm", "ci"], ["npm", "run", "build"]):
            proc = subprocess.run(
                args,
                cwd=str(spa),
                check=False,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise AssertionError(
                    f"{' '.join(args)} failed ({proc.returncode}):\n{detail}"
                )
        if not index.is_file():
            raise AssertionError(f"SPA bake did not produce {index}")


class FreshInstallImage:
    """``docker build`` + ``docker run`` for the fresh-install smoke."""

    def __init__(self, *, ref: Optional[str] = None, repo_root: Optional[Path] = None) -> None:
        self.ref = ref if ref is not None else FreshInstallRef().resolve()
        self.repo_root = repo_root or REPO_ROOT
        self.tag = f"raft-e2e-fresh-install:{uuid.uuid4().hex[:12]}"

    def run(self) -> None:
        try:
            self._build()
            self._smoke()
        finally:
            self._rmi()

    def _build(self) -> None:
        if self.ref == "workspace":
            FreshInstallSpaBake().ensure(self.repo_root)
        self._docker(
            [
                "build",
                "-f",
                str(DOCKERFILE),
                "--build-arg",
                f"RAFT_REF={self.ref}",
                "-t",
                self.tag,
                str(self.repo_root),
            ],
            timeout=600,
        )

    def _smoke(self) -> None:
        self._docker(["run", "--rm", self.tag], timeout=180)

    def _rmi(self) -> None:
        subprocess.run(
            ["docker", "rmi", "-f", self.tag],
            check=False,
            capture_output=True,
            timeout=60,
        )

    @staticmethod
    def _docker(args: List[str], *, timeout: int) -> None:
        proc = subprocess.run(
            ["docker", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode == 0:
            return
        detail = (proc.stderr or proc.stdout or "").strip()
        raise AssertionError(
            f"docker {' '.join(args[:3])}… failed ({proc.returncode}):\n{detail}"
        )
