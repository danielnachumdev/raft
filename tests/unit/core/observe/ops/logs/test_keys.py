"""Service log store key mapping."""

from raft.core.observe.ops.logs.keys import ServiceLogsKeys

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestServiceLogsKeys(RaftTestCase):
    def test_tmp_container_maps_to_compose_id(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        keys = ServiceLogsKeys(stack)
        assert keys.key_for_container_name("raft-demo-api_tmp") == "demo-api"
        assert keys.key_for_container_name(stack.apps[0].tmp_container) == "demo-api"

    def test_known_compose_ids_include_edge(self) -> None:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("demo-api"),)
        )
        ids = ServiceLogsKeys(stack).known_compose_ids(include_edge=True)
        assert "raft-gate" in ids and "demo-api" in ids
        assert "raft-gate" not in ServiceLogsKeys(stack).known_compose_ids(
            include_edge=False
        )
