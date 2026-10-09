"""DependsOnCycleGuard — apply-time cycle reject."""

from __future__ import annotations

import pytest

from raft.errors.cta import OperatorError
from raft.models.depends import DependsOnSpec
from raft.models.depends_cycle import DependsOnCycleGuard

from ..base import RaftTestCase, write_applied_app


class TestDependsOnCycleGuard(RaftTestCase):
    def test_acyclic_ok(self) -> None:
        write_applied_app(
            self.tmp_path,
            "db",
            public_host="db.test",
            extra={"dependsOn": []},
        )
        write_applied_app(
            self.tmp_path,
            "api",
            public_host="api.test",
            extra={"dependsOn": ["db"]},
        )
        DependsOnCycleGuard(self.tmp_path).reject(
            "front",
            (DependsOnSpec("api", scale_with_parent=True),),
        )

    def test_rejects_ab_ba(self) -> None:
        write_applied_app(
            self.tmp_path,
            "a",
            public_host="a.test",
            extra={"dependsOn": ["b"]},
        )
        with pytest.raises(OperatorError, match="dependsOn cycle") as exc:
            DependsOnCycleGuard(self.tmp_path).reject("b", (DependsOnSpec("a"),))
        assert "Fix:" in str(exc.value)

    def test_rejects_self_loop(self) -> None:
        with pytest.raises(OperatorError, match="dependsOn cycle"):
            DependsOnCycleGuard(self.tmp_path).reject(
                "worker", (DependsOnSpec("worker"),)
            )

    def test_rejects_longer_cycle(self) -> None:
        write_applied_app(
            self.tmp_path,
            "front",
            public_host="front.test",
            extra={"dependsOn": ["api"]},
        )
        write_applied_app(
            self.tmp_path,
            "api",
            public_host="api.test",
            extra={"dependsOn": ["db"]},
        )
        with pytest.raises(OperatorError, match="dependsOn cycle"):
            DependsOnCycleGuard(self.tmp_path).reject(
                "db", (DependsOnSpec("front"),)
            )

    def test_object_form_scale_with_parent(self) -> None:
        write_applied_app(
            self.tmp_path,
            "a",
            public_host="a.test",
            extra={
                "dependsOn": [
                    {"name": "b", "scaleWithParent": False},
                ]
            },
        )
        with pytest.raises(OperatorError, match="dependsOn cycle"):
            DependsOnCycleGuard(self.tmp_path).reject(
                "b",
                (DependsOnSpec("a", scale_with_parent=True),),
            )

    def test_unknown_dep_not_treated_as_cycle(self) -> None:
        DependsOnCycleGuard(self.tmp_path).reject(
            "front",
            (DependsOnSpec("missing-dep"),),
        )

    def test_reapply_overlays_existing_edges(self) -> None:
        write_applied_app(
            self.tmp_path,
            "api",
            public_host="api.test",
            extra={"dependsOn": []},
        )
        write_applied_app(
            self.tmp_path,
            "front",
            public_host="front.test",
            extra={"dependsOn": ["api"]},
        )
        DependsOnCycleGuard(self.tmp_path).reject(
            "front",
            (DependsOnSpec("api"),),
        )

    def test_edges_for_missing_and_corrupt(self) -> None:
        guard = DependsOnCycleGuard(self.tmp_path)
        assert guard._edges_for("missing") == ()
        dest = write_applied_app(
            self.tmp_path,
            "broken",
            public_host="broken.test",
        )
        dest.write_text("{{{{", encoding="utf-8")
        assert guard._edges_for("broken") == ()
