"""E2E: fresh ``uv tool install`` from git, then routine CLI smoke."""

from __future__ import annotations

import pytest

from tests.e2e.shared.fresh_install import FreshInstallGate, FreshInstallImage

pytestmark = pytest.mark.e2e


class TestFreshInstall:
    """Operator-shaped install path (packaged share must be present)."""

    def test_fresh_git_install_cli_smoke(self) -> None:
        if not FreshInstallGate().should_run():
            pytest.skip("fresh-install image runs once per CI matrix (Py 3.13)")
        FreshInstallImage().run()
