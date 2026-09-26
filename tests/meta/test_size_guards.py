"""Meta guards: file & function-body size limits (see ``scan`` module docstring)."""

from __future__ import annotations

import pytest

from tests.meta.scan import (
    MAX_BODY_LINES,
    MAX_FILE_LINES,
    SRC_RAFT,
    TESTS_ROOT,
    CodebaseScanner,
)

pytestmark = pytest.mark.meta


class TestSizeGuards:
    """Four codebase-as-artifact checks; failures list every offender."""

    def setup_method(self) -> None:
        self.scan = CodebaseScanner()

    def test_src_raft_files_under_300_lines(self) -> None:
        bad = self.scan.file_offenders(SRC_RAFT)
        assert not bad, self._fmt_files("src/raft", MAX_FILE_LINES, bad)

    def test_tests_files_under_300_lines(self) -> None:
        bad = self.scan.file_offenders(TESTS_ROOT)
        assert not bad, self._fmt_files("tests", MAX_FILE_LINES, bad)

    def test_src_raft_function_bodies_at_most_20_lines(self) -> None:
        bad = self.scan.body_offenders(SRC_RAFT)
        assert not bad, self._fmt_bodies("src/raft", MAX_BODY_LINES, bad)

    def test_tests_function_bodies_at_most_20_lines(self) -> None:
        bad = self.scan.body_offenders(TESTS_ROOT)
        assert not bad, self._fmt_bodies("tests", MAX_BODY_LINES, bad)

    def _fmt_files(self, label: str, limit: int, bad: list) -> str:
        lines = [f"{label}: Python files must have < {limit} lines:"]
        lines += [f"  {path}: {n}" for path, n in bad]
        return "\n".join(lines)

    def _fmt_bodies(self, label: str, limit: int, bad: list) -> str:
        lines = [f"{label}: function/method bodies must be ≤ {limit} lines:"]
        lines += [f"  {qual}: {n}" for qual, n in bad]
        return "\n".join(lines)
