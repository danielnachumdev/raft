"""ServeDependsMap + status presentation depends_on coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.models import EDGE_GROUP
from raft.services.ops.status.models import StatusSnapshot
from raft.services.read import ServeDependsMap, ServeSnapshotView, StatusRead

from ...base import RaftTestCase, make_app, make_stack, write_applied_app
from ...services.ops.status.fixtures import StatusFixtures


class TestServeDependsMap(RaftTestCase):
    def test_maps_depends_on_to_compose_ids(self) -> None:
        write_applied_app(
            self.tmp_path,
            "stack-front",
            extra={"group": "demo", "dependsOn": ["stack-redis"]},
        )
        write_applied_app(self.tmp_path, "stack-redis", extra={"group": "demo"})
        stack = make_stack(
            self.tmp_path,
            (
                make_app("stack-front", group="demo"),
                make_app("stack-redis", group="demo"),
            ),
        )
        edges = ServeDependsMap(stack)
        assert edges.for_service("demo-stack-front") == ("demo-stack-redis",)
        assert edges.for_service("demo-stack-redis") == ()
        assert edges.for_service("missing") == ()

    def test_skips_unknown_dep_names(self) -> None:
        write_applied_app(
            self.tmp_path, "web", extra={"dependsOn": ["ghost", "api"]}
        )
        write_applied_app(self.tmp_path, "api")
        stack = make_stack(self.tmp_path, (make_app("web"), make_app("api")))
        assert ServeDependsMap(stack).for_service("web") == ("api",)

    def test_bad_spec_yields_empty_deps(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("web"),))
        assert ServeDependsMap(stack).for_service("web") == ()


class TestStatusDependsPresentation(RaftTestCase):
    def test_api_payload_apps_include_depends_on(self) -> None:
        self._seed_demo_apps()
        stack = make_stack(
            self.tmp_path,
            (
                make_app("frontend-dev", group="demo"),
                make_app("backend-dev", group="demo"),
            ),
        )
        status = MagicMock()
        status.collect.return_value = self._demo_snap()
        payload = StatusRead(stack, status=status).api_payload()
        apps = {row["service"]: row for row in payload["apps"]}
        assert apps["demo-frontend-dev"]["depends_on"] == ["demo-backend-dev"]
        assert apps["demo-backend-dev"]["depends_on"] == []
        assert payload["control_plane"][0]["depends_on"] == []

    def test_view_uses_depends_map(self) -> None:
        write_applied_app(
            self.tmp_path, "front", extra={"dependsOn": ["back"]}
        )
        write_applied_app(self.tmp_path, "back")
        stack = make_stack(self.tmp_path, (make_app("front"), make_app("back")))
        snap = StatusSnapshot(
            host=StatusFixtures.empty_host_status(),
            containers=(
                StatusFixtures.container("front", role="app", app="front"),
                StatusFixtures.container("back", role="app", app="back"),
            ),
        )
        rows = ServeSnapshotView(snap, depends=ServeDependsMap(stack)).apps()
        by_svc = {r.service: r.depends_on for r in rows}
        assert by_svc["front"] == ("back",)
        assert by_svc["back"] == ()

    def _seed_demo_apps(self) -> None:
        write_applied_app(
            self.tmp_path,
            "frontend-dev",
            extra={"group": "demo", "dependsOn": ["backend-dev"]},
        )
        write_applied_app(
            self.tmp_path, "backend-dev", extra={"group": "demo"}
        )

    def _demo_snap(self) -> StatusSnapshot:
        fx = StatusFixtures
        return StatusSnapshot(
            host=fx.empty_host_status(),
            containers=(
                fx.container(
                    "demo-frontend-dev",
                    role="app",
                    app="frontend-dev",
                    group="demo",
                ),
                fx.container(
                    "demo-backend-dev",
                    role="app",
                    app="backend-dev",
                    group="demo",
                ),
                fx.container("raft-gate", role="gate", group=EDGE_GROUP),
            ),
        )
