"""InstallIdentity prefers RAFT_HOST_HOME for dashboard host-CLI checks."""

from __future__ import annotations

from pathlib import Path

from raft.core.observe.ops.update import InstallIdentity
from raft.core.observe.ops.update import identity as id_mod


class TestInstallIdentityHostHome:
    def test_reads_dist_info_under_raft_host_home(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(id_mod.shutil, "which", lambda name: None)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        home = tmp_path / "demo-home"
        root = home / ".local" / "share" / "uv" / "tools" / "raft"
        dist = root / "lib" / "python3.12" / "site-packages" / "raft-1.0.0.dist-info"
        dist.mkdir(parents=True)
        (dist / "METADATA").write_text("Name: raft\nVersion: 1.0.0\n", encoding="utf-8")
        monkeypatch.setenv("RAFT_HOST_HOME", str(home))
        identity = InstallIdentity()
        assert identity.dist_info_dir() == dist
        assert "Version: 1.0.0" in (identity.read() or "")
