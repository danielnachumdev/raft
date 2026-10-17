"""Container registry pull CTAs (GHCR / docker login)."""

from __future__ import annotations

import json
import os
from pathlib import Path
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
        if "failed to authorize" in lower:
            return True
        if "error from registry" in lower and "denied" in lower:
            return True
        if "denied" in lower and ("pull" in lower or "package" in lower or "ghcr" in lower):
            return True
        return False

    @staticmethod
    def is_ghcr_image(image: str) -> bool:
        return image.strip().lower().startswith("ghcr.io/")

    @staticmethod
    def registry_host(image: str) -> str:
        """Registry hostname for ``image`` (e.g. ``ghcr.io``), else ``docker.io``."""
        name = image.strip().split("@", 1)[0]
        if "/" not in name:
            return "docker.io"
        first = name.split("/", 1)[0]
        if "." in first or ":" in first or first == "localhost":
            return first.split(":", 1)[0].lower()
        return "docker.io"

    @staticmethod
    def ghcr_pat_create_url(*, description: str = "raft-ghcr-pull") -> str:
        """Deep-link to GitHub classic PAT creation with only ``read:packages``."""
        return (
            "https://github.com/settings/tokens/new"
            f"?scopes=read:packages&description={quote(description, safe='')}"
        )

    @classmethod
    def docker_config_has_registry_auth(
        cls,
        registry: str,
        *,
        config_path: Optional[Path] = None,
    ) -> Optional[bool]:
        """True/False if ``auths``/``credHelpers`` lists ``registry``; None if unknown."""
        path = config_path if config_path is not None else cls._docker_config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        host = registry.strip().lower()
        return cls._auth_dict_has_host(data.get("auths"), host) or cls._auth_dict_has_host(
            data.get("credHelpers"), host
        )

    @staticmethod
    def _docker_config_path() -> Path:
        override = os.environ.get("DOCKER_CONFIG", "").strip()
        if override:
            return Path(override).expanduser() / "config.json"
        return Path.home() / ".docker" / "config.json"

    @staticmethod
    def _auth_dict_has_host(mapping: object, host: str) -> bool:
        if not isinstance(mapping, dict):
            return False
        for key in mapping:
            if not isinstance(key, str):
                continue
            normalized = key.strip().lower().removeprefix("https://").removeprefix("http://")
            if normalized.split("/", 1)[0] == host:
                return True
        return False

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
        config_path: Optional[Path] = None,
    ) -> str:
        """Single call-to-action for a failed ``docker pull`` (private GHCR, etc.)."""
        return CtaFormatter.format(
            f"cannot pull {image}: registry unauthorized / denied.",
            cls.registry_login_fix_steps(image, app=app, repo=repo),
            detail=detail,
            tag="docker",
            fix_label="Fix (as the raft user):",
            preamble=cls._unauthorized_preamble(image, config_path=config_path),
        )

    @classmethod
    def _unauthorized_preamble(
        cls, image: str, *, config_path: Optional[Path]
    ) -> Tuple[str, ...]:
        host = cls.registry_host(image)
        lines = [
            "This is Docker registry auth/access — not `raft auth` (git deploy keys).",
            "",
            "Possible causes:",
            "  - never logged in to the registry on this host",
            "  - stored credentials expired, revoked, or invalid",
            "  - token/PAT missing pull scope (GHCR: read:packages)",
            "  - no access to that package / org SSO not authorized for the token",
            "",
            "How to check (as the raft user; no secrets printed):",
            f"  - {cls._config_check_line(host, config_path=config_path)}",
            f"  - retry `docker pull {image}` and note denied/unauthorized",
        ]
        if cls.is_ghcr_image(image):
            lines.append(
                "  - if the package org uses SAML SSO: authorize the token on GitHub"
            )
        return tuple(lines)

    @classmethod
    def _config_check_line(cls, host: str, *, config_path: Optional[Path]) -> str:
        present = cls.docker_config_has_registry_auth(host, config_path=config_path)
        cfg = "~/.docker/config.json"
        if present is True:
            return (
                f"{cfg} has an entry for {host} — credentials may be stale; "
                "re-login with a fresh token"
            )
        if present is False:
            return f"{cfg} has no entry for {host} — registry login is missing on this host"
        return f"confirm {cfg} has an entry for {host} (as the raft user)"

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
