"""Compose project leftover cleanup after raft down."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.adapters.docker.project_cleanup import ComposeProjectCleanup

from ..base import AdapterTestCase


class TestComposeProjectCleanup:
    def test_remove_labeled_force_rms_each_id(self) -> None:
        sh = MagicMock()
        sh.docker.side_effect = [
            AdapterTestCase.ok("abc\ndef\n"),
            AdapterTestCase.ok("/raft-raft-gate-1\n"),
            AdapterTestCase.ok(""),
            AdapterTestCase.ok("/orphan\n"),
            AdapterTestCase.ok(""),
        ]
        removed = ComposeProjectCleanup(sh).remove_labeled()
        assert removed == ["raft-raft-gate-1", "orphan"]
        assert sh.docker.call_args_list[2].args[:2] == ("rm", "-f")

    def test_remove_labeled_noop_when_ps_empty(self) -> None:
        sh = MagicMock()
        sh.docker.return_value = AdapterTestCase.ok("")
        assert ComposeProjectCleanup(sh).remove_labeled() == []

    def test_remove_labeled_noop_when_ps_fails(self) -> None:
        sh = MagicMock()
        sh.docker.return_value = AdapterTestCase.ok("", returncode=1, stderr="daemon down")
        assert ComposeProjectCleanup(sh).remove_labeled() == []

    def test_remove_labeled_falls_back_to_id_prefix(self) -> None:
        sh = MagicMock()
        sh.docker.side_effect = [
            AdapterTestCase.ok("abcdef0123456789\n"),
            AdapterTestCase.ok(""),  # inspect name empty
            AdapterTestCase.ok(""),  # rm -f
        ]
        assert ComposeProjectCleanup(sh).remove_labeled() == ["abcdef012345"]

    def test_network_holders_splits_names(self) -> None:
        sh = MagicMock()
        sh.docker.return_value = AdapterTestCase.ok("raft-gate c1\n")
        assert ComposeProjectCleanup(sh).network_holders("raft_default") == [
            "raft-gate",
            "c1",
        ]

    def test_network_holders_empty_on_inspect_failure(self) -> None:
        sh = MagicMock()
        sh.docker.return_value = AdapterTestCase.ok("", returncode=1, stderr="no such")
        assert ComposeProjectCleanup(sh).network_holders("raft_default") == []
