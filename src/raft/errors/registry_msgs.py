"""Container registry pull CTAs (GHCR / docker login)."""

from typing import List, Optional, Tuple
from urllib.parse import quote

from .cta import CtaFormatter

__all__ = ["RegistryMessages"]


class RegistryMessages:
    """Private registry unauthorized CTAs and doctor fix text."""

    @staticmethod
    def looks_like_registry_unauthorized(text: str) -> bool:
        lower = text.lower()
        if "unauthorized" in lower:
            return True
        if "authentication required" in lower:
            return True
        if "denied" in lower and ("pull" in lower or "package" in lower or "ghcr" in lower):
            return True
        return False

    @staticmethod
    def is_ghcr_image(image: str) -> bool:
        return image.strip().lower().startswith("ghcr.io/")

    @staticmethod
    def ghcr_pat_create_url(*, description: str = "raft-ghcr-pull") -> str:
        """Deep-link to GitHub classic PAT creation with only ``read:packages``."""
        return (
            "https://github.com/settings/tokens/new"
            f"?scopes=read:packages&description={quote(description, safe='')}"
        )

    @classmethod
    def registry_login_fix_steps(
        cls,
        image: str,
        *,
        app: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> List[str]:
        """Ordered operator steps to pull a (likely private) image on the VPS."""
        token_step, login = cls._credential_steps(image, app=app)
        return [
            token_step,
            "Generate the token and copy it once",
            login,
            f"docker pull {image}",
            cls._retry_step(app=app, repo=repo),
        ]

    @classmethod
    def _credential_steps(cls, image: str, *, app: Optional[str]) -> Tuple[str, str]:
        if cls.is_ghcr_image(image):
            desc = f"raft-ghcr-{app}" if app else "raft-ghcr-pull"
            token_step = (
                f"Open {cls.ghcr_pat_create_url(description=desc)} "
                "(classic PAT, read:packages only)"
            )
            login = (
                "echo 'YOUR_PAT' | docker login ghcr.io -u YOUR_GITHUB_USERNAME "
                "--password-stdin"
            )
            return token_step, login
        return (
            "Create a registry credential that can pull this image",
            "docker login <registry>   # credentials for this image's registry",
        )

    @staticmethod
    def _retry_step(*, app: Optional[str], repo: Optional[str]) -> str:
        if repo:
            return (
                f"raft sync {app}   # or: raft apply --git {repo}"
                if app
                else f"raft apply --git {repo}"
            )
        if app:
            return f"raft sync {app}   # or re-run: raft apply --git <repo>"
        return "raft sync <app>   # or re-run: raft apply --git <repo>"

    @classmethod
    def registry_unauthorized_message(
        cls,
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
        for i, step in enumerate(cls.registry_login_fix_steps(image, app=app, repo=repo), start=1):
            lines.append(f"  {i}. {step}")
        first = CtaFormatter.first_line(detail)
        if first:
            lines.extend(["", f"(docker: {first})"])
        return "\n".join(lines)

    @classmethod
    def missing_image_doctor_fix(
        cls,
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
        for i, step in enumerate(cls.registry_login_fix_steps(image, app=app, repo=repo), start=1):
            lines.append(f"{i}. {step}")
        return "\n".join(lines)
