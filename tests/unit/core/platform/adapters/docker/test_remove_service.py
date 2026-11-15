"""Compose ``rm -sf`` coverage for ``DockerStack.remove_service``."""

from unittest.mock import patch

import pytest

from raft.core.core.errors.cta import OperatorError

from tests.unit.core.platform.adapters.docker.base import DockerTestCase


class TestDockerRemoveService(DockerTestCase):
    def test_remove_service_compose_rm(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.remove_service("app")
        self.shell.compose.assert_any_call(
            "rm", "-sf", "app", capture=False, check=False
        )

    def test_remove_service_enrich_failure(self) -> None:
        with patch.object(
            self.docker,
            "enrich_compose_failure",
            side_effect=lambda exc, **kw: OperatorError(
                f"{exc}\n\n--- app ---\nbad",
                has_fix=True,
            ),
        ):
            self.shell.compose.return_value = self.ok(returncode=1)
            with pytest.raises(RuntimeError, match="--- app ---"):
                self.docker.remove_service("app")
