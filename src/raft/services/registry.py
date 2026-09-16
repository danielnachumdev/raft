"""Container registry pull errors (GHCR / docker login)."""

from __future__ import annotations


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


def registry_login_fix_steps(image: str) -> list[str]:
    """Ordered operator steps to pull a (likely private) image on the VPS."""
    login = (
        "echo 'YOUR_PAT' | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin"
        if is_ghcr_image(image)
        else "docker login <registry>   # credentials for this image's registry"
    )
    return [
        "GitHub → Settings → Developer settings → Personal access tokens (classic)",
        "Create a token with only read:packages",
        login,
        f"docker pull {image}",
        "raft sync <app>   # or re-run: raft apply --git <repo>",
    ]


def registry_unauthorized_message(image: str, *, detail: str = "") -> str:
    """Single call-to-action for a failed ``docker pull`` (private GHCR, etc.)."""
    lines = [
        f"cannot pull {image}: registry unauthorized.",
        "",
        "Private images need docker registry login on this VPS.",
        "`raft auth` (git deploy keys) does not authenticate GHCR pulls.",
        "",
        "fix (as the raft user):",
    ]
    for i, step in enumerate(registry_login_fix_steps(image), start=1):
        lines.append(f"  {i}. {step}")
    if detail:
        first = detail.splitlines()[0].strip()
        if first:
            lines.extend(["", f"(docker: {first})"])
    return "\n".join(lines)


def missing_image_doctor_fix(image: str) -> str:
    """Doctor ``fix:`` text when the Compose pin image is not present locally."""
    lines = [
        f"image not on this VPS yet ({image}).",
        "`raft auth` does not pull images — login to the registry, then sync:",
    ]
    for i, step in enumerate(registry_login_fix_steps(image), start=1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)
