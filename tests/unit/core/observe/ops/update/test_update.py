"""Self-update / reinstall via remote install.sh (no lasting clone)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

from datetime import datetime, timezone

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.graph_event_kinds import KIND_UPDATE
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.ops import update as update_mod
from raft.core.observe.ops.update import identity as identity_mod
from raft.core.observe.ops.update import DEFAULT_INSTALL_URL, InstallIdentity, SelfUpdate
from raft.core.core.ui.progress import TerminalProgress

from tests.unit.domain_case import DomainTestCase

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class TestSelfUpdate(DomainTestCase):
    def setup_method(self) -> None:
        TerminalProgress._active = None

    def teardown_method(self) -> None:
        TerminalProgress._active = None

    def test_run_fetches_remote_install_script(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say") as say:
            upd.run()
        shell.run.assert_called_once()
        args = shell.run.call_args.args[0]
        assert args[0] == "bash"
        assert args[1] == "-c"
        assert "curl -fsSL" in args[2]
        assert args[4] == DEFAULT_INSTALL_URL
        assert "RAFT_INSTALL_QUIET=1" in args[2]
        styles = [c.kwargs.get("style") for c in say.call_args_list]
        assert "ok" in styles and styles.count("info") >= 1
        next_body = " ".join(c.args[0] for c in say.call_args_list if c.args)
        assert "raft render" in next_body and "raft doctor" in next_body
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
        upd = SelfUpdate(self.stack)
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
        upd = SelfUpdate(self.stack)
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
        upd = SelfUpdate(self.stack)
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
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run()
        assert shell.run.call_args.args[0][4] == url

    def test_run_passes_ref_as_raft_ref_env(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run(ref="main")
        script = shell.run.call_args.args[0][2]
        assert "RAFT_INSTALL_QUIET=1" in script
        assert "RAFT_REF=main" in script
        assert shell.run.call_args.args[0][4] == DEFAULT_INSTALL_URL

    def test_run_omits_raft_ref_when_ref_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run()
        script = shell.run.call_args.args[0][2]
        assert "RAFT_REF=" not in script

    def test_run_ignores_local_install_script(self, monkeypatch) -> None:
        script = self.tmp_path / "install.sh"
        script.write_text("#!/bin/bash\n", encoding="utf-8")
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod.InstallIdentity, "read", lambda self: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
            upd.run()
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
        upd = SelfUpdate(self.stack)
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
        upd = SelfUpdate(self.stack)
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
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        with TerminalProgress(prefix="raft update", label="updating"):
            with patch("raft.core.observe.ops.update.announce.OperatorSay.say"):
                upd.run()
            assert TerminalProgress.active() is not None
            assert TerminalProgress.current()._finished
        shell.run.assert_called_once()

    def test_set_label_noop_without_active_spinner(self) -> None:
        SelfUpdate._set_label("checking install")

    def test_version_line_none_without_dist_info(self, monkeypatch) -> None:
        monkeypatch.setattr(
            update_mod.InstallIdentity, "dist_info_dir", lambda self: None
        )
        assert SelfUpdate(self.stack)._version_line() is None


class TestInstallIdentity(DomainTestCase):
    def _fake_tool_env(
        self, *, direct_url: Optional[str] = None, metadata: Optional[str] = None
    ) -> Path:
        root = self.tmp_path / "tools" / "raft"
        dist = root / "lib" / "python3.12" / "site-packages" / "raft-0.1.0.dist-info"
        dist.mkdir(parents=True)
        if direct_url is not None:
            (dist / "direct_url.json").write_text(direct_url, encoding="utf-8")
        if metadata is not None:
            (dist / "METADATA").write_text(metadata, encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir(parents=True)
        raft_bin = bin_dir / "raft"
        raft_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        return root

    def test_dist_info_dir_via_which(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"url":"x"}')
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        dist = InstallIdentity().dist_info_dir()
        assert dist is not None
        assert dist.name == "raft-0.1.0.dist-info"

    def test_identity_from_direct_url_via_which(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"url":"git","vcs_info":{"commit_id":"abc"}}\n')
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        assert InstallIdentity().read() == '{"url":"git","vcs_info":{"commit_id":"abc"}}'

    def test_identity_falls_back_to_metadata(self, monkeypatch) -> None:
        root = self._fake_tool_env(metadata="Name: raft\nVersion: 0.1.0\n")
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        identity = InstallIdentity().read() or ""
        assert "0.1.0" in identity

    def test_identity_via_uv_tool_dir_when_which_misses(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"commit":"xyz"}')
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: None)
        monkeypatch.setenv("UV_TOOL_DIR", str(root.parent))
        assert InstallIdentity().read() == '{"commit":"xyz"}'

    def test_identity_none_when_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: None)
        monkeypatch.setenv("UV_TOOL_DIR", str(self.tmp_path / "empty-tools"))
        monkeypatch.setattr(identity_mod.Path, "home", lambda: self.tmp_path / "nohome")
        assert InstallIdentity().read() is None

    def test_identity_none_when_tool_env_has_no_dist_info(self, monkeypatch) -> None:
        root = self.tmp_path / "tools" / "raft"
        (root / "bin").mkdir(parents=True)
        raft_bin = root / "bin" / "raft"
        raft_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        assert InstallIdentity().read() is None

    def test_identity_none_when_dist_info_empty(self, monkeypatch) -> None:
        root = self._fake_tool_env()
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        assert InstallIdentity().read() is None

    def test_identity_falls_through_when_which_not_bin_layout(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"commit":"from-env"}')
        odd = self.tmp_path / "elsewhere" / "raft"
        odd.parent.mkdir(parents=True)
        odd.write_text("x", encoding="utf-8")
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(odd))
        monkeypatch.setenv("UV_TOOL_DIR", str(root.parent))
        assert InstallIdentity().read() == '{"commit":"from-env"}'

    def test_identity_default_home_tool_dir(self, monkeypatch) -> None:
        home = self.tmp_path / "home"
        root = home / ".local" / "share" / "uv" / "tools" / "raft"
        dist = root / "lib" / "python3.12" / "site-packages" / "raft-0.1.0.dist-info"
        dist.mkdir(parents=True)
        (dist / "direct_url.json").write_text('{"ok":1}', encoding="utf-8")
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: None)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.setattr(identity_mod.Path, "home", lambda: home)
        assert InstallIdentity().read() == '{"ok":1}'
