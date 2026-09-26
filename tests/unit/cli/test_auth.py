"""CLI auth subcommand coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft import cli

from ..base import make_git_app, make_stack, write_demo_inventory
from .base import CliTestCase


class TestCliAuth(CliTestCase):
    @pytest.fixture(autouse=True)
    def _cli_auth_setup(self, _raft_base) -> None:
        write_demo_inventory(self.tmp_path)
        self.stack = make_stack(
            self.tmp_path,
            (make_git_app("svc"),),
        )
        self.auth = MagicMock()
        self.auth.list_services.return_value = ["svc"]
        self.auth.key_path.return_value = Path("/tmp/key")
        self.auth.show_pubkey.return_value = "ssh-ed25519 AAAA"

    def auth_main(self, argv: list[str]) -> int:
        with self.patched_deps(Orchestrator=MagicMock(), GitAuthManager=self.auth):
            return cli.main(argv)

    def test_auth_setup_list_show_test_remove(self, capsys) -> None:
        self._test_auth_setup_list_show_test_remove_p1()
        self._test_auth_setup_list_show_test_remove_p2()

    def _test_auth_setup_list_show_test_remove_p1(self) -> None:
        assert self.auth_main(["auth", "setup", "svc", "--force"]) == 0
        self.auth.setup.assert_called_once_with("svc", force=True, repo=None)
        assert self.auth_main(["auth", "list"]) == 0
        assert self.auth_main(["auth", "show", "svc"]) == 0
        self.auth.show.assert_called_once_with("svc", repo=None)
        assert (
            self.auth_main(
                [
                    "auth",
                    "setup",
                    "newsvc",
                    "--repo",
                    "git@github.com:org/new.git",
                ]
            )
            == 0
        )

    def _test_auth_setup_list_show_test_remove_p2(self) -> None:
        self.auth.setup.assert_called_with("newsvc", force=False, repo="git@github.com:org/new.git")
        assert self.auth_main(["auth", "test", "svc"]) == 0
        self.auth.test.assert_called_with("svc", repo=None)
        assert self.auth_main(["auth", "remove", "svc", "--keep-key"]) == 0
        self.auth.remove.assert_called_once_with("svc", remove_files=False)

    def test_auth_requires_service(self) -> None:
        with self.patched_deps(Orchestrator=MagicMock(), GitAuthManager=self.auth):
            with pytest.raises(RuntimeError, match="auth setup requires SERVICE"):
                cli.main(["auth", "setup"])
            with pytest.raises(RuntimeError, match="auth show requires SERVICE"):
                cli.main(["auth", "show"])
            with pytest.raises(RuntimeError, match="auth test requires SERVICE"):
                cli.main(["auth", "test"])
            with pytest.raises(RuntimeError, match="auth remove requires SERVICE"):
                cli.main(["auth", "remove"])

    def test_auth_list_empty(self, capsys) -> None:
        self.auth.list_services.return_value = []
        assert self.auth_main(["auth", "list"]) == 0
        assert "No local raft deploy keys" in capsys.readouterr().out

    def test_auth_list_marks_unknown_inventory(self, capsys) -> None:
        self.auth.list_services.return_value = ["ghost"]
        self.auth.key_path.return_value = Path("/tmp/ghost")
        assert self.auth_main(["auth", "list"]) == 0
        assert "not applied" in capsys.readouterr().out
