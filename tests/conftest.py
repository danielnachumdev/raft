"""Root pytest hooks — markers only (no autouse isolation here)."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: fast mocked unit tests")
    config.addinivalue_line(
        "markers", "integration: app.yaml → render artifact checks (no Docker)"
    )
    config.addinivalue_line(
        "markers", "e2e: Docker Compose runtime checks (skipped without Docker)"
    )
