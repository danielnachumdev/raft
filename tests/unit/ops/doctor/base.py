"""Shared Doctor test case with mocked host probe."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Mapping, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from raft.adapters.docker.compose_status import ComposeStatusTable
from raft.ops.doctor import CheckResult, Doctor

from tests.unit.services_case import ServicesTestCase


class DoctorTestCase(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _public_host_ok(self):
        with patch(
            "raft.ops.doctor.checks.public_host.HttpProbe.public_host_ok",
            return_value=True,
        ):
            yield

    def doctor(self, stack=None, **kwargs) -> Doctor:
        stack = stack or self.stack
        shell = kwargs.pop("shell", MagicMock())
        auth = kwargs.pop("auth", MagicMock())
        docker = kwargs.pop("docker", None)
        if kwargs:
            raise TypeError(f"unexpected Doctor test kwargs: {sorted(kwargs)}")
        if docker is None:
            docker = self.mock_docker()
        else:
            self._ensure_compose_status(docker)
        if isinstance(docker.gate_published_ports.return_value, MagicMock):
            docker.gate_published_ports.return_value = [80, 443]
        doctor = Doctor(stack)
        doctor.sh = shell
        doctor.auth = auth
        doctor.docker = docker
        return doctor

    @staticmethod
    def _ensure_compose_status(docker: MagicMock) -> None:
        if isinstance(docker.compose_service_status.return_value, ComposeStatusTable):
            return
        if docker.compose_service_status.side_effect is not None:
            return
        running = docker.running_services.return_value
        names = list(running) if isinstance(running, list) else []
        docker.compose_service_status.return_value = ComposeStatusTable.from_runtime_map(
            {name: ("running", "none") for name in names}
        )
        if not isinstance(docker.service_runtime.return_value, tuple):
            docker.service_runtime.return_value = ("running", "none")


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

    def mock_docker(
        self,
        running=None,
        image_rc: int = 0,
        image_out: str = "sha256:abc\n",
        *,
        runtime: Optional[Mapping[str, Tuple[str, str]]] = None,
    ):
        docker = MagicMock()
        names = list(running or [])
        table = self._status_table(names, runtime)
        docker.compose_service_status.return_value = table
        docker.running_services.return_value = names
        docker.service_runtime.return_value = ("running", "none")
        docker.sh.docker.return_value = MagicMock(returncode=image_rc, stdout=image_out, stderr="")
        return docker

    @staticmethod
    def _status_table(
        names: list,
        runtime: Optional[Mapping[str, Tuple[str, str]]],
    ) -> ComposeStatusTable:
        mapping = {name: ("running", "none") for name in names}
        if runtime:
            mapping.update(runtime)
        return ComposeStatusTable.from_runtime_map(mapping)

    @contextmanager
    def doctor_env(self, *, connect: bool = False):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            if connect:
                with patch("socket.create_connection"):
                    yield
            else:
                with patch(
                    "socket.create_connection",
                    side_effect=OSError("refused"),
                ):
                    yield

    def run_keyed(self, *args, connect: bool = False, **kwargs):
        with self.doctor_env(connect=connect):
            return self.by_key(self.doctor(*args, **kwargs).run())

    @staticmethod
    def by_key(results) -> dict[tuple[str, str], CheckResult]:
        return {(r.service, r.check): r for r in results}
