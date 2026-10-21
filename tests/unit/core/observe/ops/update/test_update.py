"""Self-update / reinstall via remote install.sh (no lasting clone)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.graph_event_kinds import KIND_UPDATE
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.ops import update as update_mod
from raft.core.observe.ops.update import (
    DEFAULT_INSTALL_URL,
    HostApplyGate,
    SelfUpdate,
)
from raft.core.core.ui.progress import TerminalProgress

from tests.unit.domain_case import DomainTestCase

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class TestSelfUpdate(DomainTestCase):
    def setup_method(self) -> None:
        TerminalProgress._active = None

    def teardown_method(self) -> None:
        TerminalProgress._active = None

    @staticmethod
    def _open_gate() -> MagicMock:
        gate = MagicMock(spec=HostApplyGate)
        gate.ensure = MagicMock()
        gate.uses_host_docker.return_value = False
        return gate

    def _upd(self) -> SelfUpdate:
        return SelfUpdate(self.stack, host_gate=self._open_gate())

    def _run_with_shell(self, monkeypatch, *, identity=None, ref=None):
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: identity)
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            if ref is None:
                upd.run()
            else:
                upd.run(ref=ref)
        return shell, say

    @staticmethod
    def _assert_curl_pipeline(args: list) -> None:
        assert args[0] == "bash" and args[1] == "-c"
        assert "set -euo pipefail" in args[2]
        assert "curl -fsSL" in args[2]
        assert args[4] == DEFAULT_INSTALL_URL
        assert "RAFT_INSTALL_QUIET=1" in args[2]

    def test_run_fetches_remote_install_script(self, monkeypatch) -> None:
        shell, say = self._run_with_shell(monkeypatch)
        self._assert_curl_pipeline(shell.run.call_args.args[0])
        styles = [c.kwargs.get("style") for c in say.call_args_list]
        assert "ok" in styles and styles.count("info") >= 1
        next_body = " ".join(c.args[0] for c in say.call_args_list if c.args)
        assert "raft render" in next_body and "raft doctor" in next_body
        assert "raft redeploy dashboard" in next_body
        events = GraphEventStore(self.stack.root).events_in_window(from_ts=_EPOCH)
        assert [e.kind for e in events] == [KIND_UPDATE]

    def test_run_reports_already_up_to_date_when_identity_unchanged(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: "same-id")
        monkeypatch.setattr(
            update_mod.SelfUpdate,
            "_version_line",
            lambda self: "raft 0.1.0 (git main@abc1234)",
        )
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            upd.run()
        texts = [c.args[0] for c in say.call_args_list if c.args]
        assert texts[0] == "raft is already up to date"
        assert texts[1] == "raft 0.1.0 (git main@abc1234)"
        events = GraphEventStore(self.stack.root).events_in_window(from_ts=_EPOCH)
        assert events == []

    def test_run_reports_updated_when_identity_changes(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        identities = iter(["before", "after"])
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: next(identities))
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            upd.run()
        styles = [c.kwargs.get("style") for c in say.call_args_list]
        assert "ok" in styles and styles.count("info") >= 1
        events = GraphEventStore(self.stack.root).events_in_window(from_ts=_EPOCH)
        assert [e.kind for e in events] == [KIND_UPDATE]

    def test_run_wires_version_lines_into_announce(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        identities = iter(["id-a", "id-b"])
        lines = iter(["raft 0.1.0 (git main@abc)", "raft 0.1.0 (git feat/x@def)"])
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: next(identities))
        monkeypatch.setattr(update_mod.SelfUpdate, "_version_line", lambda self: next(lines))
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            upd.run()
        texts = [c.args[0] for c in say.call_args_list if c.args]
        assert texts[0] == (
            "OK: raft 0.1.0 (git main@abc) → raft 0.1.0 (git feat/x@def)"
        )
        assert texts[1].startswith("Next: align the running stack")
        assert "PREVIOUS → CURRENT" not in texts

    def test_run_respects_install_url_env(self, monkeypatch) -> None:
        url = "https://example.test/install.sh"
        monkeypatch.setenv("RAFT_INSTALL_URL", url)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run()
        assert shell.run.call_args.args[0][4] == url

    def test_run_passes_ref_as_raft_ref_env(self, monkeypatch) -> None:
        shell, _ = self._run_with_shell(monkeypatch, ref="main")
        script = shell.run.call_args.args[0][2]
        assert "RAFT_INSTALL_QUIET=1" in script
        assert "RAFT_REF=main" in script
        assert shell.run.call_args.args[0][4] == DEFAULT_INSTALL_URL

    def test_run_omits_raft_ref_when_ref_unset(self, monkeypatch) -> None:
        shell, _ = self._run_with_shell(monkeypatch)
        script = shell.run.call_args.args[0][2]
        assert "RAFT_REF=" not in script

    def test_run_ignores_local_install_script(self, monkeypatch) -> None:
        script = self.tmp_path / "install.sh"
        script.write_text("#!/bin/bash\n", encoding="utf-8")
        shell, _ = self._run_with_shell(monkeypatch)
        args = shell.run.call_args.args[0]
        assert args[4] == DEFAULT_INSTALL_URL
        assert "bash" == args[0]

    def test_run_spins_while_reinstalling(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        order: list[str] = []
        monkeypatch.setattr(update_mod.InstallIdentity, "read", self._active_step(order, "identity"))
        monkeypatch.setattr(update_mod.SelfUpdate, "_version_line", lambda self: None)
        shell = MagicMock()
        shell.run.side_effect = self._active_step(order, "install")
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run(progress_stream=object())
        assert order == ["identity", "install", "identity"]
        assert TerminalProgress.active() is None

    @staticmethod
    def _active_step(order: list[str], name: str):
        def step(*_a, **_k):
            order.append(name)
            assert TerminalProgress.active() is not None
            return None

        return step

    def test_run_clears_spinner_before_error(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("curl failed")
        upd = self._upd()
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            try:
                upd.run(progress_stream=object())
                raise AssertionError("expected OperatorError")
            except OperatorError:
                pass
        assert shell.run.called
        assert TerminalProgress.active() is None

    def test_run_reuses_active_spinner(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = self._upd()
        upd.sh = shell
        with TerminalProgress(prefix="raft update", label="updating"):
            with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
                upd.run()
            assert TerminalProgress.active() is not None
            assert TerminalProgress.current()._finished
        shell.run.assert_called_once()

    def test_run_refuses_when_host_gate_blocks(self) -> None:
        gate = MagicMock(spec=HostApplyGate)
        gate.ensure.side_effect = OperatorError("blocked\nFix: host raft update")
        gate.uses_host_docker.return_value = False
        upd = SelfUpdate(self.stack, host_gate=gate)
        upd.sh = MagicMock()
        try:
            upd.run(announce=False)
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "blocked" in str(exc)
        upd.sh.run.assert_not_called()

    def test_run_uses_host_docker_when_gate_says_so(self, monkeypatch) -> None:
        fake = self._patch_host_docker_path(monkeypatch, identity="after-id")
        identities = iter(["before-id", "after-id"])
        monkeypatch.setattr(
            update_mod.InstallIdentity, "read", lambda self: next(identities)
        )
        monkeypatch.setattr(
            update_mod.SelfUpdate, "_version_line", lambda self: "raft 0.2.0"
        )
        upd = SelfUpdate(self.stack, host_gate=self._docker_gate())
        upd.sh = MagicMock()
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            outcome = upd.run(announce=False)
        fake.run.assert_called_once()
        upd.sh.run.assert_not_called()
        assert outcome.already_current is False
        assert outcome.after_line == "raft 0.2.0"

    def test_run_rejects_empty_host_identity_after_docker(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        fake = self._patch_host_docker_path(monkeypatch, identity=None)
        upd = SelfUpdate(self.stack, host_gate=self._docker_gate())
        upd.sh = MagicMock()
        try:
            upd.run(announce=False)
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "RAFT_HOST_HOME" in str(exc)
        fake.run.assert_called_once()

    @staticmethod
    def _docker_gate() -> MagicMock:
        gate = MagicMock(spec=HostApplyGate)
        gate.ensure = MagicMock()
        gate.uses_host_docker.return_value = True
        return gate

    def _patch_host_docker_path(self, monkeypatch, *, identity) -> MagicMock:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(
            update_mod.InstallIdentity, "read", lambda self: identity
        )
        fake = MagicMock()
        monkeypatch.setattr(
            "raft.core.observe.ops.update.service.HostDockerUpdate",
            lambda sh: fake,
        )
        return fake

    def test_set_label_noop_without_active_spinner(self) -> None:
        SelfUpdate._set_label("checking install")

    def test_version_line_none_without_dist_info(self, monkeypatch) -> None:
        monkeypatch.setattr(
            update_mod.InstallIdentity, "dist_info_dir", lambda self: None
        )
        assert self._upd()._version_line() is None
