"""DashboardRbacMiddleware + ServeRbac + RequirePermission (#admission SoT)."""

import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from raft.services.serve.auth.rbac_deps import ServeRbac
from raft.services.serve.auth.rbac_middleware import DashboardRbacMiddleware
from raft.services.serve.auth.require import require_read, require_write
from tests.unit.base import RaftTestCase

_RBAC = (
    "version: 1\n"
    "roles:\n"
    "  - id: admin\n"
    "    permissions: ['*:read', '*:write']\n"
    "  - id: viewer\n"
    "    permissions: ['firewall:read']\n"
    "bindings:\n"
    "  - subject: ops@example.com\n"
    "    role: admin\n"
    "  - subject: viewer@example.com\n"
    "    role: viewer\n"
)
_EXT = DashboardConfig(auth=DashboardAuthConfig(mode="external"))


class TestDashboardRbacMiddleware(RaftTestCase):
    def test_bootstrap_allows(self) -> None:
        assert self._client(write_rbac=False).get("/api/status").status_code == 200

    def test_admission_deny_and_allow_with_header(self) -> None:
        client = self._authed_client(write_rbac=True, cfg=_EXT)
        assert client.get("/api/firewall").status_code == 401
        ok = client.get(
            "/api/firewall", headers={"X-Raft-Identity": "ops@example.com"}
        )
        assert ok.status_code == 200
        stranger = TestClient(self._authed_app(write_rbac=True, cfg=_EXT))
        denied = stranger.get(
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

    def test_serve_rbac_require_uses_state_subject(self) -> None:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        rbac = ServeRbac(home, _EXT)
        app = FastAPI()

        @app.middleware("http")
        async def inject(request: Request, call_next):
            request.state.rbac_subject = request.headers.get("X-Subject", "")
            return await call_next(request)

        @app.get("/who")
        def who(request: Request, _=Depends(rbac.require("firewall:read"))):
            return rbac.session_fields(request)

        client = TestClient(app)
        assert client.get("/who").status_code == 403
        ok = client.get("/who", headers={"X-Subject": "ops@example.com"})
        assert ok.status_code == 200
        assert ok.json()["identity"] == "ops@example.com"

    def test_require_permission_depends_allow_deny(self) -> None:
        client = TestClient(self._depends_app())
        viewer = {"X-Subject": "viewer@example.com"}
        assert client.get("/api/firewall", headers=viewer).status_code == 200
        assert client.put("/api/firewall", headers=viewer).status_code == 403
        assert (
            client.put(
                "/api/firewall", headers={"X-Subject": "ops@example.com"}
            ).status_code
            == 200
        )

    def _depends_app(self) -> FastAPI:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        app = FastAPI()
        app.state.raft_home = home

        @app.get("/api/firewall", dependencies=[Depends(require_read("firewall"))])
        def firewall():
            return {"ok": True}

        @app.put("/api/firewall", dependencies=[Depends(require_write("firewall"))])
        def put_firewall():
            return {"ok": True}

        @app.middleware("http")
        async def inject_subject(request: Request, call_next):
            request.state.rbac_subject = request.headers.get("X-Subject", "")
            return await call_next(request)

        return app

    def test_serve_rbac_bootstrap(self) -> None:
        rbac = ServeRbac(
            Path(self.tmp_path),
            DashboardConfig(auth=DashboardAuthConfig(mode="password")),
        )
        fields = rbac.session_fields_for("admin")
        assert fields["bootstrap"] is True
        assert fields["permissions"] == ["*:read", "*:write"]

    def test_require_invalid_permission_and_missing_home(self) -> None:
        import pytest
        from raft.services.serve.auth.require import RequirePermission

        with pytest.raises(ValueError, match="invalid permission"):
            RequirePermission("not-a-perm")
        app = FastAPI()

        @app.get("/x", dependencies=[Depends(require_read("status"))])
        def x():
            return {"ok": True}

        @app.middleware("http")
        async def inject(request: Request, call_next):
            request.state.rbac_subject = "local"
            return await call_next(request)

        assert TestClient(app).get("/x").status_code == 500

    def test_rbac_middleware_sets_local_in_none_mode(self) -> None:
        app = self._rbac_only_app(write_rbac=False, cfg=DashboardConfig())
        client = TestClient(app)
        assert client.get("/api/status").status_code == 200

    def _client(self, *, write_rbac: bool, cfg=None):
        return TestClient(self._rbac_only_app(write_rbac=write_rbac, cfg=cfg))

    def _authed_client(self, *, write_rbac: bool, cfg):
        return TestClient(self._authed_app(write_rbac=write_rbac, cfg=cfg))

    def _authed_app(self, *, write_rbac: bool, cfg):
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        if write_rbac:
            (host / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        store = DashboardSessionStore(home)
        app = self._routes()
        app.add_middleware(DashboardRbacMiddleware, home=home, config=cfg)
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, home=home, store=store
        )
        return app

    def _rbac_only_app(self, *, write_rbac: bool, cfg=None):
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
