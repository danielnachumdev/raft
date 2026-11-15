"""``docker logs --tail`` slice vs shipper cursor."""

from raft.core.platform.adapters.docker.logs_tail_coverage import LogsTailCoverage


class TestLogsTailCoverage:
    def test_reaches_when_oldest_line_at_or_before_cursor(self) -> None:
        text = "2026-10-14T11:00:00Z a\n2026-10-14T12:00:00Z b\n"
        assert LogsTailCoverage.reaches(text, "2026-10-14T11:00:00Z")
        assert LogsTailCoverage.reaches(text, "2026-10-14T11:30:00Z")

    def test_not_reached_when_oldest_line_after_cursor(self) -> None:
        text = "2026-10-14T12:00:00Z b\n"
        assert not LogsTailCoverage.reaches(text, "2026-10-14T11:59:59Z")

    def test_trimmed_fraction_compares_numerically(self) -> None:
        # Docker trims trailing zeros: ".5" is later than ".123456789".
        text = "2026-10-14T12:00:00.5Z b\n"
        assert not LogsTailCoverage.reaches(text, "2026-10-14T12:00:00.123456789Z")
        assert LogsTailCoverage.reaches(text, "2026-10-14T12:00:00.500000001Z")

    def test_skips_leading_blank_lines(self) -> None:
        assert LogsTailCoverage.reaches("\n  \n2026-10-14T11:00:00Z a", "2026-10-14T11:00:00Z")

    def test_unparseable_inputs_do_not_reach(self) -> None:
        assert not LogsTailCoverage.reaches("", "2026-10-14T11:00:00Z")
        assert not LogsTailCoverage.reaches("no-stamp line\n", "2026-10-14T11:00:00Z")
        assert not LogsTailCoverage.reaches("2026-10-14T11:00:00Z a\n", "garbage")

    def test_sortable_pads_and_caps_fraction(self) -> None:
        assert LogsTailCoverage.sortable("2026-10-14T11:00:00Z") == (
            "2026-10-14T11:00:00.000000000Z"
        )
        assert LogsTailCoverage.sortable("2026-10-14T11:00:00.1234567891Z") == (
            "2026-10-14T11:00:00.123456789Z"
        )
        assert LogsTailCoverage.sortable("nope") is None
