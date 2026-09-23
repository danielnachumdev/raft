"""Unit tests for App-manifest ``${VAR}`` expansion.

Contract under test (apply-time only):
- ``${NAME}`` required; unset or empty → error
- ``${NAME:-default}`` uses default when unset/empty; empty default allowed
- ``$${`` → literal ``${``
- Invalid placeholder → error
- Env merge precedence: process → ``--env-file`` → ``--env``
- Expansion happens on raw text before YAML parse
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from raft.errors import OperatorError
from raft.services.manifest_env import (
    ApplyEnvSources,
    DotenvLoader,
    EnvAssignment,
    ManifestTextExpander,
)

from .fixtures import (
    DEFAULT_PLACEHOLDER_CASES,
    EXPECTED_EXPANDED_SNIPPET,
    ExpandCase,
    ErrorCase,
    INVALID_PLACEHOLDER_CASES,
    MIXED_PLACEHOLDERS_ENV,
    MIXED_PLACEHOLDERS_TEXT,
    PLACEHOLDER_ENV,
    PLACEHOLDER_MANIFEST,
)

# ---------------------------------------------------------------------------
# ${NAME} / ${NAME:-default} / $${
# ---------------------------------------------------------------------------


class TestRequiredPlaceholder:
    def test_substitutes_nonempty_env_value(self) -> None:
        text = "name: ${NAME}"
        env = {"NAME": "web"}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "name: web"

    def test_errors_when_variable_unset(self) -> None:
        text = "x: ${FOO}"
        env: dict[str, str] = {}

        with pytest.raises(OperatorError, match=r"undefined variable FOO in \$\{FOO\}") as caught:
            ManifestTextExpander(env).expand(text)

        error = str(caught.value)
        assert "export FOO=" in error
        assert "--env-file" in error

    def test_errors_when_variable_empty(self) -> None:
        text = "x: ${FOO}"
        env = {"FOO": ""}

        with pytest.raises(OperatorError, match="undefined variable FOO"):
            ManifestTextExpander(env).expand(text)

    def test_error_includes_manifest_path(self) -> None:
        text = "${FOO}"
        env: dict[str, str] = {}
        path = "/tmp/app.yaml"

        with pytest.raises(OperatorError, match="manifest at /tmp/app.yaml") as caught:
            ManifestTextExpander(env, path=path).expand(text)

        error = str(caught.value)
        assert "export FOO=" in error
        assert "--env-file" in error


class TestDefaultPlaceholder:
    @pytest.mark.parametrize(
        "case",
        DEFAULT_PLACEHOLDER_CASES,
        ids=lambda c: c.id,
    )
    def test_uses_default_when_unset_or_empty(self, case: ExpandCase) -> None:
        expanded = ManifestTextExpander(case.env).expand(case.text)

        assert expanded == case.expected

    def test_default_closes_at_first_brace_nested_not_supported(self) -> None:
        # First `}` ends the placeholder — nested `${…}` in defaults is not supported.
        unset_env = {"B": "inner"}
        set_env = {"A": "set", "B": "inner"}
        text = "${A:-${B}}"

        when_unset = ManifestTextExpander(unset_env).expand(text)
        when_set = ManifestTextExpander(set_env).expand(text)

        # Unset A → default literal `${B` plus leftover `}` → `${B}`
        assert when_unset == "${B}"
        # Set A → value plus leftover closing brace from the inner-looking default
        assert when_set == "set}"


class TestLiteralEscape:
    def test_dollar_dollar_brace_becomes_literal_dollar_brace(self) -> None:
        text = "$${NAME}"
        env = {"NAME": "nope"}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "${NAME}"

    def test_escape_mid_string_does_not_look_up_name(self) -> None:
        text = "pre$${NAME}post"
        env: dict[str, str] = {}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "pre${NAME}post"

    def test_escape_then_real_placeholder(self) -> None:
        # $${ → literal ${, then ${REAL} expands.
        text = "$${${REAL}}"
        env = {"REAL": "ok"}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "${ok}"

    def test_bare_dollar_without_braces_untouched(self) -> None:
        text = "cost is $5 and $FOO"
        env = {"FOO": "x"}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "cost is $5 and $FOO"


class TestInvalidPlaceholder:
    @pytest.mark.parametrize(
        "case",
        INVALID_PLACEHOLDER_CASES,
        ids=lambda c: c.id,
    )
    def test_rejects_invalid_syntax(self, case: ErrorCase) -> None:
        with pytest.raises(OperatorError, match=case.match) as caught:
            ManifestTextExpander(case.env).expand(case.text)

        error = str(caught.value)
        assert "$${ for a literal" in error or "$${" in error


class TestMultiplePlaceholders:
    def test_adjacent_required_placeholders(self) -> None:
        text = "${A}${B}"
        env = {"A": "1", "B": "2"}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "12"

    def test_adjacent_defaults_when_unset(self) -> None:
        text = "${A:-x}${B:-y}"
        env: dict[str, str] = {}

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == "xy"

    def test_required_default_and_escape_in_one_document(self) -> None:
        text = MIXED_PLACEHOLDERS_TEXT
        env = MIXED_PLACEHOLDERS_ENV

        expanded = ManifestTextExpander(env).expand(text)

        assert expanded == EXPECTED_EXPANDED_SNIPPET


class TestExpandBeforeYamlParse:
    def test_expanded_text_is_valid_yaml_with_concrete_values(self) -> None:
        text = PLACEHOLDER_MANIFEST
        env = PLACEHOLDER_ENV

        expanded = ManifestTextExpander(env, path="app.yaml").expand(text)
        data = yaml.safe_load(expanded)

        assert data["metadata"]["name"] == "frontend-dev"
        # Empty default expands to empty text; YAML may load that as null.
        assert data["spec"]["publicHost"] in ("", None)
        assert data["spec"]["group"] == "limudpsanter-dev"
        assert data["spec"]["ref"] == "abc123"
        assert data["spec"]["path"] == "apps/frontend-dev"
        assert "${" not in expanded


# ---------------------------------------------------------------------------
# dotenv / --env / merge precedence
# ---------------------------------------------------------------------------


class TestDotenvLoader:
    def test_parses_comments_quotes_and_later_key_wins(self, tmp_path: Path) -> None:
        path = tmp_path / "vars.env"
        path.write_text(
            "# comment\n"
            "\n"
            "A=one\n"
            "A=two\n"
            "export B=bee\n"
            "C='quoted'\n"
            'D="dquoted"\n'
            "E= spaced \n",
            encoding="utf-8",
        )

        loaded = DotenvLoader(path).load()

        assert loaded == {
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

    def test_from_apply_reads_os_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAFT_SMOKE", "yes")

        env = ApplyEnvSources.from_apply(env_overrides=["EXTRA=1"]).build()

        assert env["RAFT_SMOKE"] == "yes"
        assert env["EXTRA"] == "1"
