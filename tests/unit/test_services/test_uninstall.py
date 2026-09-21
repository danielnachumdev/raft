"""Full-machine uninstall (`raft uninstall --yes`)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.errors import OperatorError
from raft.services.uninstall import Uninstall

from .base import ServicesTestCase


class TestUninstall(ServicesTestCase):
    def _mgr(self) -> Uninstall:
        mgr = Uninstall(self.stack)
        mgr.sh = MagicMock()
        return mgr

    def test_refuses_without_yes(self, capsys) -> None:
        mgr = self._mgr()
        with pytest.raises(OperatorError, match="uninstall --yes"):
            mgr.run(yes=False)
        out = capsys.readouterr().out
        assert "permanently removes" in out
        assert str(self.stack.root) in out
        assert "leaves `uv` installed" in out
        mgr.sh.compose.assert_not_called()

    def test_preview_with_uv_flag(self, capsys) -> None:
        mgr = self._mgr()
        with pytest.raises(OperatorError, match="--uv"):
            mgr.run(yes=False, uv=True)
        out = capsys.readouterr().out
        assert "requested via --uv" in out

    def test_full_cleanup(self, capsys, monkeypatch) -> None:
        home = self.stack.root
        (home / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        (home / "state" / "apps").mkdir(parents=True, exist_ok=True)
        (home / "state" / "apps" / "web.yaml").write_text("x\n", encoding="utf-8")

        ssh = Path(str(self.tmp_path) + "-ssh")
        keys = ssh / "raft"
        keys.mkdir(parents=True)
        (keys / "web_ed25519").write_text("priv\n", encoding="utf-8")
        config = ssh / "config"
        config.write_text(
            "Host keep\n  HostName z\n"
            "# BEGIN raft:web\nHost github.com-raft-web\n  HostName github.com\n"
            "# END raft:web\n"
            "Host other\n  HostName y\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("RAFT_SSH_DIR", str(ssh))

        checkout = Path(str(self.tmp_path) + "-checkout")
        checkout.mkdir()
        (checkout / "pyproject.toml").write_text('name = "raft"\n', encoding="utf-8")
        monkeypatch.setenv("RAFT_HOME", str(checkout))

        mgr = self._mgr()
        mgr.sh.compose.return_value = MagicMock(returncode=0)
        mgr.sh.docker.side_effect = [
            MagicMock(
                returncode=0,
                stdout="raft-web:latest\nnginx:alpine\nraft-other:dev\n",
            ),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]
        mgr.sh.run.return_value = MagicMock(returncode=0)

        mgr.run(yes=True)

        mgr.sh.compose.assert_called_once_with(
            "down", "--remove-orphans", "--volumes", check=False, capture=False
        )
        rmi_calls = [
            c
            for c in mgr.sh.docker.call_args_list
            if c.args and c.args[0] == "rmi"
        ]
        assert any("raft-web:latest" in c.args for c in rmi_calls)
        assert not any("nginx:alpine" in str(c) for c in rmi_calls)
        mgr.sh.run.assert_called_once_with(
            ["uv", "tool", "uninstall", "raft"], check=False, capture=True
        )

        assert not home.exists()
        assert not keys.exists()
        assert not checkout.exists()
        cfg = config.read_text(encoding="utf-8")
        assert "BEGIN raft:web" not in cfg
        assert "Host keep" in cfg
        assert "Host other" in cfg
        out = capsys.readouterr().out
        assert "OK: raft uninstalled" in out
        assert "Removing uv" not in out

    def test_removes_uv_when_requested(self, capsys, monkeypatch) -> None:
        fake_home = Path(str(self.tmp_path) + "-uvhome")
        bin_dir = fake_home / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        uv_bin = bin_dir / "uv"
        uvx_bin = bin_dir / "uvx"
        uv_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        uvx_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        share = fake_home / ".local" / "share" / "uv"
        share.mkdir(parents=True)
        (share / "tools").mkdir()
        tool_dir = Path(str(self.tmp_path) + "-uvtool")
        tool_dir.mkdir()
        monkeypatch.setenv("UV_TOOL_DIR", str(tool_dir))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        monkeypatch.setattr(
            "raft.services.uninstall.shutil.which",
            lambda _name: str(uv_bin),
        )
        monkeypatch.setenv("RAFT_SSH_DIR", str(Path(str(self.tmp_path) + "-ssh-uv")))
        monkeypatch.setenv("RAFT_HOME", str(self.tmp_path / "no-co"))

        mgr = self._mgr()
        mgr.sh.docker.return_value = MagicMock(returncode=0, stdout="")
        mgr.sh.run.return_value = MagicMock(returncode=0)
        compose = self.stack.root / "compose.yaml"
        if compose.is_file():
            compose.unlink()
        mgr.run(yes=True, uv=True)

        assert not uv_bin.exists()
        assert not uvx_bin.exists()
        assert not share.exists()
        assert not tool_dir.exists()
        out = capsys.readouterr().out
        assert "Removing uv" in out
        assert "OK: raft uninstalled" in out

    def test_remove_uv_handles_resolve_error_and_no_which(
        self, monkeypatch, capsys
    ) -> None:
        fake_home = Path(str(self.tmp_path) + "-uvhome2")
        bin_dir = fake_home / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        uv_bin = bin_dir / "uv"
        uv_bin.write_text("x\n", encoding="utf-8")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        monkeypatch.setattr("raft.services.uninstall.shutil.which", lambda _n: None)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.setenv("RAFT_SSH_DIR", str(Path(str(self.tmp_path) + "-ssh-uv2")))
        monkeypatch.setenv("RAFT_HOME", str(self.tmp_path / "no-co2"))

        real_resolve = Path.resolve

        def boom(self, *args, **kwargs):
            if self == uv_bin or self.name == "uv":
                raise OSError("resolve failed")
            return real_resolve(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", boom)
        mgr = self._mgr()
        mgr.sh.docker.return_value = MagicMock(returncode=0, stdout="")
        mgr.sh.run.return_value = MagicMock(returncode=0)
        compose = self.stack.root / "compose.yaml"
        if compose.is_file():
            compose.unlink()
        mgr.run(yes=True, uv=True)
        assert not uv_bin.exists()
        assert "OK: raft uninstalled" in capsys.readouterr().out

    def test_skips_missing_compose_and_tolerates_failures(self, capsys, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_SSH_DIR", str(self.tmp_path / "nossh"))
        monkeypatch.setenv("RAFT_HOME", str(self.tmp_path / "not-a-checkout"))
        (self.tmp_path / "not-a-checkout").mkdir()
        mgr = self._mgr()
        mgr.sh.compose.side_effect = RuntimeError("no docker")
        mgr.sh.docker.side_effect = RuntimeError("no docker")
        mgr.sh.run.side_effect = RuntimeError("no uv")
        # home still exists from fixture; ensure compose.yaml absent for skip path
        compose = self.stack.root / "compose.yaml"
        if compose.is_file():
            compose.unlink()
        mgr.run(yes=True)
        out = capsys.readouterr().out
        assert "skipping stack tear-down" in out or "OK: raft uninstalled" in out
        assert "OK: raft uninstalled" in out
        assert not self.stack.root.exists()

    def test_looks_like_raft_checkout(self) -> None:
        path = self.tmp_path / "x"
        path.mkdir()
        assert Uninstall._looks_like_raft_checkout(path) is False
        (path / "pyproject.toml").write_text('name = "other"\n', encoding="utf-8")
        assert Uninstall._looks_like_raft_checkout(path) is False
        (path / "pyproject.toml").write_text('name = "raft"\n', encoding="utf-8")
        assert Uninstall._looks_like_raft_checkout(path) is True
        with patch.object(Path, "read_text", side_effect=OSError("boom")):
            assert Uninstall._looks_like_raft_checkout(path) is False

    def test_preview_lists_checkout_and_edge_paths(self, capsys, monkeypatch) -> None:
        checkout = Path(str(self.tmp_path) + "-preview-co")
        checkout.mkdir()
        (checkout / "pyproject.toml").write_text('name = "raft"\n', encoding="utf-8")
        monkeypatch.setenv("RAFT_HOME", str(checkout))
        monkeypatch.setenv("RAFT_SSH_DIR", str(Path(str(self.tmp_path) + "-preview-ssh")))
        mgr = self._mgr()
        with pytest.raises(OperatorError, match="uninstall --yes"):
            mgr.run(yes=False)
        out = capsys.readouterr().out
        assert str(checkout) in out

    def test_compose_down_warns_and_image_list_nonzero(self, capsys, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_SSH_DIR", str(Path(str(self.tmp_path) + "-ssh2")))
        monkeypatch.setenv("RAFT_HOME", str(self.tmp_path / "nope"))
        (self.stack.root / "compose.yaml").write_text("name: raft\n", encoding="utf-8")
        mgr = self._mgr()
        mgr.sh.compose.side_effect = RuntimeError("compose boom")
        mgr.sh.docker.return_value = MagicMock(returncode=1, stdout="")
        mgr.sh.run.return_value = MagicMock(returncode=0)
        mgr.run(yes=True)
        out = capsys.readouterr().out
        assert "compose down skipped" in out
        assert "OK: raft uninstalled" in out

    def test_remove_tree_missing_and_config_without_blocks(self, monkeypatch, capsys) -> None:
        ssh = Path(str(self.tmp_path) + "-ssh3")
        ssh.mkdir()
        config = ssh / "config"
        config.write_text("Host only\n  HostName z\n", encoding="utf-8")
        monkeypatch.setenv("RAFT_SSH_DIR", str(ssh))
        monkeypatch.setenv("RAFT_HOME", str(self.tmp_path / "missing-co"))
        mgr = self._mgr()
        mgr.sh.docker.return_value = MagicMock(
            returncode=0, stdout="raft-x:<none>\n"
        )
        mgr.sh.run.return_value = MagicMock(returncode=0)
        compose = self.stack.root / "compose.yaml"
        if compose.is_file():
            compose.unlink()
        # Remove home first via helper coverage for missing path message
        Uninstall._remove_tree(self.tmp_path / "ghost", label="ghost")
        mgr.run(yes=True)
        out = capsys.readouterr().out
        assert "no ghost at" in out
        assert "OK: raft uninstalled" in out
        assert "BEGIN raft" not in config.read_text(encoding="utf-8")
        # no scrub message when config unchanged
        assert "Scrubbing" not in out
