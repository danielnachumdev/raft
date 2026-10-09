"""AppDependsGraph unit coverage."""

from __future__ import annotations

import pytest

from raft.models.depends import AppDependsGraph, DependsOnError, DependsOnSpec


class TestAppDependsGraph:
    def test_empty_deps(self) -> None:
        g = AppDependsGraph({"a": ()})
        assert g.before("a") == ()
        assert g.wake_chain("a") == ("a",)
        assert g.costop_before("a") == ()

    def test_direct_dep(self) -> None:
        g = AppDependsGraph({"a": ("b",), "b": ()})
        assert g.before("a") == ("b",)
        assert g.wake_chain("a") == ("b", "a")
        assert g.costop_before("a") == ("b",)

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

    def test_costop_filters_scale_with_parent_false(self) -> None:
        g = AppDependsGraph(
            {
                "front": (
                    DependsOnSpec("api", scale_with_parent=True),
                    DependsOnSpec("sidecar", scale_with_parent=False),
                ),
                "api": (DependsOnSpec("db", scale_with_parent=True),),
                "sidecar": (),
                "db": (),
            }
        )
        assert g.costop_before("front") == ("db", "api")
        assert g.before("front") == ("db", "api", "sidecar")
        assert g.wake_chain("front") == ("db", "api", "sidecar", "front")

    def test_costop_stops_at_false_edge(self) -> None:
        g = AppDependsGraph(
            {
                "front": (DependsOnSpec("api", scale_with_parent=True),),
                "api": (DependsOnSpec("db", scale_with_parent=False),),
                "db": (),
            }
        )
        assert g.costop_before("front") == ("api",)
        assert g.before("front") == ("db", "api")

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
        with pytest.raises(DependsOnError, match="cycle"):
            g.assert_acyclic()

    def test_self_cycle(self) -> None:
        g = AppDependsGraph({"a": ("a",)})
        with pytest.raises(DependsOnError, match="cycle"):
            g.wake_chain("a")
        with pytest.raises(DependsOnError, match="cycle"):
            g.assert_acyclic()

    def test_longer_cycle_assert_acyclic(self) -> None:
        g = AppDependsGraph(
            {"front": ("api",), "api": ("db",), "db": ("front",)}
        )
        with pytest.raises(DependsOnError, match="cycle"):
            g.assert_acyclic()

    def test_assert_acyclic_ok(self) -> None:
        g = AppDependsGraph(
            {
                "front": (
                    DependsOnSpec("api", scale_with_parent=True),
                    DependsOnSpec("sidecar", scale_with_parent=False),
                ),
                "api": (DependsOnSpec("db", scale_with_parent=True),),
                "sidecar": (),
                "db": (),
            }
        )
        g.assert_acyclic()

    def test_object_form_cycle_assert_acyclic(self) -> None:
        g = AppDependsGraph(
            {
                "a": (DependsOnSpec("b", scale_with_parent=False),),
                "b": (DependsOnSpec("a", scale_with_parent=True),),
            }
        )
        with pytest.raises(DependsOnError, match="cycle"):
            g.assert_acyclic()
