"""CatalogField options/default."""

from raft.core.observe.notify.catalog_field import CatalogField
from tests.unit.base import RaftTestCase


class TestCatalogFieldOptions(RaftTestCase):
    def test_options_and_default(self) -> None:
        row = CatalogField.define(
            "op",
            label="Op",
            kind="select",
            options=[{"value": "gt", "label": ">"}],
            default="gt",
        )
        assert row["options"][0]["value"] == "gt"
        assert row["default"] == "gt"
