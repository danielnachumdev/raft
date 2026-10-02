"""Batch compose ps parser and DockerStack.running_services collapse."""

from __future__ import annotations

from raft.adapters.docker.compose_status import ComposeServiceRow, ComposeStatusTable

from .base import DockerTestCase


class TestComposeStatusTable:
    def test_parse_service_state_health(self) -> None:
        table = ComposeStatusTable.from_ps_stdout(
            "raft-gate running\n"
            "raft-router running healthy\n"
            "app running unhealthy\n"
            "web restarting\n"
            "\n"
            "bad-line\n"
        )
        assert table.runtime("raft-gate") == ("running", "none")
        assert table.runtime("raft-router") == ("running", "healthy")
        assert table.runtime("app") == ("running", "unhealthy")
        assert table.runtime("web") == ("restarting", "none")
        assert table.runtime("missing") == ("missing", "none")
        assert table.is_running("raft-gate") is True
        assert table.is_running("web") is False
        assert table.running_names(["raft-gate", "web", "ghost"]) == ["raft-gate"]

    def test_parse_normalizes_case_and_empty_health(self) -> None:
        row = ComposeStatusTable._parse_line("svc Running ")
        assert row == ComposeServiceRow("svc", "running", "none")
        assert ComposeStatusTable._parse_line("") is None

    def test_from_runtime_map(self) -> None:
        table = ComposeStatusTable.from_runtime_map({"a": ("running", ""), "b": ("exited", "none")})
        assert table.runtime("a") == ("running", "none")
        assert table.get("b") is not None


class TestComposeStatusBatch(DockerTestCase):
    def test_running_services_one_compose_ps(self) -> None:
        self.shell.compose.return_value = self.ok(
            "raft-gate running\n"
            "raft-router running healthy\n"
            "app exited\n"
        )
        assert self.docker.running_services() == ["raft-gate", "raft-router"]
        assert self.shell.compose.call_count == 1
        self.shell.compose.assert_called_once_with(
            "ps",
            "--format",
            "{{.Service}} {{.State}} {{.Health}}",
            capture=True,
            check=False,
        )

    def test_compose_service_status_empty_on_failure(self) -> None:
        self.shell.compose.return_value = self.ok("", returncode=1)
        table = self.docker.compose_service_status()
        assert list(table.services()) == []
        assert self.docker.running_services() == []
