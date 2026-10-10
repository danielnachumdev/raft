"""DockerPrune + reclaim parsing (no live Engine calls)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.adapters.docker.prune import DockerPrune, DockerPruneReclaim
from raft.errors.cta import OperatorError


class TestDockerPruneReclaim:
    def test_parses_mib_and_gib(self) -> None:
        text = "Deleted Images:\nuntagged: x\n\nTotal reclaimed space: 1.5MiB\n"
        assert DockerPruneReclaim.parse(text) == int(1.5 * 1024**2)
        assert DockerPruneReclaim.parse("Total reclaimed space: 2GB") == 2_000_000_000

    def test_missing_or_bad_line_is_zero(self) -> None:
        assert DockerPruneReclaim.parse("") == 0
        assert DockerPruneReclaim.parse("Deleted Images:\n") == 0
        assert DockerPruneReclaim.parse("Total reclaimed space: nope") == 0


class TestDockerPrune:
    def test_unused_images_returns_reclaimed(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(
            returncode=0,
            stdout="Total reclaimed space: 64MiB\n",
            stderr="",
        )
        assert DockerPrune(shell).unused_images() == 64 * 1024**2
        shell.docker.assert_called_once()
        assert shell.docker.call_args.args[0:3] == ("image", "prune", "-af")

    def test_unused_images_raises_operator_error(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon",
        )
        with pytest.raises(OperatorError):
            DockerPrune(shell).unused_images()

    def test_build_cache_best_effort_on_failure(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(returncode=1, stdout="", stderr="no")
        assert DockerPrune(shell).build_cache() == 0

    def test_build_cache_parses_reclaim(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(
            returncode=0,
            stdout="Total reclaimed space: 10MiB\n",
            stderr="",
        )
        assert DockerPrune(shell).build_cache() == 10 * 1024**2
