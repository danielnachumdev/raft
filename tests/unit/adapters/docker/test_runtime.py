"""ContainerRuntimeGateway batch docker ps / inspect / stats."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from raft.adapters.docker.runtime import ContainerRuntimeGateway

from .base import DockerTestCase


class TestContainerRuntimeGateway(DockerTestCase):
    def _gateway(self) -> ContainerRuntimeGateway:
        return ContainerRuntimeGateway(self.shell)

    def test_collect_empty_when_ps_fails(self) -> None:
        self.shell.docker.return_value = self.ok("", returncode=1)
        assert self._gateway().collect(["raft-gate"]) == {}

    def test_collect_batches_ps_inspect_stats(self) -> None:
        self.shell.docker.side_effect = self._ps_inspect_stats()
        rows = self._gateway().collect(["raft-gate", "app", "ghost"])
        assert set(rows) == {"raft-gate", "app"}
        assert rows["raft-gate"].status == "running"
        assert rows["raft-gate"].health == "none"
        assert rows["raft-gate"].stats is not None
        assert rows["raft-gate"].stats["CPUPerc"] == "1.5%"
        assert rows["app"].health == "healthy"
        self._assert_three_docker_calls()

    def _ps_inspect_stats(self):
        inspect_payload = [
            self._inspect_dict("gatecidFULL", status="running", health=None, mem=32),
            self._inspect_dict("appcidFULL", status="running", health="healthy", mem=64),
        ]
        stats = self._stats_json()

        def docker(*args, **kwargs):
            if args[:1] == ("ps",):
                return self.ok("gatecid\traft-gate\nappcid\tapp\n")
            if args[:1] == ("inspect",):
                return self.ok(json.dumps(inspect_payload))
            if args[:1] == ("stats",):
                return self.ok(stats)
            return self.ok()

        return docker

    @staticmethod
    def _stats_json() -> str:
        return (
            '{"ID":"gatecid","CPUPerc":"1.5%","MemUsage":"1MiB / 32MiB",'
            '"MemPerc":"3%","NetIO":"0B / 0B","BlockIO":"0B / 0B","PIDs":"2"}\n'
            '{"ID":"appcid","CPUPerc":"2%","MemUsage":"2MiB / 64MiB",'
            '"MemPerc":"4%","NetIO":"0B / 0B","BlockIO":"0B / 0B","PIDs":"3"}\n'
        )

    def _assert_three_docker_calls(self) -> None:
        assert self.shell.docker.call_count == 3
        ps_args = self.shell.docker.call_args_list[0].args
        assert ps_args[0] == "ps"
        assert "label=com.docker.compose.project=raft" in ps_args
        inspect_args = self.shell.docker.call_args_list[1].args
        assert inspect_args[0] == "inspect"
        assert "gatecid" in inspect_args and "appcid" in inspect_args
        stats_args = self.shell.docker.call_args_list[2].args
        assert stats_args[0] == "stats"

    @staticmethod
    def _inspect_dict(cid: str, *, status: str, health, mem: int) -> dict:
        state = {
            "Status": status,
            "StartedAt": "2024-01-01T00:00:00Z",
        }
        if health is not None:
            state["Health"] = {"Status": health}
        return {
            "Id": cid,
            "State": state,
            "HostConfig": {"NanoCpus": 0, "Memory": mem},
        }

    def test_collect_skips_bad_ps_lines_and_inspect_errors(self) -> None:
        def docker(*args, **kwargs):
            if args[:1] == ("ps",):
                return self.ok("\nbadline\ngatecid\traft-gate\n")
            if args[:1] == ("inspect",):
                return self.ok("", returncode=1)
            if args[:1] == ("stats",):
                return self.ok("", returncode=1)
            return self.ok()

        self.shell.docker.side_effect = docker
        rows = self._gateway().collect(["raft-gate"])
        assert rows["raft-gate"].status == "unknown"
        assert rows["raft-gate"].stats is None

    def test_parse_ps_and_inspect_index_edges(self) -> None:
        assert ContainerRuntimeGateway._parse_ps("") == {}
        assert ContainerRuntimeGateway._parse_ps("onlyid\n") == {}
        assert ContainerRuntimeGateway._parse_ps("gate\traft-gate\n") == {
            "raft-gate": "gate"
        }
        by_id = ContainerRuntimeGateway._index_inspect("not-json", ["cid"])
        assert by_id == {}
        by_id = ContainerRuntimeGateway._index_inspect("{}", ["cid"])
        assert by_id == {}
        by_id = ContainerRuntimeGateway._index_inspect("[1, null]", ["cid"])
        assert by_id == {}
        payload = json.dumps(
            {"Id": "abcdef", "State": {"Status": "running"}, "HostConfig": {}}
        )
        by_id = ContainerRuntimeGateway._index_inspect(payload, ["abc"])
        assert by_id["abc"]["status"] == "running"

    def test_inspect_and_stats_empty_ids(self) -> None:
        gw = self._gateway()
        assert gw._inspect_many([]) == {}
        assert gw._stats_many([]) == {}
        self.shell.docker.assert_not_called()

    def test_collect_no_services_short_circuits(self) -> None:
        assert self._gateway().collect([]) == {}
        self.shell.docker.assert_not_called()
