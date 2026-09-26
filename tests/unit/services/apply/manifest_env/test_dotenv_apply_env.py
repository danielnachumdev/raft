"""Dotenv / ApplyEnvSources coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.errors import OperatorError
from raft.services.apply.manifest_env import ApplyEnvSources, DotenvLoader, EnvAssignment

DOTENV_SAMPLE = (
    "# comment\n\nA=one\nA=two\nexport B=bee\n" "C='quoted'\nD=\"dquoted\"\nE= spaced \n"
)


class TestDotenvLoader:
    def test_parses_comments_quotes_and_later_key_wins(self, tmp_path: Path) -> None:
        path = tmp_path / "vars.env"
        path.write_text(DOTENV_SAMPLE, encoding="utf-8")
        assert DotenvLoader(path).load() == {
            "A": "two",
            "B": "bee",
            "C": "quoted",
            "D": "dquoted",
            "E": "spaced",
        }

    def test_missing_file_errors(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.env"

        with pytest.raises(OperatorError, match="cannot read apply --env-file"):
            DotenvLoader(missing).load()

    def test_bad_line_errors(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.env"
        bad.write_text("not-an-assignment\n", encoding="utf-8")

        with pytest.raises(OperatorError, match="invalid line 1"):
            DotenvLoader(bad).load()


class TestEnvAssignment:
    def test_parse_key_equals_value(self) -> None:
        key, value = EnvAssignment.parse("FOO=bar")

        assert (key, value) == ("FOO", "bar")

    def test_parse_export_prefix(self) -> None:
        key, value = EnvAssignment.parse("export FOO=bar")

        assert (key, value) == ("FOO", "bar")

    def test_parse_rejects_non_assignment(self) -> None:
        with pytest.raises(OperatorError, match="invalid --env value"):
            EnvAssignment.parse("nope")

    def test_normalize_none_str_and_sequence(self) -> None:
        none_result = EnvAssignment.normalize_flags(None)
        str_result = EnvAssignment.normalize_flags("A=1")
        seq_result = EnvAssignment.normalize_flags(["A=1", "B=2"])

        assert none_result == []
        assert str_result == ["A=1"]
        assert seq_result == ["A=1", "B=2"]


class TestApplyEnvPrecedence:
    def test_process_then_env_file_then_env_flags(self, tmp_path: Path) -> None:
        """Later sources win: process < --env-file < --env."""
        path = tmp_path / "e.env"
        path.write_text("A=from-file\nB=from-file\nC=from-file\n", encoding="utf-8")
        process_env = {"A": "from-process", "B": "from-process", "D": "proc"}
        flag_overrides = ["B=from-flag", "E=flag"]

        merged = ApplyEnvSources(
            environ=process_env,
            env_file=path,
            overrides=flag_overrides,
        ).build()

        assert merged == {
            "A": "from-file",  # file overrides process
            "B": "from-flag",  # flag overrides file
            "C": "from-file",  # file only
            "D": "proc",  # process only
            "E": "flag",  # flag only
        }

    def test_from_apply_reads_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_SMOKE", "yes")

        env = ApplyEnvSources.from_apply(env_overrides=["EXTRA=1"]).build()

        assert env["RAFT_SMOKE"] == "yes"
        assert env["EXTRA"] == "1"
