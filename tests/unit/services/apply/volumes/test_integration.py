"""CLI get/apply/doctor/render for groups and volumes."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from raft.cli import get as get_cmd
from raft.models.stack import load_stack
from raft.services.apply import AppApply
from raft.services.ops.doctor import INFRA, CheckResult, Doctor
from raft.services.render import StackRenderer

from ....base import write_applied_app
from .base import VolumesTestCase


class TestVolumesIntegration(VolumesTestCase):
    def test_get_apps_group_filter_and_spec_errors(self) -> None:
        write_applied_app(self.tmp_path, "a", extra={"group": "demo"})
        write_applied_app(self.tmp_path, "b")
        stack = load_stack(self.tmp_path)
        get_cmd.get_apps(stack, group="demo")
        get_cmd.get_apps(stack, group="missing")
        get_cmd.get_app(stack, "a")
        get_cmd.get_apps(stack)

    def test_apply_warns_missing_depends_on(self) -> None:
        path = self.tmp_path / "app.yaml"
        doc = self.base_docker(name="stack-front")
        doc["spec"]["dependsOn"] = ["stack-redis"]
        path.write_text(yaml.safe_dump(doc), encoding="utf-8")
        with patch("raft.services.apply.service.say") as say:
            AppApply(load_stack(self.tmp_path)).apply_file(path, deploy=False)
        assert any("dependsOn not yet applied" in str(c) for c in say.call_args_list)
        self._assert_git_apply_warns_depends_on()

    def _assert_git_apply_warns_depends_on(self) -> None:
        shell = MagicMock()
        shell.git.side_effect = self._clone_with_depends_on
        applier = AppApply(load_stack(self.tmp_path))
        applier.sh = shell
        with patch("raft.services.apply.service.say") as say_git:
            applier.apply_git("git@github.com:org/stack.git", deploy=False)
        assert any("dependsOn not yet applied" in str(c) for c in say_git.call_args_list)

    def _clone_with_depends_on(self, *args, **kwargs):
        if "clone" not in args:
            return
        target = Path(args[-1])
        (target / ".raft").mkdir(parents=True, exist_ok=True)
        git_doc = self.base_docker(name="stack-admin")
        git_doc["spec"]["dependsOn"] = ["stack-redis"]
        (target / ".raft" / "app.yaml").write_text(yaml.safe_dump(git_doc), encoding="utf-8")

    def test_doctor_group_banner(self) -> None:
        write_applied_app(self.tmp_path, "stack-a", extra={"group": "demo"})
        write_applied_app(self.tmp_path, "solo")
        text = self._report(
            load_stack(self.tmp_path),
            [
                CheckResult(INFRA, "docker", "ok", "fine"),
                CheckResult("demo-stack-a", "contract", "ok", "fine"),
                CheckResult("solo", "contract", "ok", "fine"),
            ],
        )
        self._assert_mixed_group_out(text)
        self._assert_doctor_grouped_only_banner()

    def _report(self, stack, results) -> str:
        d = Doctor(stack)
        d.sh = MagicMock()
        d.auth = MagicMock()
        d.docker = MagicMock()
        buf = StringIO()
        assert d.report(results, out=buf, color=False) == 0
        return buf.getvalue()

    def _assert_mixed_group_out(self, text: str) -> None:
        assert "demo\n" in text and "  stack-a\n" in text
        assert "  demo-stack-a\n" not in text and "ungrouped\n" not in text
        assert "solo\n" in text and "group: demo" not in text
        assert "infra\n" not in text and "raft\n" in text
        assert "  gate\n" in text and "  router\n" in text
        assert "  raft-gate\n" not in text and "  docker\n" not in text

    def _assert_doctor_grouped_only_banner(self) -> None:
        only_grouped = self.tmp_path / "grouped-only"
        only_grouped.mkdir()
        write_applied_app(only_grouped, "stack-b", extra={"group": "demo"})
        text3 = self._report(
            load_stack(only_grouped),
            [
                CheckResult(INFRA, "docker", "ok", "fine"),
                CheckResult("demo-stack-b", "contract", "ok", "fine"),
            ],
        )
        assert "ungrouped\n" not in text3 and "demo\n" in text3
        assert "  stack-b\n" in text3 and "  demo-stack-b\n" not in text3

    def test_render_quoted_env(self) -> None:
        write_applied_app(
            self.tmp_path, "svc", source="docker", image="redis",
            public_host="", build_context=None,
            extra={
                "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
                "readiness": {"type": "none"},
                "env": {"EMPTY": "", "COLON": "a:b"},
            },
        )
        StackRenderer(load_stack(self.tmp_path)).render()
        text = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert 'EMPTY: ""' in text and 'COLON: "a:b"' in text
