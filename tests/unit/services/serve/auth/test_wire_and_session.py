"""Serve auth wire, login routes, and password session coverage."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.services.serve.auth.wire import ServeAuthWire
from tests.unit.base import RaftTestCase, StackMakers


class TestServeAuthWireAndSession(RaftTestCase):
    def test_login_logout_and_csrf(self) -> None:
        client = self._password_client()
        assert client.get("/api/status").status_code == 401
        bad = client.post("/api/dashboard/login", json={"password": "nope"})
        assert bad.status_code == 401
        ok = client.post(
            "/api/dashboard/login", json={"password": "correct-horse"}
        )
        assert ok.status_code == 200
        self._assert_authed_mutative(client)

    def test_wire_skips_none_and_password_without_hash(self) -> None:
        home = self.tmp_path
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
        stack = StackMakers.make_stack(home)
        ServeAuthWire(stack, config=DashboardConfig()).apply(FastAPI())
        ServeAuthWire(
            stack,
            config=DashboardConfig(auth=DashboardAuthConfig(mode="password")),
        ).apply(FastAPI())

    def test_session_corrupt_cookie(self) -> None:
        from raft.services.serve.auth.password_session import PasswordSessionAuth

        hashed = DashboardPassword().hash("correct-horse")
        sessions = PasswordSessionAuth(self.tmp_path, password_hash=hashed)
        assert not sessions.session_ok("bad")
        assert not sessions.session_ok("a.b")
        assert not sessions.csrf_ok(None, "x")
        tokens = sessions.login("correct-horse")
        assert tokens is not None
        assert sessions.csrf_ok(tokens[0], tokens[1])
        assert not sessions.csrf_ok(tokens[0], "wrong")

    def _password_client(self) -> TestClient:
        home = self.tmp_path
        (home / "settings.yaml").write_text("{}\n", encoding="utf-8")
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
        return TestClient(app)

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
