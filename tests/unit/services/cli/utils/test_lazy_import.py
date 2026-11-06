"""LazyImportManager resolves targets on use, not at construction."""

import importlib

from raft.services.cli.utils.lazy_import import LazyImportManager


class _Sample:
    def __init__(self, value: str) -> None:
        self.value = value

    def ping(self) -> str:
        return self.value


def test_get_and_call_import_on_use(monkeypatch) -> None:
    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package=None):
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    manager = LazyImportManager(
        {"Sample": "tests.unit.services.cli.utils.test_lazy_import:_Sample"}
    )
    assert seen == []
    assert manager.get("Sample") is _Sample
    assert manager.call("Sample", "ok").ping() == "ok"
    assert seen == ["tests.unit.services.cli.utils.test_lazy_import"]


def test_command_defers_import_until_attribute_use(monkeypatch) -> None:
    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package=None):
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    manager = LazyImportManager(
        {},
        commands={
            "sample": (
                "tests.unit.services.cli.utils.test_lazy_import:_Sample",
                "sample group",
            )
        },
    )
    group = manager.command("sample", "ok")
    assert seen == []
    assert group.__doc__ == "sample group"
    assert group.ping() == "ok"
    assert seen == ["tests.unit.services.cli.utils.test_lazy_import"]


def test_bind_does_not_import_until_called(monkeypatch) -> None:
    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package=None):
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    manager = LazyImportManager(
        {"Sample": "tests.unit.services.cli.utils.test_lazy_import:_Sample"}
    )
    bound = manager.bind("Sample")
    assert seen == []
    assert bound("ok").ping() == "ok"
    assert seen == ["tests.unit.services.cli.utils.test_lazy_import"]


def test_bind_invokes_call_looked_up_at_call_time(monkeypatch) -> None:
    seen: list[str] = []
    real = importlib.import_module

    def spy(name: str, package=None):
        seen.append(name)
        return real(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    manager = LazyImportManager(
        {"Sample": "tests.unit.services.cli.utils.test_lazy_import:_Sample"}
    )
    bound = manager.bind("Sample")

    def fake_call(name: str, *args, **kwargs):
        return ("patched", name, args, kwargs)

    monkeypatch.setattr(manager, "call", fake_call)
    assert bound("ok", flag=True) == ("patched", "Sample", ("ok",), {"flag": True})
    assert seen == []


def test_callable_command_imports_when_built() -> None:
    manager = LazyImportManager(
        {},
        commands={
            "sample": (
                "tests.unit.services.cli.utils.test_lazy_import:_Sample",
                "sample group",
            )
        },
        callable_commands=frozenset({"sample"}),
    )
    built = manager.command("sample", "ok")
    assert isinstance(built, _Sample)
    assert built.ping() == "ok"
