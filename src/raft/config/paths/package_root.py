"""Locate packaged Compose/nginx templates (``src/raft/share``)."""

from pathlib import Path
from typing import Optional

from ...errors.cta import OperatorError


class PackageRootFinder:
    """Find the raft share root that contains ``compose.yaml`` + ``nginx/``."""

    def find(self, start: Optional[Path] = None) -> Path:
        bundled = self._bundled_share()
        if self._is_package_root(bundled):
            return bundled
        here = (start or Path.cwd()).resolve()
        for candidate in [here, *here.parents]:
            if self._is_package_root(candidate):
                return candidate
        pkg = Path(__file__).resolve().parent
        for candidate in [pkg, *pkg.parents]:
            if self._is_package_root(candidate):
                return candidate
        raise OperatorError(
            "could not find raft package templates (compose.yaml + nginx/).\n"
            "Fix: reinstall raft (`raft update`) or run from a checkout that "
            "includes src/raft/share/"
        )

    def _bundled_share(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "share"

    @staticmethod
    def _is_package_root(candidate: Path) -> bool:
        return (candidate / "compose.yaml").is_file() and (candidate / "nginx").is_dir()
