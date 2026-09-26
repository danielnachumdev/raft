"""Shared Doctor test case with mocked host probe."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from raft.services import CheckResult, Doctor

from ..base import ServicesTestCase


class DoctorTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _public_host_ok(self):
        with patch(
            "raft.services.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=True,
        ):
            yield

    def doctor(self, stack=None, **kwargs) -> Doctor:
        stack = stack or self.stack
        shell = kwargs.pop("shell", MagicMock())
        auth = kwargs.pop("auth", MagicMock())
        docker = kwargs.pop("docker", MagicMock())
        if kwargs:
            raise TypeError(f"unexpected Doctor test kwargs: {sorted(kwargs)}")
        if isinstance(docker.gate_published_ports.return_value, MagicMock):
            docker.gate_published_ports.return_value = [80, 443]
        doctor = Doctor(stack)
        doctor.sh = shell
        doctor.auth = auth
        doctor.docker = docker
        return doctor

    def write_certs(self, *names: str) -> None:
        for name in names:
            d = self.tmp_path / "certs" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "origin.pem").write_text("pem\n", encoding="utf-8")
            (d / "origin.key").write_text("key\n", encoding="utf-8")

    def seed_compose(self, text: str = "name: x\n") -> None:
        (self.tmp_path / "compose.yaml").write_text(text, encoding="utf-8")

    def seed_generated_apps(self, text: str = "services: {}\n") -> None:
        path = self.tmp_path / "generated" / "compose.apps.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def mock_shell(self, returncode: int = 0) -> MagicMock:
        shell = MagicMock()
        shell.run.return_value = MagicMock(returncode=returncode, stdout="", stderr="")
        return shell

    def mock_docker(self, running=None, image_rc: int = 0, image_out: str = "sha256:abc\n"):
        docker = MagicMock()
        docker.running_services.return_value = list(running or [])
        docker.sh.docker.return_value = MagicMock(
            returncode=image_rc, stdout=image_out, stderr=""
        )
        return docker

    @contextmanager
    def doctor_env(self, *, connect: bool = False):
        with patch("raft.services.ops.doctor.shutil.which", return_value="/usr/bin/docker"):
            if connect:
                with patch("raft.services.ops.doctor.socket.create_connection"):
                    yield
            else:
                with patch(
                    "raft.services.ops.doctor.socket.create_connection",
                    side_effect=OSError("refused"),
                ):
                    yield

    def run_keyed(self, *args, connect: bool = False, **kwargs):
        with self.doctor_env(connect=connect):
            return self.by_key(self.doctor(*args, **kwargs).run())

    @staticmethod
    def by_key(results) -> dict[tuple[str, str], CheckResult]:
        return {(r.service, r.check): r for r in results}
