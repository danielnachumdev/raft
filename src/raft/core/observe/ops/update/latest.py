"""Fetch the latest GitHub Release for the raft install SoT."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.github.gateway import GithubApiGateway, GithubHttpError

_DEFAULT_REPO = "danielnachumdev/raft"
_SLUG_RE = re.compile(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", re.I)


@dataclass(frozen=True)
class LatestRelease:
    tag: str
    html_url: str
    name: str


class LatestReleaseFetcher:
    """``GET /repos/{owner}/{repo}/releases/latest`` (same SoT as install.sh)."""

    def __init__(
        self,
        *,
        gateway: Optional[GithubApiGateway] = None,
        repo: Optional[str] = None,
        opener: Optional[Callable[..., object]] = None,
    ) -> None:
        self._gateway = gateway or GithubApiGateway(opener=opener, timeout=15.0)
        self._repo = (repo or self._repo_from_env()).strip() or _DEFAULT_REPO

    def fetch(self) -> LatestRelease:
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        try:
            resp = self._gateway.get(url, headers=self._headers())
        except GithubHttpError as exc:
            raise self._fail(url, f"HTTP {exc.code}") from exc
        except Exception as exc:
            raise self._fail(url, str(exc) or exc.__class__.__name__) from exc
        return self._parse(resp.body, url)

    def _parse(self, body: str, url: str) -> LatestRelease:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise self._fail(url, "invalid JSON") from exc
        if not isinstance(data, dict):
            raise self._fail(url, "unexpected JSON shape")
        tag = str(data.get("tag_name") or "").strip()
        if not tag:
            raise self._fail(url, "missing tag_name")
        html = str(data.get("html_url") or "").strip()
        name = str(data.get("name") or tag).strip()
        return LatestRelease(tag=tag, html_url=html, name=name)

    @staticmethod
    def _headers() -> dict:
        return {
            "Accept": "application/vnd.github+json",
            "User-Agent": "raft-update-check-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _repo_from_env() -> str:
        raw = (os.environ.get("RAFT_REPO_URL") or "").strip()
        if not raw:
            return _DEFAULT_REPO
        match = _SLUG_RE.search(raw.rstrip("/"))
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        path = urlparse(raw).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1].removesuffix('.git')}"
        return _DEFAULT_REPO

    @staticmethod
    def _fail(url: str, detail: str) -> OperatorError:
        return OperatorError(
            "Could not resolve the latest raft GitHub Release.\n"
            f"Detail: {detail}\n"
            f"Fix: check outbound HTTPS to {url}, then retry "
            "`raft update` or Settings → Check for updates"
        )
