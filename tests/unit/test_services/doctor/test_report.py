"""Doctor report formatting and grouping."""

from __future__ import annotations

from raft.models.app import GATE_COMPOSE_ID, ROUTER_COMPOSE_ID
from raft.models.stack import load_stack
from raft.services import CheckResult, Doctor
from raft.services.doctor import INFRA

from ...base import make_stack, write_applied_app
from .base import DoctorTestCase
from .report_cases import NoTty, ReportCases, Tty


class TestDoctorReport(DoctorTestCase):
    def test_report_collapses_healthy_and_expands_issues(self, capsys) -> None:
        d = self.doctor()
        self._assert_healthy_collapsed(d, capsys)
        self._assert_warn_expanded(d, capsys)
        self._assert_fail_multiline(d, capsys)
        self._assert_fail_infra(d, capsys)

    def _assert_healthy_collapsed(self, d, capsys) -> None:
        assert d.report(ReportCases.ok_infra_and_svc(), color=False) == 0
        out = capsys.readouterr().out
        assert "raft\n" in out and "  docker\n" not in out
        assert "  gate\n" in out and "  router\n" in out
        assert "  raft-gate\n" not in out and "  raft-router\n" not in out
        assert "infra\n" not in out and "svc\n" in out
        assert "ungrouped\n" not in out and "all checks passed" in out
        assert "\033[" not in out
        assert "  OK    auth" not in out and "  OK    sync" not in out

    def _assert_warn_expanded(self, d, capsys) -> None:
        assert d.report(ReportCases.warn_svc(), color=False) == 0
        out = capsys.readouterr().out
        assert "svc\n" in out and "  WARN" in out
        assert "  maybe" in out or "    maybe" in out
        assert "fix → do x" in out and "warning" in out
        assert "sync" not in out and "auth" not in out

    def _assert_fail_multiline(self, d, capsys) -> None:
        assert d.report(ReportCases.fail_hub_multiline(), color=False) == 1
        out = capsys.readouterr().out
        assert "hub\n" in out and "  FAIL" in out
        assert "docker image missing locally:" in out
        assert "fix → line one" in out and "line two" in out and "line three" in out

    def _assert_fail_infra(self, d, capsys) -> None:
        assert d.report(ReportCases.fail_infra_docker(), color=False) == 1
        out = capsys.readouterr().out
        assert "raft\n" in out and "  docker\n" in out
        assert "    FAIL" in out and "bad" in out
        assert "fix → fix it" in out and "failed" in out

    def test_report_uses_ansi_when_color_enabled(self, capsys) -> None:
        d = self.doctor()
        assert d.report(
            [CheckResult("svc", "auth", "fail", "bad", fix="raft auth setup svc")],
            color=True,
        ) == 1
        assert "\033[31m" in capsys.readouterr().out
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], color=True) == 0
        assert "\033[32m" in capsys.readouterr().out
        assert d.report([CheckResult(INFRA, "stack", "warn", "partial")], color=True) == 0
        assert "\033[33m" in capsys.readouterr().out

    def test_report_respects_no_color_and_isatty(self, monkeypatch) -> None:
        d = self.doctor()
        monkeypatch.delenv("NO_COLOR", raising=False)
        buf = Tty()
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=buf) == 0
        assert "\033[32m" in buf.getvalue()
        monkeypatch.setenv("NO_COLOR", "1")
        buf2 = Tty()
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=buf2) == 0
        assert "\033[" not in buf2.getvalue()
        monkeypatch.delenv("NO_COLOR", raising=False)
        assert d.report([CheckResult(INFRA, "docker", "ok", "fine")], out=NoTty()) == 0

    def test_report_raft_group_and_orphan_paths(self, capsys) -> None:
        write_applied_app(self.tmp_path, "raftling", extra={"group": "raft"})
        write_applied_app(self.tmp_path, "solo")
        d = self.doctor(stack=load_stack(self.tmp_path))
        assert d.report(ReportCases.raft_group_mix(), color=False) == 0
        self._assert_raft_group_out(capsys.readouterr().out)
        self._assert_custom_ungrouped(capsys)

    def _assert_raft_group_out(self, out: str) -> None:
        assert "raft\n" in out
        assert "  compose.yaml\n" not in out and "  port 80\n" not in out
        assert "  gate\n" in out and "  router\n" in out and "  raftling\n" in out
        assert "  OK    80, 443" in out or "OK    80, 443" in out
        assert "  OK    80" in out
        assert "  raft-gate\n" not in out and "  raft-raftling\n" not in out
        assert "ungrouped\n" not in out and "solo\n" in out and "orphan\n" in out

    def _assert_custom_ungrouped(self, capsys) -> None:
        d2 = self.doctor(stack=make_stack(self.tmp_path, apps=()))
        assert d2.report(
            [CheckResult(INFRA, "docker", "ok", "fine"), CheckResult("custom", "item", "ok", "fine")],
            color=False,
        ) == 0
        out2 = capsys.readouterr().out
        assert "ungrouped\n" not in out2 and "custom\n" in out2

    def test_report_edge_already_listed_and_raft_group_dedupe(self, capsys) -> None:
        write_applied_app(self.tmp_path, "gate", extra={"group": "raft"})
        d = self.doctor(stack=load_stack(self.tmp_path))
        assert d.report(
            [
                CheckResult(INFRA, GATE_COMPOSE_ID, "ok", "probe"),
                CheckResult(INFRA, ROUTER_COMPOSE_ID, "ok", "probe"),
                CheckResult(INFRA, "docker", "ok", "fine"),
                CheckResult("raft-gate", "contract", "ok", "app ok"),
            ],
            color=False,
        ) == 0
        out = capsys.readouterr().out
        assert "raft\n" in out and "  gate\n" in out
        assert GATE_COMPOSE_ID not in out and "ungrouped\n" not in out
        self._assert_auth_fix_urls()

    def _assert_auth_fix_urls(self) -> None:
        assert "github.com/acme/site/settings/keys/new" in Doctor._auth_deploy_key_fix(
            "svc", "git@github.com:acme/site.git"
        )
        assert "Title + Key" in Doctor._auth_deploy_key_fix("svc", "git@github.com:acme/site.git")
        assert "gitlab.com" in Doctor._auth_deploy_key_fix("svc", "git@gitlab.com:acme/site.git")
        assert "on the git host" in Doctor._auth_deploy_key_fix("svc", "not-a-url")

    def test_report_blank_lines_between_ok_and_issues(self, capsys) -> None:
        d = self.doctor()
        assert d.report(
            [
                CheckResult(INFRA, "docker", "ok", "fine"),
                CheckResult("svc", "auth", "fail", "bad", fix="fix"),
                CheckResult("other", "sync", "ok", "fine"),
            ],
            color=False,
        ) == 1
        out = capsys.readouterr().out
        assert "raft\n" in out and "  docker\n" not in out
        assert "svc\n" in out and "  FAIL" in out and "fix → fix" in out
        assert "other\n" in out
