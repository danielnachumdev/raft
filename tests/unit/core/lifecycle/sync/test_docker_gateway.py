"""DockerGateway skip-when-present pull decision."""

from __future__ import annotations

from unittest.mock import MagicMock

from raft.core.lifecycle.sync.docker_gateway import DockerGateway


class TestDockerGatewayPull:
    def test_pull_skips_when_image_present(self) -> None:
        shell = MagicMock()
        shell.docker.return_value = MagicMock(returncode=0, stdout="sha256:local\n")
        result = DockerGateway(shell).pull("ghcr.io/example/demo-api:abc123")
        assert result.returncode == 0
        shell.docker.assert_called_once_with(
            "image",
            "inspect",
            "-f",
            "{{.Id}}",
            "ghcr.io/example/demo-api:abc123",
            check=False,
            capture=True,
        )

    def test_pull_runs_when_image_missing(self) -> None:
        shell = MagicMock()
        shell.docker.side_effect = [
            MagicMock(returncode=1, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="Pulled\n", stderr=""),
        ]
        gateway = DockerGateway(shell)
        result = gateway.pull("ghcr.io/example/demo-api:abc123")
        assert result.returncode == 0
        assert shell.docker.call_args_list[1].args[:2] == (
            "pull",
            "ghcr.io/example/demo-api:abc123",
        )
