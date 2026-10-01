"""AppDependsGraph unit coverage."""

from __future__ import annotations

import pytest

from raft.models.depends import AppDependsGraph, DependsOnError


class TestAppDependsGraph:
    def test_empty_deps(self) -> None:
        g = AppDependsGraph({"a": ()})
        assert g.before("a") == ()
        assert g.wake_chain("a") == ("a",)

    def test_direct_dep(self) -> None:
        g = AppDependsGraph({"a": ("b",), "b": ()})
        assert g.before("a") == ("b",)
        assert g.wake_chain("a") == ("b", "a")

    def test_transitive_chain(self) -> None:
        g = AppDependsGraph({"a": ("b",), "b": ("c",), "c": ()})
        assert g.before("a") == ("c", "b")
        assert g.wake_chain("a") == ("c", "b", "a")

    def test_diamond_preserves_declaration_order(self) -> None:
        g = AppDependsGraph(
            {
                "a": ("b", "c"),
                "b": ("d",),
                "c": ("d",),
                "d": (),
            }
        )
        assert g.before("a") == ("d", "b", "c")

    def test_unknown_root(self) -> None:
        g = AppDependsGraph({"a": ()})
        with pytest.raises(DependsOnError, match="unknown app"):
            g.before("missing")

    def test_missing_dep(self) -> None:
        g = AppDependsGraph({"a": ("redis",)})
        with pytest.raises(DependsOnError, match="unknown app"):
            g.before("a")

    def test_cycle(self) -> None:
        g = AppDependsGraph({"a": ("b",), "b": ("a",)})
        with pytest.raises(DependsOnError, match="cycle"):
            g.before("a")

    def test_self_cycle(self) -> None:
        g = AppDependsGraph({"a": ("a",)})
        with pytest.raises(DependsOnError, match="cycle"):
            g.wake_chain("a")
