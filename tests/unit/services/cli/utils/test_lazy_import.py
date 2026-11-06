"""One LazyImport loads its target on first call and not before."""

import importlib

from raft.services.cli.utils.lazy_import import LazyImport


class _Sample:
    def __init__(self, value: str) -> None:
        self.value = value

    def ping(self) -> str:
        return self.value


def test_call_imports_once_and_invokes_target(monkeypatch) -> None:
    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package=None):
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    sample = LazyImport("tests.unit.services.cli.utils.test_lazy_import", "_Sample")
    assert seen == []
    first = sample("ok")
    assert isinstance(first, _Sample)
    assert first.ping() == "ok"
    second = sample("again")
    assert second.ping() == "again"
    assert seen == ["tests.unit.services.cli.utils.test_lazy_import"]
