"""Doctor diagnostics (docker/auth/sync mocked)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from raft.services import CheckResult, Doctor
from raft.services.doctor import INFRA

from ..base import make_app, make_git_app, make_stack, write_applied_app
from .base import ServicesTestCase


class TestDoctor(ServicesTestCase):
    def _doctor(self, stack=None, **kwargs) -> Doctor:
        stack = stack or self.stack
        shell = kwargs.pop("shell", MagicMock())
        auth = kwargs.pop("auth", MagicMock())
        docker = kwargs.pop("docker", MagicMock())
        if isinstance(docker.gate_published_ports.return_value, MagicMock):
            docker.gate_published_ports.return_value = [80, 443]
        return Doctor(stack, shell=shell, auth=auth, docker=docker, **kwargs)

    def _write_certs(self, *names: str) -> None:
        for name in names:
            d = self.tmp_path / "certs" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "origin.pem").write_text("pem\n", encoding="utf-8")
            (d / "origin.key").write_text("key\n", encoding="utf-8")

    @staticmethod
    def _by_key(results) -> dict[tuple[str, str], CheckResult]:
        return {(r.service, r.check): r for r in results}

    def test_report_collapses_healthy_and_expands_issues(self, capsys) -> None:
        d = self._doctor()
        assert (
            d.report(
                [
                    CheckResult(INFRA, "docker", "ok", "fine"),
                    CheckResult("svc", "auth", "ok", "fine"),
                    CheckResult("svc", "sync", "ok", "fine"),
                ],
                color=False,
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "  OK    infra" in out
        assert "  OK    svc" in out
        assert "all checks passed" in out
        assert "\033[" not in out
        assert "  OK    auth" not in out
        assert "  OK    sync" not in out

        assert (
            d.report(
                [
                    CheckResult("svc", "auth", "ok", "fine"),
                    CheckResult("svc", "sync", "warn", "maybe", fix="do x"),
                ],
                color=False,
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "svc\n" in out
        assert "  WARN  sync  maybe" in out
        assert "fix: do x" in out
        assert "auth" not in out
        assert "warning" in out

        assert (
            d.report(
                [CheckResult(INFRA, "docker", "fail", "bad", fix="fix it")],
                color=False,
            )
            == 1
        )
        out = capsys.readouterr().out
        assert "infra\n" in out
        assert "  FAIL  docker  bad" in out
        assert "fix: fix it" in out
        assert "failed" in out

    def test_report_uses_ansi_when_color_enabled(self, capsys) -> None:
        d = self._doctor()
        assert (
            d.report(
                [
                    CheckResult("svc", "auth", "fail", "bad", fix="raft auth setup svc"),
                ],
                color=True,
            )
            == 1
        )
        out = capsys.readouterr().out
        assert "\033[31m" in out
        assert "\033[36m" in out
        assert "\033[0m" in out

        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], color=True) == 0
        out = capsys.readouterr().out
        assert "\033[32m" in out

        assert (
            d.report(
                [CheckResult(INFRA, "stack", "warn", "partial")],
                color=True,
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "\033[33m" in out

    def test_report_respects_no_color_and_isatty(self, monkeypatch) -> None:
        d = self._doctor()

        class Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        monkeypatch.delenv("NO_COLOR", raising=False)
        buf = Tty()
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=buf) == 0
        assert "\033[32m" in buf.getvalue()

        monkeypatch.setenv("NO_COLOR", "1")
        buf2 = Tty()
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=buf2) == 0
        assert "\033[" not in buf2.getvalue()

        monkeypatch.delenv("NO_COLOR", raising=False)

        class NoTty:
            def write(self, s: str) -> int:
                return len(s)

            def flush(self) -> None:
                return None

        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=NoTty()) == 0

    def test_local_app_path_and_upstream(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        up = self.tmp_path / "generated" / "nginx" / "upstreams"
        up.mkdir(parents=True)
        (up / "app-http.conf").write_text(
            "upstream app_http { server app:80; }\n", encoding="utf-8"
        )
        self._write_certs("app")

        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = ["gate", "router", "app"]
        auth = MagicMock()

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch("raft.services.doctor.socket.create_connection"):
                results = self._by_key(self._doctor(shell=shell, auth=auth, docker=docker).run())
        assert results[(INFRA, "compose.yaml")].status == "ok"
        assert results[(INFRA, "docker")].status == "ok"
        assert results[("app", "sync")].status == "ok"
        assert results[("app", "upstream")].status == "ok"
        assert results[("app", "certs")].status == "ok"
        assert results[(INFRA, "stack")].status == "ok"
        assert results[(INFRA, "port 80")].status == "ok"

    def test_git_app_missing_auth_and_checkout(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        write_applied_app(
            self.tmp_path,
            "svc",
            source="git",
            repo="git@github.com:org/svc.git",
            public_host="svc.test",
        )
        stack = make_stack(self.tmp_path, (make_git_app("svc"),))
        auth = MagicMock()
        auth.is_configured.return_value = False
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError("refused"),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, auth=auth, docker=docker).run()
                )
        assert results[("svc", "auth")].status == "fail"
        assert "auth setup svc" in results[("svc", "auth")].fix
        assert results[("svc", "sync")].status == "fail"
        assert "sync svc" in results[("svc", "sync")].fix
        assert results[("svc", "certs")].status == "ok"
        assert "tls: off" in results[("svc", "certs")].detail
        assert results[(INFRA, "stack")].status == "warn"
        assert results[(INFRA, "port 80")].status == "ok"

    def test_docker_missing_and_daemon_fail(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        shell = MagicMock()
        with patch("raft.services.doctor.shutil.which", return_value=None):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(self._doctor(shell=shell).run())
        assert results[(INFRA, "docker")].status == "fail"

        shell.run.return_value = MagicMock(returncode=1, stdout="", stderr="Cannot connect\n")
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(self._doctor(shell=shell).run())
        assert results[(INFRA, "docker")].status == "fail"
        assert "Cannot connect" in results[(INFRA, "docker")].detail

    def test_git_auth_test_failure_and_non_git_dir(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        dest = self.tmp_path / "apps" / "svc"
        dest.mkdir(parents=True)
        (dest / "README").write_text("x", encoding="utf-8")
        write_applied_app(
            self.tmp_path,
            "svc",
            source="git",
            repo="git@github.com:org/svc.git",
            public_host="svc.test",
        )
        stack = make_stack(self.tmp_path, (make_git_app("svc"),))
        auth = MagicMock()
        auth.is_configured.return_value = True
        auth.test.side_effect = RuntimeError("auth test failed")
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, auth=auth, docker=docker).run()
                )
        assert results[("svc", "auth")].status == "fail"
        assert results[("svc", "sync")].status == "fail"
        assert "not a git checkout" in results[("svc", "sync")].detail
        assert "github.com/org/svc/settings/keys/new" in results[("svc", "auth")].fix

    def test_missing_compose_and_port_conflict(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("app"),))
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        compose = self.tmp_path / "compose.yaml"
        if compose.is_file():
            compose.unlink()
        gen = self.tmp_path / "generated" / "compose.apps.yaml"
        if gen.is_file():
            gen.unlink()
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch("raft.services.doctor.socket.create_connection"):
                results = self._by_key(
                    self._doctor(stack, shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[(INFRA, "compose.yaml")].status == "fail"
        assert results[(INFRA, "generated")].status == "fail"
        assert results[(INFRA, "port 80")].status == "warn"

    def test_git_ok_partial_stack_and_gate_owns_port(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        dest = self.tmp_path / "apps" / "svc"
        dest.mkdir(parents=True)
        (dest / ".git").mkdir()
        self._write_certs("svc")
        write_applied_app(
            self.tmp_path,
            "svc",
            source="git",
            repo="git@github.com:org/svc.git",
            public_host="svc.test",
        )
        stack = make_stack(self.tmp_path, (make_git_app("svc"),))
        auth = MagicMock()
        auth.is_configured.return_value = True
        auth.test.return_value = None
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = ["gate"]

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch("raft.services.doctor.socket.create_connection"):
                results = self._by_key(
                    self._doctor(stack, shell=shell, auth=auth, docker=docker).run()
                )
        assert results[("svc", "auth")].status == "ok"
        assert results[("svc", "sync")].status == "ok"
        assert results[("svc", "upstream")].status == "warn"
        assert results[("svc", "certs")].status == "ok"
        assert results[(INFRA, "stack")].status == "warn"
        assert "missing" in results[(INFRA, "stack")].detail
        assert results[(INFRA, "port 80")].status == "ok"

    def test_stack_query_error_and_port_query_error(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.side_effect = RuntimeError("compose broke")

        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch("raft.services.doctor.socket.create_connection"):
                results = self._by_key(
                    self._doctor(shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[(INFRA, "stack")].status == "warn"
        assert "compose broke" in results[(INFRA, "stack")].detail
        assert results[(INFRA, "port 80")].status == "warn"

    def test_local_path_missing(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[("app", "sync")].status == "fail"
        assert results[("app", "certs")].status == "ok"

    def test_docker_source_image_checks(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        self._write_certs("hub")
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        stack = make_stack(self.tmp_path, (app,))
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.sh.docker.return_value = MagicMock(returncode=0, stdout="sha256:abc\n", stderr="")
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[("hub", "sync")].status == "ok"
        assert "ghcr.io/org/hub:main" in results[("hub", "sync")].detail
        assert results[("hub", "auth")].status == "ok"
        assert "registry auth" in results[("hub", "auth")].detail
        assert results[("hub", "contract")].status == "fail"

    def test_docker_with_repo_checks_contract_and_auth(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "generated" / "compose.apps.yaml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (self.tmp_path / "generated" / "compose.apps.yaml").write_text("services: {}\n")
        self._write_certs("hub")
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            repo="git@github.com:org/hub.git",
            path="apps/hub",
        )
        checkout = self.tmp_path / "apps" / "hub"
        checkout.mkdir(parents=True)
        reg = self.tmp_path / "state" / "apps" / "hub.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: hub\nspec:\n"
            "  publicHost: hub.test\n  source: docker\n  image: ghcr.io/org/hub\n"
            "  ref: main\n  repo: git@github.com:org/hub.git\n  path: apps/hub\n"
            "  www: false\n  ports:\n"
            "    - name: http\n      containerPort: 80\n      expose: http\n",
            encoding="utf-8",
        )
        stack = make_stack(self.tmp_path, (app,))
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.sh.docker.return_value = MagicMock(returncode=0, stdout="sha256:abc\n", stderr="")
        auth = MagicMock()
        auth.is_configured.return_value = True
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, docker=docker, auth=auth).run()
                )
        assert results[("hub", "contract")].status == "ok"
        assert results[("hub", "auth")].status == "ok"
        assert "deploy key present" in results[("hub", "auth")].detail

    def test_docker_with_repo_warns_without_deploy_key(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "generated" / "compose.apps.yaml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (self.tmp_path / "generated" / "compose.apps.yaml").write_text("services: {}\n")
        self._write_certs("hub")
        app = make_app(
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            ref="main",
            repo="git@github.com:org/hub.git",
            path="apps/hub",
        )
        (self.tmp_path / "apps" / "hub").mkdir(parents=True)
        stack = make_stack(self.tmp_path, (app,))
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.sh.docker.return_value = MagicMock(returncode=0, stdout="sha256:abc\n", stderr="")
        auth = MagicMock()
        auth.is_configured.return_value = False
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, docker=docker, auth=auth).run()
                )
        assert results[("hub", "auth")].status == "warn"
        assert results[("hub", "contract")].status == "fail"

    def test_contract_invalid_content(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "generated" / "compose.apps.yaml").parent.mkdir(
            parents=True, exist_ok=True
        )
        (self.tmp_path / "generated" / "compose.apps.yaml").write_text("services: {}\n")
        self._write_certs("app")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        reg = self.tmp_path / "state" / "apps" / "app.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            "apiVersion: nope\nkind: App\nmetadata:\n  name: app\nspec:\n  publicHost: app.test\n  source: local\n",
            encoding="utf-8",
        )
        stack = make_stack(self.tmp_path, (make_app("app"),))
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(self._doctor(stack, shell=shell, docker=docker).run())
        assert results[("app", "contract")].status == "fail"
        assert "apiVersion" in results[("app", "contract")].detail

    def test_docker_source_image_missing(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        self._write_certs("hub")
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        stack = make_stack(self.tmp_path, (app,))
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.sh.docker.return_value = MagicMock(returncode=1, stdout="", stderr="missing")
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(stack, shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[("hub", "sync")].status == "fail"
        assert "docker pull" in (results[("hub", "sync")].fix or "")

    def test_certs_partial_pair_fails(self) -> None:
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        write_applied_app(self.tmp_path, "app", tls="origin")
        d = self.tmp_path / "certs" / "app"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("pem\n", encoding="utf-8")
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        with patch("raft.services.doctor.shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "raft.services.doctor.socket.create_connection",
                side_effect=OSError(),
            ):
                results = self._by_key(
                    self._doctor(shell=shell, docker=docker, auth=MagicMock()).run()
                )
        assert results[("app", "certs")].status == "fail"
        assert "origin.key" in results[("app", "certs")].detail
        assert "tls: origin" in results[("app", "certs")].fix

    def test_report_unknown_service_appended(self, capsys) -> None:
        d = self._doctor()
        assert d.report([CheckResult("custom", "item", "ok", "fine")]) == 0
        out = capsys.readouterr().out
        assert "  OK    custom" in out

    def test_auth_deploy_key_fix_urls(self) -> None:
        assert "github.com/acme/site/settings/keys/new" in Doctor._auth_deploy_key_fix(
            "svc", "git@github.com:acme/site.git"
        )
        assert "Title + Key" in Doctor._auth_deploy_key_fix("svc", "git@github.com:acme/site.git")
        assert "gitlab.com" in Doctor._auth_deploy_key_fix("svc", "git@gitlab.com:acme/site.git")
        assert "on the git host" in Doctor._auth_deploy_key_fix("svc", "not-a-url")

    def test_report_blank_lines_between_ok_and_issues(self, capsys) -> None:
        d = self._doctor()
        assert (
            d.report(
                [
                    CheckResult(INFRA, "docker", "ok", "fine"),
                    CheckResult("svc", "auth", "fail", "bad", fix="fix"),
                    CheckResult("other", "sync", "ok", "fine"),
                ],
                color=False,
            )
            == 1
        )
        out = capsys.readouterr().out
        assert "  OK    infra\n\nsvc\n" in out
        assert "fix: fix\n\n  OK    other" in out
