"""Serve auth wire, login routes, and SQLite session coverage."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.services.serve.auth.password_session import PasswordSessionAuth
from raft.services.serve.auth.wire import ServeAuthWire
from tests.unit.base import RaftTestCase, StackMakers


class TestServeAuthWireAndSession(RaftTestCase):
    def test_login_logout_and_csrf(self) -> None:
        client = self._password_client()
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/dashboard/auth").status_code == 401
        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert "Sign in" in login_page.text
        bad = client.post("/api/dashboard/login", json={"password": "nope"})
        assert bad.status_code == 401
        ok = client.post(
            "/api/dashboard/login", json={"password": "correct-horse"}
        )
        assert ok.status_code == 200
        self._assert_authed_mutative(client)

    def test_password_rejects_unbound_when_rbac_present(self) -> None:
        client = self._password_client(write_rbac=True)
        denied = client.post(
            "/api/dashboard/login", json={"password": "correct-horse"}
        )
        assert denied.status_code == 403
        assert "not admitted" in denied.json()["detail"]

    def test_wire_skips_none_and_password_without_hash(self) -> None:
        home = self.tmp_path
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        stack = StackMakers.make_stack(home)
        ServeAuthWire(stack, config=DashboardConfig()).apply(FastAPI())
        ServeAuthWire(
            stack,
            config=DashboardConfig(auth=DashboardAuthConfig(mode="password")),
        ).apply(FastAPI())

    def test_password_verify_only(self) -> None:
        hashed = DashboardPassword().hash("correct-horse")
        sessions = PasswordSessionAuth.from_hashes(self.tmp_path, password_hash=hashed)
        assert sessions.verify("nope") is None
        assert sessions.verify("correct-horse") == "admin"
        assert sessions.verify("correct-horse", username="missing") is None

    def _password_client(self, *, write_rbac: bool = False) -> TestClient:
        home = self.tmp_path
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        if write_rbac:
            self._write_admin_rbac(home)
        return TestClient(self._password_app(home))

    @staticmethod
    def _write_admin_rbac(home) -> None:
        (home / "host" / "rbac.yaml").write_text(
            "version: 1\n"
            "roles:\n"
            "  - id: admin\n"
            "    permissions: ['*:read', '*:write']\n"
            "bindings:\n"
            "  - subject: ops@example.com\n"
            "    role: admin\n",
            encoding="utf-8",
        )

    def _password_app(self, home) -> FastAPI:
        hashed = DashboardPassword().hash("correct-horse")
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="password", password_hash=hashed)
        )
        app = FastAPI()

        @app.get("/api/status")
        def status():
            return {"ok": True}

        @app.post("/api/purge")
        def purge():
            return {"ok": True}

        ServeAuthWire(StackMakers.make_stack(home), config=cfg).apply(app)
        return app

    @staticmethod
    def _assert_authed_mutative(client: TestClient) -> None:
        assert client.get("/api/status").status_code == 200
        auth = client.get("/api/dashboard/auth")
        assert auth.json()["authenticated"] is True
        csrf = client.cookies.get("raft_dash_csrf")
        assert client.post("/api/purge").status_code == 403
        assert client.post(
            "/api/purge", headers={"X-CSRF-Token": csrf}
        ).status_code == 200
        client.post("/api/dashboard/logout")
        assert client.get("/api/status").status_code == 401
