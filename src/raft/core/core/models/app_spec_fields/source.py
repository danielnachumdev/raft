"""Parse ``spec.source`` / repo / image / ref / path."""

from pathlib import Path
from typing import Any, Optional


class AppSourceFields:
    """Parse App source identity (local / git / docker)."""

    @staticmethod
    def parse(
        spec: dict[str, Any], path: Path, *, name: str
    ) -> tuple[str, Optional[str], Optional[str], str, str]:
        source = AppSourceFields._resolve_source(spec)
        if source not in {"local", "git", "docker"}:
            raise ValueError(
                f"{path}: spec.source must be 'local', 'git', or 'docker' "
                f"(got {source!r})"
            )
        ref = str(spec.get("ref", "main")).strip() or "main"
        default = f"services/{name}/checkout"
        rel_path = str(spec.get("path", default)).strip() or default
        repo, image = AppSourceFields._repo_image(source, spec, path)
        return source, repo, image, ref, rel_path

    @staticmethod
    def _resolve_source(spec: dict[str, Any]) -> str:
        raw = spec.get("source")
        if raw is not None and str(raw).strip():
            return str(raw).strip().lower()
        # Bare/empty specs (e.g. worker with omitted ports) default to local;
        # a repo without source still implies git (historical omit-source shape).
        if spec.get("repo") and str(spec.get("repo")).strip():
            return "git"
        return "local"

    @staticmethod
    def _repo_image(
        source: str, spec: dict[str, Any], path: Path
    ) -> tuple[Optional[str], Optional[str]]:
        repo_raw = spec.get("repo")
        image_raw = spec.get("image")
        if source == "git":
            if not repo_raw or not str(repo_raw).strip():
                raise ValueError(f"{path}: spec.repo is required when source=git")
            return str(repo_raw).strip(), None
        if source == "docker":
            return AppSourceFields._docker_repo_image(repo_raw, image_raw, path)
        repo = str(repo_raw).strip() if repo_raw and str(repo_raw).strip() else None
        return repo, None

    @staticmethod
    def _docker_repo_image(
        repo_raw: Any, image_raw: Any, path: Path
    ) -> tuple[Optional[str], str]:
        if not image_raw or not str(image_raw).strip():
            raise ValueError(f"{path}: spec.image is required when source=docker")
        image = str(image_raw).strip()
        if ":" in image.split("/")[-1]:
            raise ValueError(
                f"{path}: spec.image must be registry/repo without a tag "
                f"(put the tag in spec.ref); got {image!r}"
            )
        repo = str(repo_raw).strip() if repo_raw and str(repo_raw).strip() else None
        return repo, image
