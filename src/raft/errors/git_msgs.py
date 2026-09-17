"""Git failure classifiers and message builders."""

from __future__ import annotations

from typing import Optional

from .cta import OperatorError, exc_blob, first_line, format_cta


def looks_like_git_auth_failure(exc: BaseException) -> bool:
    text = exc_blob(exc)
    needles = (
        "permission denied (publickey)",
        "could not read from remote repository",
        "host key verification failed",
        "authentication failed",
        "publickey",
        "repository not found",
        "invalid privatekey",
        "error in libcrypto",
    )
    return any(n in text for n in needles)


def looks_like_git_network_failure(exc: BaseException) -> bool:
    text = exc_blob(exc)
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
    return format_cta(
        f"git auth failed for {repo!r}.",
        (
            f"raft auth setup {svc} --repo {repo}",
            "paste Title + Key as a read-only Deploy key on the git host",
            f"raft auth test {svc} --repo {repo}",
            "re-run your raft apply / sync / redeploy command",
        ),
        detail=detail,
        tag="git",
        fix_label="Fix (as the raft user):",
        preamble=(
            "A read-only deploy key is required (raft auth is separate from GHCR docker login).",
        ),
    )


def git_network_failure_message(repo: str, *, detail: str = "") -> str:
    return format_cta(
        f"cannot reach git host for {repo!r}.",
        (
            "check DNS / outbound HTTPS+SSH from this VPS",
            "retry: raft auth test <app> --repo <url>",
        ),
        detail=detail,
        tag="git",
        fix_label="Fix:",
    )


def git_generic_failure_message(
    repo: str,
    *,
    app: Optional[str] = None,
    detail: str = "",
) -> str:
    svc = app or "<app-name>"
    return format_cta(
        f"git command failed for {repo!r}.",
        (
            f"raft auth test {svc} --repo {repo}",
            "check the ref exists on the remote",
            "raft doctor",
        ),
        detail=detail,
        tag="git",
    )
