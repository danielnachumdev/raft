"""Doctor edge/listener coverage edges."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.models.stack import load_stack
from raft.services.ops.doctor import INFRA

from ...base import RaftTestCase, write_applied_app
from .doctor_fixture import CoverageDoctor


class TestDoctorEdgeCoverage(RaftTestCase):
    def _seed_app(self) -> None:
        write_applied_app(self.tmp_path, "app")
        (self.tmp_path / "apps" / "app").mkdir(parents=True)
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")

    def _run(self, stack, shell, docker, *, connect: bool = False):
        with patch("raft.services.ops.doctor.shutil.which", return_value="/bin/docker"):
            if connect:
                return {
                    (r.service, r.check): r
                    for r in CoverageDoctor.for_stack(stack, shell=shell, docker=docker).run()
                }
            with patch(
                "raft.services.ops.doctor.socket.create_connection", side_effect=OSError()
            ):
                return {
                    (r.service, r.check): r
                    for r in CoverageDoctor.for_stack(stack, shell=shell, docker=docker).run()
                }

    def test_doctor_gate_drift_and_udp_listener(self) -> None:
        self._seed_app()
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: null\n  streams:\n"
            "    - name: dns\n      port: 53\n      protocol: udp\n",
            encoding="utf-8",
        )
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = [
            "raft-gate", "raft-router", "raft-controller", "app"
        ]
        docker.gate_published_ports.return_value = [80, 999]
        results = self._run(load_stack(self.tmp_path), shell, docker)
        assert results[("raft-gate", "ports")].status == "fail"
        assert "raft gate recreate" in results[("raft-gate", "ports")].fix
        assert results[(INFRA, "port 53/udp")].status == "ok"

    def test_doctor_no_edge_and_gate_up_not_listening(self) -> None:
        self._seed_app()
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: null\n  https: null\n  streams: []\n", encoding="utf-8"
        )
        docker = MagicMock()
        docker.running_services.return_value = []
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        results = self._run(load_stack(self.tmp_path), shell, docker, connect=True)
        assert results[(INFRA, "edge")].status == "warn"
        self._assert_gate_not_listening(shell, docker)

    def _assert_gate_not_listening(self, shell, docker) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: null\n", encoding="utf-8"
        )
        docker.running_services.return_value = ["raft-gate"]
        docker.gate_published_ports.return_value = []
        results = self._run(load_stack(self.tmp_path), shell, docker)
        assert results[(INFRA, "port 80")].status == "warn"
        assert results[("raft-gate", "ports")].status == "warn"

    def test_doctor_stream_only_upstream_and_tls_ok(self) -> None:
        self._seed_mail_origin()
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.gate_published_ports.return_value = [80, 443, 25]
        results = self._run(load_stack(self.tmp_path), shell, docker)
        assert results[("mail", "upstream")].detail.startswith("n/a")
        assert results[("mail", "certs")].status == "ok"

    def _seed_mail_origin(self) -> None:
        write_applied_app(
            self.tmp_path, "mail", public_host="mail.example.com", tls="origin",
            extra={
                "ports": [{"name": "smtp", "containerPort": 25, "expose": "stream", "publicPort": 25}],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )
        d = self.tmp_path / "certs" / "mail"
        d.mkdir(parents=True)
        (d / "origin.pem").write_text("p", encoding="utf-8")
        (d / "origin.key").write_text("k", encoding="utf-8")
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  http: 80\n  https: 443\n  streams:\n    - name: smtp\n      port: 25\n",
            encoding="utf-8",
        )
