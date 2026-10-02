"""Unit tests for ``raft serve`` snapshot view + instructions."""

from __future__ import annotations

from io import StringIO

from raft.models import EDGE_GROUP
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.instructions import ServeInstructions
from raft.services.serve.paths import ServePaths
from raft.services.read import ServeSnapshotView

from ...services.ops.status.fixtures import StatusFixtures


class TestServeInstructions:
    def test_render_includes_url_and_tunnel_examples(self) -> None:
        text = ServeInstructions(8787).render()
        assert "http://127.0.0.1:8787/" in text
        assert "ssh -L 8787:127.0.0.1:8787 USER@VM_HOST" in text
        assert "gcloud compute ssh VM_NAME --zone=ZONE -- -L 8787:127.0.0.1:8787" in text
        assert "Ctrl+C" in text

    def test_print_writes_render(self) -> None:
        buf = StringIO()
        ServeInstructions(9000).print(out=buf)
        assert "http://127.0.0.1:9000/" in buf.getvalue()


class TestServePaths:
    def test_templates_and_static_exist(self) -> None:
        assert (ServePaths.templates_dir() / "index.html").is_file()
        assert (ServePaths.templates_dir() / "trends.html").is_file()
        assert (ServePaths.static_dir() / "style.css").is_file()
        assert (ServePaths.static_dir() / "status.js").is_file()


class TestServeSnapshotView:
    def _snapshot(self) -> StatusSnapshot:
        fx = StatusFixtures
        return StatusSnapshot(
            host=fx.empty_host_status(),
            containers=(
                fx.container("raft-gate", role="gate", group=EDGE_GROUP),
                fx.container("raft-router", role="router", group=EDGE_GROUP),
                fx.container("raft-controller", role="controller", group=EDGE_GROUP),
                fx.container("demo-web", role="app", app="web", group="demo"),
            ),
        )

    def test_splits_control_plane_and_apps(self) -> None:
        view = ServeSnapshotView(self._snapshot())
        plane, apps = view.control_plane(), view.apps()
        assert [r.name for r in plane] == ["gate", "router", "controller"]
        assert [r.group for r in plane] == [EDGE_GROUP] * 3
        assert len(apps) == 1 and apps[0].name == "web" and apps[0].group == "demo"
        assert "%" in apps[0].cpu or apps[0].cpu == "-"

    def test_to_payload_includes_host_and_rows(self) -> None:
        payload = ServeSnapshotView(self._snapshot()).to_payload()
        assert "cpus" in payload["host"]
        assert [r["name"] for r in payload["control_plane"]] == [
            "gate",
            "router",
            "controller",
        ]
        assert payload["apps"][0]["name"] == "web"
        assert set(payload["apps"][0]) == {
            "name",
            "role",
            "group",
            "status",
            "cpu",
            "memory",
            "uptime",
        }
