"""AcmeGateInstall render + reload."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.models.stack import load_stack
from raft.services.acme.install import AcmeGateInstall

from ...base import RaftTestCase, write_applied_app


class TestAcmeGateInstall(RaftTestCase):
    def test_render_and_reload_when_gate_running(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="acme")
        d = self.tmp_path / "certs" / "web"
        d.mkdir(parents=True)
        (d / "acme.pem").write_text("pem\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        stack = load_stack(self.tmp_path)
        docker = MagicMock()
        docker.running_services.return_value = [stack.gate]
        with patch("raft.services.acme.install.StackRenderer") as renderer_cls:
            with patch("raft.services.acme.install.GateNginxStamp") as stamp_cls:
                stamp = stamp_cls.return_value
                stamp.fingerprint.return_value = "abc"
                AcmeGateInstall(stack, docker).apply()
        renderer_cls.return_value.render.assert_called_once()
        docker.reload_gate_nginx.assert_called_once()
        stamp.write.assert_called_once_with("abc")

    def test_skips_reload_when_gate_down(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        stack = load_stack(self.tmp_path)
        docker = MagicMock()
        docker.running_services.return_value = []
        with patch("raft.services.acme.install.StackRenderer"):
            AcmeGateInstall(stack, docker).apply()
        docker.reload_gate_nginx.assert_not_called()

    def test_render_only_without_docker(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        stack = load_stack(self.tmp_path)
        with patch("raft.services.acme.install.StackRenderer") as renderer_cls:
            AcmeGateInstall(stack).apply()
        renderer_cls.return_value.render.assert_called_once()
