"""Doctor edge/listener coverage edges."""

from unittest.mock import MagicMock, patch

from raft.core.core.models.stack import load_stack
from raft.core.observe.ops.doctor import INFRA
from tests.shared.compose_ids import RunningServices

from tests.unit.base import AppliedInventory, RaftTestCase, ShellMocks
from tests.unit.core.observe.ops.doctor import fixtures as doctor_fx


class TestDoctorEdgeCoverage(RaftTestCase):
    def _seed_app(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "app")
        self.ensure_checkouts("app")
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")

    def _ok_shell(self) -> MagicMock:
        return ShellMocks.stub_run(MagicMock())

    def _run(self, stack, shell, docker, *, connect: bool = False):
        with patch("shutil.which", return_value="/bin/docker"):
            if connect:
                return {
                    (r.service, r.check): r
                    for r in doctor_fx.coverage_doctor(
                        stack, shell=shell, docker=docker
                    ).run()
                }
            with patch("socket.create_connection", side_effect=OSError()):
                return {
                    (r.service, r.check): r
                    for r in doctor_fx.coverage_doctor(
                        stack, shell=shell, docker=docker
                    ).run()
                }

    def test_doctor_gate_drift_and_udp_listener(self) -> None:
        self._seed_app()
        self.write_home_settings(
            "edge:\n  http: 80\n  https: null\n  streams:\n"
            "    - name: dns\n      port: 53\n      protocol: udp\n"
        )
        docker = MagicMock()
        docker.running_services.return_value = RunningServices.with_apps("app")
        docker.gate_published_ports.return_value = [80, 999]
        results = self._run(load_stack(self.tmp_path), self._ok_shell(), docker)
        assert results[("raft-gate", "ports")].status == "fail"
        assert "raft gate recreate" in results[("raft-gate", "ports")].fix
        assert results[(INFRA, "port 53/udp")].status == "ok"

    def test_doctor_no_edge_and_gate_up_not_listening(self) -> None:
        self._seed_app()
        self.write_home_settings("edge:\n  http: null\n  https: null\n  streams: []\n")
        docker = MagicMock()
        docker.running_services.return_value = []
        shell = self._ok_shell()
        results = self._run(load_stack(self.tmp_path), shell, docker, connect=True)
        assert results[(INFRA, "edge")].status == "warn"
        self._assert_gate_not_listening(shell, docker)

    def _assert_gate_not_listening(self, shell, docker) -> None:
        self.write_home_settings("edge:\n  http: 80\n  https: null\n")
        docker.running_services.return_value = ["raft-gate"]
        docker.gate_published_ports.return_value = []
        results = self._run(load_stack(self.tmp_path), shell, docker)
        assert results[(INFRA, "port 80")].status == "warn"
        assert results[("raft-gate", "ports")].status == "warn"

    def test_doctor_stream_only_upstream_and_tls_ok(self) -> None:
        self._seed_mail_origin()
        docker = MagicMock()
        docker.running_services.return_value = []
        docker.gate_published_ports.return_value = [80, 443, 25]
        results = self._run(load_stack(self.tmp_path), self._ok_shell(), docker)
        assert results[("mail", "upstream")].detail.startswith("n/a")
        assert results[("mail", "certs")].status == "ok"

    def _seed_mail_origin(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            tls="origin",
            extra=self._mail_origin_extra(),
        )
        self._write_mail_origin_files()

    @staticmethod
    def _mail_origin_extra() -> dict:
        return {
            "ports": [
                {
                    "name": "smtp",
                    "containerPort": 25,
                    "expose": "stream",
                    "publicPort": 25,
                }
            ],
            "readiness": {"type": "tcp", "port": "smtp"},
        }

    def _write_mail_origin_files(self) -> None:
        d = self.tmp_path / "services" / "mail" / "certs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "origin.pem").write_text("p", encoding="utf-8")
        (d / "origin.key").write_text("k", encoding="utf-8")
        (self.tmp_path / "compose.yaml").write_text("name: x\n", encoding="utf-8")
        self.write_home_settings(
            "edge:\n  http: 80\n  https: 443\n  streams:\n"
            "    - name: smtp\n      port: 25\n"
        )
