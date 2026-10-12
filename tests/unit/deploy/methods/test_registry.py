"""DeploymentMethodRegistry: register, get, catalog, unknown type CTA."""

from __future__ import annotations

import pytest

from raft.errors.cta import OperatorError
from raft.deploy.methods.catalogs import DeploymentMethodCatalogs
from raft.deploy.methods.method import DeploymentContext, DeploymentMethod
from raft.deploy.methods.registry import DeploymentMethodRegistry

from tests.unit.base import RaftTestCase


class _FakeMethod(DeploymentMethod):
    def __init__(self, type_id: str) -> None:
        self._type_id = type_id

    @property
    def type_id(self) -> str:
        return self._type_id

    def deploy_when_up(self, ctx: DeploymentContext) -> None:
        return None

    def deploy_when_down(self, ctx: DeploymentContext) -> None:
        return None


class TestDeploymentMethodRegistry(RaftTestCase):
    def test_default_catalog_has_seamless_and_inplace(self) -> None:
        ids = [row["type_id"] for row in DeploymentMethodCatalogs.default().catalog()]
        assert ids == ["seamless", "inplace"]

    def test_get_returns_registered(self) -> None:
        registry = DeploymentMethodRegistry()
        strategy = _FakeMethod("seamless")
        registry.register(strategy)
        assert registry.get("seamless") is strategy

    def test_unknown_is_operator_error(self) -> None:
        registry = DeploymentMethodRegistry()
        registry.register(_FakeMethod("seamless"))
        with pytest.raises(OperatorError) as caught:
            registry.get("inplace")
        message = str(caught.value)
        assert "unknown deployment method 'inplace'" in message
        assert "Fix:" in message

    def test_duplicate_register_rejected(self) -> None:
        registry = DeploymentMethodRegistry()
        registry.register(_FakeMethod("seamless"))
        with pytest.raises(ValueError, match="duplicate"):
            registry.register(_FakeMethod("seamless"))

    def test_unknown_empty_catalog(self) -> None:
        with pytest.raises(OperatorError, match=r"\(none\)"):
            DeploymentMethodRegistry().get("seamless")
