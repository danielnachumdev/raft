"""SemverParts parse / compare for release tags."""

from raft.core.observe.ops.update import SemverParts


class TestSemverParts:
    def test_parse_strips_v_prefix(self) -> None:
        assert SemverParts.parse("v0.11.0") == (0, 11, 0)
        assert SemverParts.parse("0.11.0") == (0, 11, 0)

    def test_parse_rejects_non_version(self) -> None:
        assert SemverParts.parse("main") is None
        assert SemverParts.parse("") is None

    def test_compare_orders_versions(self) -> None:
        assert SemverParts.compare("0.10.0", "0.11.0") == -1
        assert SemverParts.compare("0.11.0", "v0.11.0") == 0
        assert SemverParts.compare("0.12.0", "0.11.0") == 1

    def test_compare_pads_shorter(self) -> None:
        assert SemverParts.compare("1.2", "1.2.0") == 0

    def test_compare_none_when_unparsable(self) -> None:
        assert SemverParts.compare("main", "0.1.0") is None

    def test_parse_rejects_letter_prefix(self) -> None:
        assert SemverParts.parse("x1.2.3") is None
        assert SemverParts.parse("v") is None

    def test_parse_stops_at_non_numeric_segment(self) -> None:
        assert SemverParts.parse("1.2.x") == (1, 2)
        assert SemverParts.parse("1..2") == (1,)
