"""Parse ``spec.build.context`` / ``spec.build.dockerfile``."""

from pathlib import Path
from typing import Any, Optional

from raft.core.core.errors.cta import OperatorError


class AppBuildFields:
    """Parse optional App build context and Dockerfile paths."""

    @staticmethod
    def parse(spec: dict[str, Any], path: Path) -> tuple[Optional[str], Optional[str]]:
        build = spec.get("build")
        if build is None:
            build = {}
        if not isinstance(build, dict):
            raise ValueError(f"{path}: spec.build must be an object")
        context = AppBuildFields._optional_str(
            build.get("context"), path, label="spec.build.context"
        )
        dockerfile = AppBuildFields._optional_str(
            build.get("dockerfile"), path, label="spec.build.dockerfile"
        )
        return context, dockerfile

    @staticmethod
    def _optional_str(value: Any, path: Path, *, label: str) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            hint = (
                "`.` or a relative directory under the app checkout"
                if label.endswith("context")
                else "a filename (e.g. Dockerfile) in .raft/app.yaml"
            )
            short = label.replace("spec.", "")
            raise OperatorError(
                f"{path}: {label} must be a string path, "
                f"got {type(value).__name__}.\n"
                f"Fix: set {short} to {hint}"
            )
        text = value.strip()
        return text or None
