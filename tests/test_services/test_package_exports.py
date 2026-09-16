"""Package export surface for ``raft.services``."""

from __future__ import annotations

import pytest

import raft.services as services


def test_lazy_exports_resolve() -> None:
    assert services.Orchestrator is not None
    assert services.Doctor is not None
    assert "Orchestrator" in dir(services)


def test_unknown_export_raises() -> None:
    with pytest.raises(AttributeError, match="has no attribute"):
        _ = services.DefinitelyNotAnExport  # type: ignore[attr-defined]
