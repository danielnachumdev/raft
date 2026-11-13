"""ASGI middleware: CSP, anti-framing, nosniff, referrer; HSTS when HTTPS."""

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from raft.core.lifecycle.dashboard.browser_security import BrowserSecurityHeaders


class SecurityHeadersMiddleware:
    """Attach browser security headers to every HTTP response.

    HSTS is set only when the request is HTTPS (direct scheme or the first
    ``X-Forwarded-Proto`` hop is ``https``), so localhost HTTP ``raft serve``
    is not HSTS-pinned.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._headers = BrowserSecurityHeaders()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        extras = self._headers.as_dict(https=self._is_https(request))

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                message = self._merge_start(message, extras)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    @staticmethod
    def _is_https(request: Request) -> bool:
        if request.url.scheme == "https":
            return True
        raw = request.headers.get("x-forwarded-proto", "")
        first = raw.split(",", 1)[0].strip().lower()
        return first == "https"

    @staticmethod
    def _merge_start(message: dict, extras: dict[str, str]) -> dict:
        existing = list(message.get("headers") or [])
        present = {name.lower() for name, _ in existing}
        for name, value in extras.items():
            key = name.lower().encode("latin-1")
            if key in present:
                continue
            existing.append((key, value.encode("latin-1")))
        return {**message, "headers": existing}
