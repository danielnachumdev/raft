"""Set / clear opaque dashboard session cookies."""

from fastapi import Request
from fastapi.responses import Response

from raft.core.core.db.dashboard_sessions import (
    COOKIE_NAME,
    CSRF_COOKIE_NAME,
    MintedSession,
)

_MAX_AGE = 12 * 3600


class DashboardSessionCookies:
    """HttpOnly session id + readable CSRF cookie."""

    @classmethod
    def attach(cls, request: Request, response: Response, minted: MintedSession) -> None:
        secure = cls._secure(request)
        cls._set(response, COOKIE_NAME, minted.id, httponly=True, secure=secure)
        cls._set(
            response, CSRF_COOKIE_NAME, minted.csrf_token, httponly=False, secure=secure
        )

    @classmethod
    def clear(cls, response: Response) -> None:
        response.delete_cookie(COOKIE_NAME)
        response.delete_cookie(CSRF_COOKIE_NAME)

    @staticmethod
    def _set(
        response: Response,
        name: str,
        value: str,
        *,
        httponly: bool,
        secure: bool,
    ) -> None:
        response.set_cookie(
            name,
            value,
            httponly=httponly,
            samesite="lax",
            secure=secure,
            max_age=_MAX_AGE,
        )

    @staticmethod
    def _secure(request: Request) -> bool:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        return proto.lower() == "https"
