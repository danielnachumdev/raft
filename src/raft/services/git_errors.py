"""Git clone/fetch/ls-remote failure classification for operator CTAs."""

from __future__ import annotations

import subprocess
from typing import Optional


def _exc_text(exc: BaseException) -> str:
    text = str(exc).lower()
    if isinstance(exc, subprocess.CalledProcessError):
        text = f"{text} {(exc.stderr or '')} {(exc.output or '')}".lower()
    return text


def looks_like_git_auth_failure(exc: BaseException) -> bool:
    text = _exc_text(exc)
    needles = (
        "permission denied (publickey)",
        "could not read from remote repository",
        "host key verification failed",
        "authentication failed",
        "publickey",
        "repository not found",  # GitHub often uses this for private-without-key
        "invalid privatekey",
        "error in libcrypto",
    )
    return any(n in text for n in needles)


def looks_like_git_network_failure(exc: BaseException) -> bool:
    text = _exc_text(exc)
    needles = (
        "could not resolve host",
        "name or service not known",
        "network is unreachable",
        "network unreachable",
        "connection timed out",
        "connection refused",
        "temporary failure in name resolution",
        "no route to host",
    )
    return any(n in text for n in needles)


def git_auth_failure_message(
    repo: str,
    *,
    app: Optional[str] = None,
    detail: str = "",
) -> str:
    svc = app or "<app-name>"
    lines = [
        f"git auth failed for {repo!r}.",
        "A read-only deploy key is required (raft auth is separate from GHCR docker login).",
        "",
        "fix (as the raft user):",
        f"  1. raft auth setup {svc} --repo {repo}",
        "  2. paste Title + Key as a read-only Deploy key on the git host",
        f"  3. raft auth test {svc} --repo {repo}",
        f"  4. re-run your raft apply / sync / redeploy command",
    ]
    if detail:
        first = detail.strip().splitlines()[0].strip() if detail.strip() else ""
        if first:
            lines.extend(["", f"(git: {first})"])
    return "\n".join(lines)


def git_network_failure_message(repo: str, *, detail: str = "") -> str:
    lines = [
        f"cannot reach git host for {repo!r}.",
        "",
        "fix:",
        "  1. check DNS / outbound HTTPS+SSH from this VPS",
        "  2. retry: raft auth test <app> --repo <url>",
    ]
    if detail:
        first = detail.strip().splitlines()[0].strip() if detail.strip() else ""
        if first:
            lines.extend(["", f"(git: {first})"])
    return "\n".join(lines)


def git_generic_failure_message(
    repo: str,
    *,
    app: Optional[str] = None,
    detail: str = "",
) -> str:
    svc = app or "<app-name>"
    lines = [
        f"git command failed for {repo!r}.",
        "",
        "Fix:",
        f"  1. raft auth test {svc} --repo {repo}",
        "  2. check the ref exists on the remote",
        "  3. raft doctor",
    ]
    if detail:
        first = detail.strip().splitlines()[0].strip() if detail.strip() else ""
        if first:
            lines.extend(["", f"(git: {first})"])
    return "\n".join(lines)


def raise_for_git_failure(
    exc: BaseException,
    repo: str,
    *,
    app: Optional[str] = None,
    always: bool = False,
) -> None:
    """Re-raise ``exc`` as a clear RuntimeError for known git classes.

    When ``always`` is True, unmatched failures still become a RuntimeError
    with a generic Fix CTA (never leave a bare CalledProcessError).
    """
    detail = ""
    if isinstance(exc, subprocess.CalledProcessError):
        detail = (exc.stderr or exc.output or "").strip()
    if looks_like_git_auth_failure(exc):
        raise RuntimeError(
            git_auth_failure_message(repo, app=app, detail=detail)
        ) from exc
    if looks_like_git_network_failure(exc):
        raise RuntimeError(
            git_network_failure_message(repo, detail=detail)
        ) from exc
    if always:
        raise RuntimeError(
            git_generic_failure_message(repo, app=app, detail=detail)
        ) from exc
