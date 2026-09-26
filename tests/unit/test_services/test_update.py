"""Self-update / reinstall via remote install.sh (no lasting clone)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from raft.services.ops import update as update_mod
from raft.services.ops.update import DEFAULT_INSTALL_URL, SelfUpdate, install_identity

from .base import ServicesTestCase


class TestSelfUpdate(ServicesTestCase):
    def test_run_fetches_remote_install_script(self, capsys, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod, "install_identity", lambda: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        upd.run()
        shell.run.assert_called_once()
        args = shell.run.call_args.args[0]
        assert args[0] == "bash"
        assert args[1] == "-c"
        assert "curl -fsSL" in args[2]
        assert args[4] == DEFAULT_INSTALL_URL
        out = capsys.readouterr().out
        assert "Updating raft" in out
        assert "OK: raft updated" in out
        assert "raft render" in out
        assert "raft down && raft up" in out
        assert "RAFT_INSTALL_QUIET=1" in args[2]

    def test_run_reports_already_up_to_date_when_identity_unchanged(
        self, capsys, monkeypatch
    ) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod, "install_identity", lambda: "same-id")
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        upd.run()
        out = capsys.readouterr().out
        assert "Updating raft" in out
        assert "raft is already up to date" in out
        assert "OK: raft updated" not in out
        assert "raft render" not in out

    def test_run_reports_updated_when_identity_changes(self, capsys, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        identities = iter(["before", "after"])
        monkeypatch.setattr(update_mod, "install_identity", lambda: next(identities))
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        upd.run()
        out = capsys.readouterr().out
        assert "OK: raft updated" in out
        assert "raft down && raft up" in out
        assert "already up to date" not in out

    def test_run_respects_install_url_env(self, monkeypatch) -> None:
        url = "https://example.test/install.sh"
        monkeypatch.setenv("RAFT_INSTALL_URL", url)
        monkeypatch.setattr(update_mod, "install_identity", lambda: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        upd.run()
        assert shell.run.call_args.args[0][4] == url

    def test_run_ignores_local_install_script(self, monkeypatch) -> None:
        script = self.tmp_path / "install.sh"
        script.write_text("#!/bin/bash\n", encoding="utf-8")
        monkeypatch.delenv("RAFT_INSTALL_URL", raising=False)
        monkeypatch.setattr(update_mod, "install_identity", lambda: None)
        shell = MagicMock()
        upd = SelfUpdate(self.stack)
        upd.sh = shell
        upd.run()
        args = shell.run.call_args.args[0]
        assert args[4] == DEFAULT_INSTALL_URL
        assert "bash" == args[0]


class TestInstallIdentity(ServicesTestCase):
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

    def test_identity_from_direct_url_via_which(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"url":"git","vcs_info":{"commit_id":"abc"}}\n')
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: str(raft_bin))
        assert install_identity() == '{"url":"git","vcs_info":{"commit_id":"abc"}}'

    def test_identity_falls_back_to_metadata(self, monkeypatch) -> None:
        root = self._fake_tool_env(metadata="Name: raft\nVersion: 0.1.0\n")
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: str(raft_bin))
        assert "Version: 0.1.0" in (install_identity() or "")

    def test_identity_via_uv_tool_dir_when_which_misses(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"commit":"xyz"}')
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: None)
        monkeypatch.setenv("UV_TOOL_DIR", str(root.parent))
        assert install_identity() == '{"commit":"xyz"}'

    def test_identity_none_when_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: None)
        monkeypatch.setenv("UV_TOOL_DIR", str(self.tmp_path / "empty-tools"))
        monkeypatch.setattr(update_mod.Path, "home", lambda: self.tmp_path / "nohome")
        assert install_identity() is None

    def test_identity_none_when_tool_env_has_no_dist_info(self, monkeypatch) -> None:
        root = self.tmp_path / "tools" / "raft"
        (root / "bin").mkdir(parents=True)
        raft_bin = root / "bin" / "raft"
        raft_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: str(raft_bin))
        assert install_identity() is None

    def test_identity_none_when_dist_info_empty(self, monkeypatch) -> None:
        root = self._fake_tool_env()
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: str(raft_bin))
        assert install_identity() is None

    def test_identity_falls_through_when_which_not_bin_layout(self, monkeypatch) -> None:
        root = self._fake_tool_env(direct_url='{"commit":"from-env"}')
        odd = self.tmp_path / "elsewhere" / "raft"
        odd.parent.mkdir(parents=True)
        odd.write_text("x", encoding="utf-8")
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: str(odd))
        monkeypatch.setenv("UV_TOOL_DIR", str(root.parent))
        assert install_identity() == '{"commit":"from-env"}'

    def test_identity_default_home_tool_dir(self, monkeypatch) -> None:
        home = self.tmp_path / "home"
        root = home / ".local" / "share" / "uv" / "tools" / "raft"
        dist = root / "lib" / "python3.12" / "site-packages" / "raft-0.1.0.dist-info"
        dist.mkdir(parents=True)
        (dist / "direct_url.json").write_text('{"ok":1}', encoding="utf-8")
        monkeypatch.setattr(update_mod.shutil, "which", lambda _name: None)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.setattr(update_mod.Path, "home", lambda: home)
        assert install_identity() == '{"ok":1}'
