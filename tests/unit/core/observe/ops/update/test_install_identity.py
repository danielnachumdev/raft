"""InstallIdentity resolution under uv tool / which layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from raft.core.observe.ops.update import identity as identity_mod
from raft.core.observe.ops.update import InstallIdentity

from tests.unit.domain_case import DomainTestCase


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
        root = self._fake_tool_env(
            direct_url='{"url":"git","vcs_info":{"commit_id":"abc"}}\n'
        )
        raft_bin = root / "bin" / "raft"
        monkeypatch.setattr(identity_mod.shutil, "which", lambda _name: str(raft_bin))
        assert InstallIdentity().read() == (
            '{"url":"git","vcs_info":{"commit_id":"abc"}}'
        )

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
