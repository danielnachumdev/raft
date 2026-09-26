"""Container registry pull CTAs (GHCR / docker login)."""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from .cta import first_line


def looks_like_registry_unauthorized(text: str) -> bool:
    lower = text.lower()
    if "unauthorized" in lower:
        return True
    if "authentication required" in lower:
        return True
    if "denied" in lower and ("pull" in lower or "package" in lower or "ghcr" in lower):
        return True
    return False


def is_ghcr_image(image: str) -> bool:
    return image.strip().lower().startswith("ghcr.io/")


def ghcr_pat_create_url(*, description: str = "raft-ghcr-pull") -> str:
    """Deep-link to GitHub classic PAT creation with only ``read:packages``."""
    return (
        "https://github.com/settings/tokens/new"
        f"?scopes=read:packages&description={quote(description, safe='')}"
    )


def registry_login_fix_steps(
    image: str,
    *,
    app: Optional[str] = None,
    repo: Optional[str] = None,
) -> list[str]:
    """Ordered operator steps to pull a (likely private) image on the VPS."""
    token_step, login = _registry_credential_steps(image, app=app)
    return [
        token_step,
        "Generate the token and copy it once",
        login,
        f"docker pull {image}",
        _registry_retry_step(app=app, repo=repo),
    ]


def _registry_credential_steps(image: str, *, app: Optional[str]) -> tuple[str, str]:
    if is_ghcr_image(image):
        desc = f"raft-ghcr-{app}" if app else "raft-ghcr-pull"
        token_step = (
            f"Open {ghcr_pat_create_url(description=desc)} " "(classic PAT, read:packages only)"
        )
        login = "echo 'YOUR_PAT' | docker login ghcr.io -u YOUR_GITHUB_USERNAME " "--password-stdin"
        return token_step, login
    return (
        "Create a registry credential that can pull this image",
        "docker login <registry>   # credentials for this image's registry",
    )


def _registry_retry_step(*, app: Optional[str], repo: Optional[str]) -> str:
    if repo:
        return (
            f"raft sync {app}   # or: raft apply --git {repo}"
            if app
            else f"raft apply --git {repo}"
        )
    if app:
        return f"raft sync {app}   # or re-run: raft apply --git <repo>"
    return "raft sync <app>   # or re-run: raft apply --git <repo>"


def registry_unauthorized_message(
    image: str,
    *,
    detail: str = "",
    app: Optional[str] = None,
    repo: Optional[str] = None,
) -> str:
    """Single call-to-action for a failed ``docker pull`` (private GHCR, etc.)."""
    lines = [
        f"cannot pull {image}: registry unauthorized.",
        "",
        "Private images need docker registry login on this VPS.",
        "`raft auth` (git deploy keys) does not authenticate GHCR pulls.",
        "",
        "Fix (as the raft user):",
    ]
    for i, step in enumerate(registry_login_fix_steps(image, app=app, repo=repo), start=1):
        lines.append(f"  {i}. {step}")
    first = first_line(detail)
    if first:
        lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def missing_image_doctor_fix(
    image: str,
    *,
    app: Optional[str] = None,
    repo: Optional[str] = None,
) -> str:
    """Doctor ``fix:`` text when the Compose pin image is not present locally."""
    lines = [
        f"image not on this VPS yet ({image}).",
        "`raft auth` does not pull images — login to the registry, then sync:",
    ]
    for i, step in enumerate(registry_login_fix_steps(image, app=app, repo=repo), start=1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)
