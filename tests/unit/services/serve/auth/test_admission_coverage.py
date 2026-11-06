"""Coverage edges for sessions, admission middleware, and session routes."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.core.core.db.models.dashboard_session import _utc_now
from raft.core.core.rbac import RbacEnforcer, RbacHttpGate
from raft.core.lifecycle.dashboard.rbac_allowlist_sync import RbacAllowlistSync
from raft.core.observe.ops.actions import ServiceActions
from raft.services.serve.auth.middleware import DashboardAuthMiddleware
from raft.services.serve.auth.rbac_middleware import DashboardRbacMiddleware
from raft.services.serve.auth.session_routes import DashboardSessionRoutes
from tests.unit.base import RaftTestCase, StackMakers

_RBAC = (
    "version: 1\n"
    "roles:\n"
    "  - id: admin\n"
    "    permissions: ['*:read', '*:write']\n"
    "bindings:\n"
    "  - subject: ops@example.com\n"
    "    role: admin\n"
)


def _http_request(headers: list | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/dashboard/session",
            "raw_path": b"/api/dashboard/session",
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 80),
        }
    )


class TestAdmissionCoverage(RaftTestCase):
    def test_session_csrf_missing_row_and_utc_now(self) -> None:
        assert _utc_now().tzinfo is not None
        store = DashboardSessionStore(Path(self.tmp_path))
        assert not store.csrf_ok("missing-id", "token")
        store.revoke("missing-id")
        store.create("ops@example.com", auth_mode="password")
        now = datetime.now(timezone.utc)
        assert not DashboardSessionStore._expired(datetime(2099, 1, 1), now)
        assert DashboardSessionStore._expired(
            datetime(2000, 1, 1, tzinfo=timezone.utc), now
        )

    def test_enforcer_document_none_and_admitted_bootstrap(self) -> None:
        empty = RbacEnforcer(Path(self.tmp_path))
        assert empty.document() is None
        home = self._write_rbac()
        enforcer = RbacEnforcer(home)
        with patch.object(enforcer._store, "load", return_value=None):
            assert enforcer.document() is None
            assert enforcer.admitted("anyone") is True

    def test_http_gate_unknown_and_login_skip(self) -> None:
        gate = RbacHttpGate()
        assert gate.permission("GET", "/api/unknown-thing") is None
        assert gate.permission("GET", "/") is None
        assert gate.permission("GET", "/login") is None

    def test_allowlist_sync_bootstrap_missing_rbac(self) -> None:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "dashboard:\n  auth:\n    mode: oauth\n", encoding="utf-8"
        )
        out = RbacAllowlistSync(home).sync()
        assert out["synced"] is False
        assert "bootstrap" in out["reason"]

    def test_dashboard_up_syncs_allowlist(self) -> None:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "dashboard:\n  enabled: true\n  auth:\n    mode: oauth\n",
            encoding="utf-8",
        )
        self._assert_up_syncs(StackMakers.make_stack(home))

    def _assert_up_syncs(self, stack) -> None:
        actions = ServiceActions(stack)
        with patch.object(actions, "_docker_stack") as docker:
            docker.return_value.start_service.return_value = None
            with patch.object(actions, "_record_up_event"):
                with patch.object(actions, "_locks") as locks:
                    locks.return_value.__enter__ = MagicMock()
                    locks.return_value.__exit__ = MagicMock(return_value=False)
                    with patch(
                        "raft.core.observe.ops.actions.service.RbacAllowlistSync"
                    ) as sync_cls:
                        actions._up_one(
                            stack.dashboard, None, no_deps=True, started_deps=()
                        )
                        sync_cls.return_value.sync.assert_called_once()

    def test_password_csrf_reject(self) -> None:
        store = DashboardSessionStore(Path(self.tmp_path))
        minted = store.create("admin", auth_mode="password")
        client = self._password_app(store)
        client.cookies.set("raft_dash_session", minted.id)
        assert client.post("/api/purge").status_code == 403

    def _password_app(self, store: DashboardSessionStore) -> TestClient:
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        app = FastAPI()
        app.add_middleware(
            DashboardAuthMiddleware,
            config=cfg,
            home=Path(self.tmp_path),
            store=store,
        )

        @app.post("/api/purge")
        def purge():
            return {"ok": True}

        return TestClient(app)

    def test_rbac_middleware_401_and_403(self) -> None:
        home = self._write_rbac()
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="external"))
        client = TestClient(self._rbac_app(home, cfg))
        assert client.get("/page").status_code == 200
        assert client.get("/api/firewall").status_code == 401
        denied = TestClient(self._rbac_with_subject(home, cfg, "other@example.com"))
        assert denied.get("/api/firewall").status_code == 403

    def _rbac_app(self, home: Path, cfg: DashboardConfig) -> FastAPI:
        app = FastAPI()

        @app.get("/api/firewall")
        def firewall():
            return {"ok": True}

        @app.get("/page")
        def page():
            return {"ok": True}

        app.add_middleware(DashboardRbacMiddleware, home=home, config=cfg)
        return app

    def _rbac_with_subject(self, home, cfg, subject: str) -> FastAPI:
        app = FastAPI()

        @app.get("/api/firewall")
        def firewall(request: Request):
            return {"ok": True, "who": request.state.rbac_subject}

        class _Inject:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    Request(scope, receive=receive).state.rbac_subject = subject
                await self.app(scope, receive, send)

        app.add_middleware(DashboardRbacMiddleware, home=home, config=cfg)
        app.add_middleware(_Inject)
        return app

    def test_session_routes_mint_and_logout(self) -> None:
        home = Path(self.tmp_path)
        store = DashboardSessionStore(home)
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="external", identity_header="X-Raft-Identity")
        )
        app = FastAPI()
        DashboardSessionRoutes(cfg, home=home, store=store).register(app)
        client = TestClient(app)
        mint = client.get(
            "/api/dashboard/session",
            headers={"X-Raft-Identity": "ops@example.com"},
        )
        assert mint.json()["identity"] == "ops@example.com"
        again = client.get("/api/dashboard/session")
        assert again.json()["identity"] == "ops@example.com"
        assert client.post("/api/dashboard/logout").status_code == 200

    def test_session_routes_existing_state_subject(self) -> None:
        routes = self._routes(DashboardAuthConfig(mode="none"))
        request = _http_request()
        request.state.rbac_subject = "local"
        assert routes._resolve_subject(request) == ("local", None)
        assert routes._resolve_subject(_http_request()) == ("local", None)

    def test_session_routes_password_empty(self) -> None:
        home = self._write_rbac()
        store = DashboardSessionStore(home)
        routes = DashboardSessionRoutes(
            DashboardConfig(auth=DashboardAuthConfig(mode="password")),
            home=home,
            store=store,
        )
        assert routes._resolve_subject(_http_request()) == ("", None)

    def test_session_routes_external_without_header(self) -> None:
        home = self._write_rbac()
        routes = self._routes(
            DashboardAuthConfig(mode="external", identity_header="X-Raft-Identity"),
            home=home,
        )
        assert routes._resolve_subject(_http_request()) == ("", None)

    def test_authed_subject_not_admitted(self) -> None:
        home = self._write_rbac()
        store = DashboardSessionStore(home)
        minted = store.create("stranger@example.com", auth_mode="password")
        client = self._status_app(home, store)
        client.cookies.set("raft_dash_session", minted.id)
        assert client.get("/api/status").status_code == 403

    def _status_app(self, home: Path, store: DashboardSessionStore) -> TestClient:
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        app = FastAPI()
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, home=home, store=store
        )

        @app.get("/api/status")
        def status():
            return {"ok": True}

        return TestClient(app)

    def _routes(self, auth: DashboardAuthConfig, home: Path | None = None):
        root = home or Path(self.tmp_path)
        return DashboardSessionRoutes(
            DashboardConfig(auth=auth),
            home=root,
            store=DashboardSessionStore(root),
        )

    def _write_rbac(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "rbac.yaml").write_text(_RBAC, encoding="utf-8")
        return home
