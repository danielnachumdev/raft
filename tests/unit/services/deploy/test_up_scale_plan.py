"""StackUpScalePlan unit coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.errors import OperatorError
from raft.models.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.deploy.up_scale_plan import StackUpScalePlan
from tests.unit.base import write_applied_app
from tests.unit.controller.base import ControllerTestCase


class TestStackUpScalePlan(ControllerTestCase):
    def test_empty_without_scaling(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path)
        plan = StackUpScalePlan(load_stack(home))
        assert not plan.has_deferred()
        assert plan.deferred_compose_ids() == ()
        assert [a.name for a in plan.apps_to_start()] == [self.APP]

    def test_scaling_app_and_costop_dep(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "api")
        write_applied_app(
            home,
            self.APP,
            extra={**self.scaling_extra(), "dependsOn": ["api"]},
        )
        plan = StackUpScalePlan(load_stack(home))
        assert plan.has_deferred()
        assert set(plan.deferred_compose_ids()) == {"api", self.APP}
        assert plan.apps_to_start() == ()
        assert plan.start_compose_ids() == (
            "raft-gate",
            "raft-router",
            "raft-controller",
        )

    def test_scale_with_parent_false_not_deferred(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "sidecar")
        write_applied_app(
            home,
            self.APP,
            extra={
                **self.scaling_extra(),
                "dependsOn": [{"name": "sidecar", "scaleWithParent": False}],
            },
        )
        plan = StackUpScalePlan(load_stack(home))
        assert plan.deferred_compose_ids() == (self.APP,)
        assert [a.name for a in plan.apps_to_start()] == ["sidecar"]

    def test_mark_scaled_to_zero(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        plan = StackUpScalePlan(load_stack(home))
        plan.mark_scaled_to_zero()
        assert ScalingStore(home).is_scaled_to_zero(self.APP)

    def test_broken_depends_still_defers_scaling_app(self, tmp_path: Path) -> None:
        home = self.applied_home(
            tmp_path,
            extra={**self.scaling_extra(), "dependsOn": ["missing"]},
        )
        plan = StackUpScalePlan(load_stack(home))
        assert plan.deferred_compose_ids() == (self.APP,)

    def test_missing_spec_file_skips_app(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        stack = load_stack(home)
        path = home / "state" / "apps" / f"{self.APP}.yaml"
        path.unlink()
        plan = StackUpScalePlan(stack)
        assert not plan.has_deferred()

    @pytest.mark.parametrize(
        "exc",
        [OSError("io"), ValueError("bad"), OperatorError("boom", has_fix=False)],
    )
    def test_spec_load_errors_skip_scaling(self, tmp_path: Path, exc: Exception) -> None:
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        stack = load_stack(home)
        with patch(
            "raft.services.deploy.up_scale_plan.AppDocument.load",
            side_effect=exc,
        ):
            plan = StackUpScalePlan(stack)
        assert not plan.has_deferred()
