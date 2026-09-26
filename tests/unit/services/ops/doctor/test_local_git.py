"""Doctor checks for local/git apps and stack infra."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.services.ops.doctor import INFRA

from ....base import make_app, make_git_app, make_stack, write_applied_app
from .base import DoctorTestCase


class TestDoctorLocalGit(DoctorTestCase):
    def test_local_app_path_and_upstream(self) -> None:
        self.seed_compose()
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        up = self.tmp_path / "generated" / "nginx" / "upstreams"
        up.mkdir(parents=True)
        (up / "app-http.conf").write_text(
            "upstream app_http { server app:80; }\n", encoding="utf-8"
        )
        self.write_certs("app")
        docker = self.mock_docker(
            running=["raft-gate", "raft-router", "raft-controller", "app"]
        )
        results = self.run_keyed(
            shell=self.mock_shell(), auth=MagicMock(), docker=docker, connect=True
        )
        self._assert_local_ok(results)

    def _assert_local_ok(self, results) -> None:
        assert results[(INFRA, "compose.yaml")].status == "ok"
        assert results[(INFRA, "docker")].status == "ok"
        assert results[("app", "sync")].status == "ok"
        assert results[("app", "upstream")].status == "ok"
        assert results[("app", "certs")].status == "ok"
        assert results[(INFRA, "stack")].status == "ok"
        assert results[(INFRA, "port 80")].status == "ok"

    def test_git_app_missing_auth_and_checkout(self) -> None:
        self.seed_compose()
        write_applied_app(
            self.tmp_path, "svc", source="git",
            repo="git@github.com:org/svc.git", public_host="svc.test",
        )
        auth = MagicMock()
        auth.is_configured.return_value = False
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_git_app("svc"),)),
            shell=self.mock_shell(), auth=auth, docker=self.mock_docker(),
        )
        self._assert_git_missing(results)

    def _assert_git_missing(self, results) -> None:
        assert results[("svc", "auth")].status == "fail"
        assert "auth setup svc" in results[("svc", "auth")].fix
        assert results[("svc", "sync")].status == "fail"
        assert "sync svc" in results[("svc", "sync")].fix
        assert results[("svc", "certs")].status == "ok"
        assert "tls: off" in results[("svc", "certs")].detail
        assert results[(INFRA, "stack")].status == "warn"
        assert results[(INFRA, "port 80")].status == "ok"

    def test_docker_missing_and_daemon_fail(self) -> None:
        self.seed_compose()
        shell = MagicMock()
        with patch("raft.services.ops.doctor.shutil.which", return_value=None):
            with patch(
                "raft.services.ops.doctor.socket.create_connection", side_effect=OSError()
            ):
                results = self.by_key(self.doctor(shell=shell).run())
        assert results[(INFRA, "docker")].status == "fail"
        shell.run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Cannot connect\n"
        )
        results = self.run_keyed(shell=shell)
        assert results[(INFRA, "docker")].status == "fail"
        assert "Cannot connect" in results[(INFRA, "docker")].detail

    def test_git_auth_test_failure_and_non_git_dir(self) -> None:
        self.seed_compose()
        dest = self.tmp_path / "apps" / "svc"
        dest.mkdir(parents=True)
        (dest / "README").write_text("x", encoding="utf-8")
        write_applied_app(
            self.tmp_path, "svc", source="git",
            repo="git@github.com:org/svc.git", public_host="svc.test",
        )
        auth = MagicMock()
        auth.is_configured.return_value = True
        auth.test.side_effect = RuntimeError("auth test failed")
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_git_app("svc"),)),
            shell=self.mock_shell(), auth=auth, docker=self.mock_docker(),
        )
        assert results[("svc", "auth")].status == "fail"
        assert results[("svc", "sync")].status == "fail"
        assert "not a git checkout" in results[("svc", "sync")].detail
        assert "github.com/org/svc/settings/keys/new" in results[("svc", "auth")].fix

    def test_missing_compose_and_port_conflict(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("app"),))
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        for path in (
            self.tmp_path / "compose.yaml",
            self.tmp_path / "generated" / "compose.apps.yaml",
        ):
            if path.is_file():
                path.unlink()
        results = self.run_keyed(
            stack, shell=self.mock_shell(), docker=self.mock_docker(),
            auth=MagicMock(), connect=True,
        )
        assert results[(INFRA, "compose.yaml")].status == "fail"
        assert results[(INFRA, "generated")].status == "fail"
        assert results[(INFRA, "port 80")].status == "warn"

    def test_git_ok_partial_stack_and_gate_owns_port(self) -> None:
        self.seed_compose()
        dest = self.tmp_path / "apps" / "svc"
        dest.mkdir(parents=True)
        (dest / ".git").mkdir()
        self.write_certs("svc")
        write_applied_app(
            self.tmp_path, "svc", source="git",
            repo="git@github.com:org/svc.git", public_host="svc.test",
        )
        auth = MagicMock()
        auth.is_configured.return_value = True
        auth.test.return_value = None
        results = self.run_keyed(
            make_stack(self.tmp_path, (make_git_app("svc"),)),
            shell=self.mock_shell(), auth=auth,
            docker=self.mock_docker(running=["raft-gate"]), connect=True,
        )
        self._assert_git_partial(results)

    def _assert_git_partial(self, results) -> None:
        assert results[("svc", "auth")].status == "ok"
        assert results[("svc", "sync")].status == "ok"
        assert results[("svc", "upstream")].status == "warn"
        assert results[("svc", "certs")].status == "ok"
        assert results[(INFRA, "stack")].status == "warn"
        assert "missing" in results[(INFRA, "stack")].detail
        assert results[(INFRA, "port 80")].status == "ok"

    def test_stack_query_error_and_port_query_error(self) -> None:
        self.seed_compose()
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        docker = MagicMock()
        docker.running_services.side_effect = RuntimeError("compose broke")
        results = self.run_keyed(
            shell=self.mock_shell(), docker=docker, auth=MagicMock(), connect=True
        )
        assert results[(INFRA, "stack")].status == "warn"
        assert "compose broke" in results[(INFRA, "stack")].detail
        assert results[(INFRA, "port 80")].status == "warn"

    def test_local_path_missing(self) -> None:
        self.seed_compose()
        results = self.run_keyed(
            shell=self.mock_shell(), docker=self.mock_docker(), auth=MagicMock()
        )
        assert results[("app", "sync")].status == "fail"
        assert results[("app", "certs")].status == "ok"
