"""Docker containers_stats + container_inspect_runtime."""

import json
from typing import Any, Optional

from .base import DockerTestCase


class TestDockerStats(DockerTestCase):
    def test_try_service_container_id(self) -> None:
        self.shell.compose.return_value = self.ok("abc123\n")
        assert self.docker.try_service_container_id("app") == "abc123"
        self.shell.compose.return_value = self.ok("", returncode=1)
        assert self.docker.try_service_container_id("app") is None
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.try_service_container_id("app") is None

    def test_containers_stats_empty_and_error(self) -> None:
        assert self.docker.containers_stats([]) == {}
        self.shell.docker.return_value = self.ok(returncode=1, stderr="boom")
        assert self.docker.containers_stats(["cid1"]) == {}

    def test_containers_stats_parses_rows(self) -> None:
        payload = (
            '{"ID":"cid1","CPUPerc":"1.2%","MemUsage":"1MiB / 64MiB",'
            '"MemPerc":"1.5%","NetIO":"1kB / 2kB","BlockIO":"0B / 0B","PIDs":"3"}\n'
            '\nnot-json\n42\n{"ID":""}\n{"ID":"other","CPUPerc":"0%"}\n'
        )
        self.shell.docker.return_value = self.ok(payload)
        by_id = self.docker.containers_stats(["cid1full"])
        assert "cid1" in by_id and by_id["cid1full"]["CPUPerc"] == "1.2%"
        assert "other" in by_id
        assert "cid1full" not in by_id or by_id["cid1full"]["CPUPerc"] == "1.2%"

    def test_containers_stats_container_key(self) -> None:
        self.shell.docker.return_value = self.ok(
            '{"Container":"short","CPUPerc":"0%","MemUsage":"0B / 0B",'
            '"MemPerc":"0%","NetIO":"0B / 0B","BlockIO":"0B / 0B","PIDs":"1"}\n'
        )
        by_container = self.docker.containers_stats(["short"])
        assert by_container["short"]["CPUPerc"] == "0%"

    def test_container_inspect_runtime(self) -> None:
        self.shell.docker.return_value = self.ok(self._inspect_json(health="healthy"))
        info = self.docker.container_inspect_runtime("cid")
        assert info == {
            "status": "running",
            "health": "healthy",
            "started_at": "2024-01-01T00:00:00Z",
            "finished_at": "",
            "restart_count": 0,
            "oom_killed": False,
            "exit_code": None,
            "nano_cpus": 250000000,
            "memory_bytes": 67108864,
        }
        self._assert_inspect_edge_cases()

    @staticmethod
    def _inspect_json(
        *,
        status: str = "running",
        health: Optional[str] = "healthy",
        started: str = "2024-01-01T00:00:00Z",
        nano: Any = 250000000,
        memory: Any = 67108864,
    ) -> str:
        state: dict = {"Status": status, "StartedAt": started}
        if health is not None:
            state["Health"] = {"Status": health}
        return json.dumps(
            {"State": state, "HostConfig": {"NanoCpus": nano, "Memory": memory}}
        )

    def _assert_inspect_edge_cases(self) -> None:
        self.shell.docker.return_value = self.ok(returncode=1)
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("not-json\n")
        assert self.docker.container_inspect_runtime("cid") is None
        self.shell.docker.return_value = self.ok("[]\n")
        assert self.docker.container_inspect_runtime("cid") is None
        self._assert_inspect_no_health_and_coercion()

    def _assert_inspect_no_health_and_coercion(self) -> None:
        self.shell.docker.return_value = self.ok(
            self._inspect_json(health=None, nano=0, memory=0)
        )
        info = self.docker.container_inspect_runtime("cid")
        assert info is not None
        assert info["status"] == "running" and info["health"] == "none"
        assert info["nano_cpus"] == 0 and info["memory_bytes"] == 0
        self.shell.docker.return_value = self.ok(
            self._inspect_json(status="exited", health="", nano=None, memory=True)
        )
        info = self.docker.container_inspect_runtime("cid")
        assert info is not None
        assert info["health"] == "none"
        assert info["nano_cpus"] is None and info["memory_bytes"] is None
        self.shell.docker.return_value = self.ok(
            self._inspect_json(health=None, nano="12", memory="bad")
        )
        info = self.docker.container_inspect_runtime("cid")
        assert info is not None
        assert info["nano_cpus"] == 12 and info["memory_bytes"] is None
