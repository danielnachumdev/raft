"""Doctor public-host probe and port-summary checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.stack import Stack, load_stack
from raft.services.ops.doctor.checks.ports_summary import PortSummaryChecks, _port_number
from raft.services.ops.doctor.checks.public_host import PublicHostChecks
from raft.services.ops.doctor.context import DoctorContext
from tests.shared.compose_ids import RunningServices
from tests.shared.nginx import NginxEmerg

from ....base import make_stack, write_applied_app
from .base import DoctorTestCase


class TestDoctorProbes(DoctorTestCase):
    def test_public_host_probe_fails_when_unreachable(self) -> None:
        write_applied_app(self.tmp_path, "app")
        self.ensure_checkouts("app")
        self.seed_compose()
        docker = self.mock_docker(running=RunningServices.with_apps("app"))
        docker.gate_published_ports.return_value = [80, 443]
        docker.diagnostics_for.return_value = (
            "--- app (running/unhealthy) ---\n" + NginxEmerg.host_not_found()
        )
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ):
            results = self.run_keyed(
                load_stack(self.tmp_path), shell=self.mock_shell(), docker=docker
            )
        self._assert_host_fail(results)

    def _assert_host_fail(self, results) -> None:
        assert results[("app", "host")].status == "fail"
        assert results[("app", "host")].detail
        assert "host not found" in results[("app", "host")].detail
        fix = results[("app", "host")].fix or ""
        assert "redeploy router" in fix
        assert "logs --tail=40 app" in fix

    def _probe_ctx(self, docker: MagicMock) -> DoctorContext:
        write_applied_app(self.tmp_path, "app")
        return DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=docker,
        )

    def test_public_host_probe_survives_diagnostics_errors(self) -> None:
        docker = MagicMock()
        docker.diagnostics_for.side_effect = RuntimeError("docker down")
        ctx = self._probe_ctx(docker)
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ):
            results = PublicHostChecks().run(ctx)
        assert results[0].status == "fail"
        assert results[0].detail
        assert "—" not in results[0].detail

    def test_public_host_probe_header_only_diagnostics(self) -> None:
        docker = MagicMock()
        docker.diagnostics_for.return_value = "--- app (absent) ---"
        ctx = self._probe_ctx(docker)
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ):
            results = PublicHostChecks().run(ctx)
        assert results[0].status == "fail"
        assert "—" not in results[0].detail

    def test_public_host_probe_empty_or_non_str_diagnostics(self) -> None:
        docker = MagicMock()
        ctx = self._probe_ctx(docker)
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=False,
        ):
            docker.diagnostics_for.return_value = ""
            empty = PublicHostChecks().run(ctx)
            docker.diagnostics_for.return_value = {"not": "a string"}
            non_str = PublicHostChecks().run(ctx)
        assert empty[0].status == "fail" and "—" not in empty[0].detail
        assert non_str[0].status == "fail" and "—" not in non_str[0].detail

    def test_public_host_probe_skips_blank_host(self) -> None:
        app = App(name="internal", public_host="", source="local", path="apps/internal")
        ctx = DoctorContext(
            stack=make_stack(self.tmp_path, (app,)),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=MagicMock(),
        )
        assert PublicHostChecks().run(ctx) == []

    def test_port_summary_for_router_and_apps(self) -> None:
        self._seed_web_and_mail()
        ctx = DoctorContext(
            stack=load_stack(self.tmp_path),
            shell=MagicMock(),
            auth=MagicMock(),
            docker=MagicMock(),
        )
        by_key = self.by_key(PortSummaryChecks().run(ctx))
        assert by_key[("raft-router", "ports")].detail == "80"
        assert by_key[("web", "ports")].detail == "80"
        assert by_key[("mail", "ports")].detail == "25"
        assert ("raft-gate", "ports") not in by_key
        self._assert_spec_missing(ctx)
        self._assert_spec_empty_or_dup(ctx)

    def _seed_web_and_mail(self) -> None:
        write_applied_app(self.tmp_path, "web")
        write_applied_app(
            self.tmp_path,
            "mail",
            extra={
                "ports": [
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "stream",
                        "publicPort": 25,
                    }
                ],
                "readiness": {"type": "none"},
            },
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "apps" / "mail").mkdir(parents=True, exist_ok=True)

    def _assert_spec_missing(self, ctx: DoctorContext) -> None:
        def raise_missing(_self, _app):
            raise FileNotFoundError("gone")

        with patch.object(Stack, "spec_for", raise_missing):
            only_router = PortSummaryChecks().run(ctx)
        assert [(r.service, r.check) for r in only_router] == [("raft-router", "ports")]

    def _assert_spec_empty_or_dup(self, ctx: DoctorContext) -> None:
        def empty_or_dup(_self, app):
            if app.name == "mail":
                return AppSpec(
                    ports=(
                        PortSpec(name="a", container_port=80, expose="http"),
                        PortSpec(name="b", container_port=80, expose="none"),
                    )
                )
            return AppSpec(ports=())

        with patch.object(Stack, "spec_for", empty_or_dup):
            mixed = self.by_key(PortSummaryChecks().run(ctx))
        assert mixed[("mail", "ports")].detail == "80"
        assert ("web", "ports") not in mixed
        assert _port_number(PortSpec(name="h", container_port=80, expose="http")) == "80"
