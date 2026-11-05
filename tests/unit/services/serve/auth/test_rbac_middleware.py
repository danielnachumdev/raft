"""DashboardRbacMiddleware + ServeRbac deps (#307)."""

import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.services.serve.auth.rbac_deps import ServeRbac
from raft.services.serve.auth.rbac_middleware import DashboardRbacMiddleware
from tests.unit.base import RaftTestCase

_RBAC = (
    "version: 1\n"
    "roles:\n"
    "  - id: admin\n"
    "    permissions: ['*:read', '*:write']\n"
    "bindings:\n"
    "  - subject: ops@example.com\n"
    "    role: admin\n"
)
_EXT = DashboardConfig(auth=DashboardAuthConfig(mode="external"))


class TestDashboardRbacMiddleware(RaftTestCase):
    def test_bootstrap_allows(self) -> None:
        assert self._client(write_rbac=False).get("/api/status").status_code == 200

    def test_deny_and_allow_with_header(self) -> None:
        client = self._client(write_rbac=True, cfg=_EXT)
        assert client.get("/api/firewall").status_code == 401
        ok = client.get(
            "/api/firewall", headers={"X-Raft-Identity": "ops@example.com"}
        )
        assert ok.status_code == 200
        denied = client.get(
            "/api/firewall", headers={"X-Raft-Identity": "other@example.com"}
        )
        assert denied.status_code == 403

    def test_non_http_scope_passes(self) -> None:
        seen = {"ok": False}

        async def app(scope, receive, send):
            seen["ok"] = True

        mw = DashboardRbacMiddleware(
            app, home=Path(self.tmp_path), config=DashboardConfig()
        )
        asyncio.run(mw({"type": "websocket"}, None, None))
        assert seen["ok"] is True

    def test_cookie_username_on_middleware(self) -> None:
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        client = self._client(
            write_rbac=True,
            cfg=cfg,
            username_from_cookie=lambda c: "ops@example.com" if c else None,
        )
        assert client.get("/api/firewall").status_code == 403
        ok = client.get("/api/firewall", cookies={"raft_dash_session": "tok"})
        assert ok.status_code == 200

    def test_serve_rbac_session_and_require(self) -> None:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        rbac = ServeRbac(home, _EXT)
        app = FastAPI()

        @app.get("/who")
        def who(request: Request, _=Depends(rbac.require("firewall:read"))):
            return rbac.session_fields(request)

        client = TestClient(app)
        assert client.get("/who").status_code == 403
        ok = client.get("/who", headers={"X-Raft-Identity": "ops@example.com"})
        assert ok.status_code == 200
        assert ok.json()["bootstrap"] is False

    def test_serve_rbac_bootstrap_and_cookie(self) -> None:
        rbac = ServeRbac(
            Path(self.tmp_path),
            DashboardConfig(auth=DashboardAuthConfig(mode="password")),
            username_from_cookie=lambda c: "ops" if c else None,
        )
        fields = rbac.session_fields(self._request([]))
        assert fields["bootstrap"] is True
        assert fields["permissions"] == ["*:read", "*:write"]
        cookied = self._request([(b"cookie", b"raft_dash_session=tok")])
        assert rbac.subject(cookied) == "ops"

    @staticmethod
    def _request(headers: list) -> Request:
        return Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "query_string": b"",
                "headers": headers,
                "client": ("127.0.0.1", 1),
                "server": ("127.0.0.1", 80),
            }
        )

    def _client(self, *, write_rbac: bool, cfg=None, username_from_cookie=None):
        return TestClient(
            self._app(
                write_rbac=write_rbac,
                cfg=cfg,
                username_from_cookie=username_from_cookie,
            )
        )

    def _app(self, *, write_rbac: bool, cfg=None, username_from_cookie=None):
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        if write_rbac:
            (host / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        app = self._routes()
        app.add_middleware(
            DashboardRbacMiddleware,
            home=home,
            config=cfg or DashboardConfig(),
            username_from_cookie=username_from_cookie,
        )
        return app

    @staticmethod
    def _routes() -> FastAPI:
        app = FastAPI()

        @app.get("/api/status")
        def status():
            return {"ok": True}

        @app.get("/api/firewall")
        def firewall():
            return {"ok": True}

        return app
