"""Raw GitHub HTTP transport (urllib). No product rules."""

from dataclasses import dataclass
from typing import Callable, Mapping, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_UA = "raft-serve-github-v1"
_API_VERSION = "2022-11-28"


@dataclass(frozen=True)
class GithubHttpResponse:
    body: str
    headers: Mapping[str, str]
    status: int


class GithubHttpError(Exception):
    """Transport-level HTTP failure from GitHub."""

    def __init__(self, code: int, body: str) -> None:
        self.code = code
        self.body = body
        super().__init__(f"HTTP {code}")


class GithubApiGateway:
    """Short protocol verbs against GitHub HTTP endpoints."""

    def __init__(
        self,
        *,
        opener: Optional[Callable[..., object]] = None,
        timeout: float = 30.0,
    ) -> None:
        self._opener = opener
        self._timeout = timeout

    def get(
        self, url: str, *, headers: Optional[Mapping[str, str]] = None
    ) -> GithubHttpResponse:
        return self._call("GET", url, headers=headers)

    def post(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> GithubHttpResponse:
        return self._call("POST", url, headers=headers, body=body)

    def put(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> GithubHttpResponse:
        return self._call("PUT", url, headers=headers, body=body)

    @staticmethod
    def bearer_headers(
        token: str, *, accept: str = "application/vnd.github+json"
    ) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "User-Agent": _UA,
            "X-GitHub-Api-Version": _API_VERSION,
        }

    @staticmethod
    def json_headers(*, extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": _UA,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if extra:
            headers.update(extra)
        return headers

    def _call(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> GithubHttpResponse:
        req = Request(
            url,
            data=body,
            method=method,
            headers=dict(headers or {}),
        )
        opener = self._opener or urlopen
        try:
            with opener(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
                hdrs = getattr(resp, "headers", None)
                return GithubHttpResponse(
                    body=raw,
                    headers=dict(hdrs.items()) if hdrs is not None else {},
                    status=self._status(resp),
                )
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:240]
            raise GithubHttpError(exc.code, detail) from exc

    @staticmethod
    def _status(resp: object) -> int:
        code = getattr(resp, "status", None)
        if isinstance(code, int):
            return code
        return int(resp.getcode())
