"""Unit tests for ``ManifestTextExpander``."""

from __future__ import annotations

import pytest
import yaml

from raft.errors import OperatorError
from raft.services.apply.manifest_env import ManifestTextExpander

from ....cta_asserts import assert_operator
from .fixtures import (
    DEFAULT_PLACEHOLDER_CASES,
    EXPECTED_EXPANDED_SNIPPET,
    INVALID_PLACEHOLDER_CASES,
    MIXED_PLACEHOLDERS_ENV,
    MIXED_PLACEHOLDERS_TEXT,
    PLACEHOLDER_ENV,
    PLACEHOLDER_MANIFEST,
    ExpandCase,
    ErrorCase,
)


class TestRequiredAndDefault:
    @pytest.mark.parametrize("case", DEFAULT_PLACEHOLDER_CASES, ids=lambda c: c.id)
    def test_valid_cases(self, case: ExpandCase) -> None:
        expanded = ManifestTextExpander(case.env).expand(case.text)
        assert expanded == case.expected

    def test_undefined_required(self) -> None:
        with pytest.raises(OperatorError, match="undefined variable FOO") as caught:
            ManifestTextExpander({}).expand("x: ${FOO}")
        assert_operator(caught.value, contains=("--env-file", "FOO"))

    def test_empty_env_value_treated_as_unset_for_required(self) -> None:
        with pytest.raises(OperatorError, match="undefined variable FOO"):
            ManifestTextExpander({"FOO": ""}).expand("${FOO}")

    def test_default_when_empty_or_unset(self) -> None:
        text = "${A:-fallback}"
        assert ManifestTextExpander({}).expand(text) == "fallback"
        assert ManifestTextExpander({"A": ""}).expand(text) == "fallback"
        assert ManifestTextExpander({"A": "set"}).expand(text) == "set"

    def test_nested_looking_default_is_literal(self) -> None:
        # Default body is literal text until `}`; not a nested expand.
        text = "${A:-${B}}"
        when_unset = ManifestTextExpander({}).expand(text)
        when_set = ManifestTextExpander({"A": "set"}).expand(text)
        # Unset A → default literal `${B` plus leftover `}` → `${B}`
        assert when_unset == "${B}"
        # Set A → value plus leftover closing brace from the inner-looking default
        assert when_set == "set}"


class TestCommentsAndPassThrough:
    def test_full_line_comment_keeps_placeholders(self) -> None:
        text = "# name: ${NAME}\nname: ${NAME}\n"
        assert ManifestTextExpander({"NAME": "web"}).expand(text) == (
            "# name: ${NAME}\nname: web\n"
        )

    def test_indented_full_line_comment(self) -> None:
        text = "  # ${MISSING}\nok: 1\n"
        assert ManifestTextExpander({}).expand(text) == "  # ${MISSING}\nok: 1\n"

    def test_comment_without_trailing_newline(self) -> None:
        text = "# ${MISSING}"
        assert ManifestTextExpander({}).expand(text) == "# ${MISSING}"

    def test_inline_hash_still_expands(self) -> None:
        # Trailing `# …` on a value line is not a full-line comment.
        text = "x: ${NAME} # note ${NOTE}\n"
        assert ManifestTextExpander({"NAME": "web", "NOTE": "n"}).expand(text) == (
            "x: web # note n\n"
        )

    def test_bare_dollar_without_braces_untouched(self) -> None:
        text = "cost is $5 and $FOO"
        assert ManifestTextExpander({"FOO": "x"}).expand(text) == "cost is $5 and $FOO"

    def test_dollar_brace_brace_passes_through(self) -> None:
        assert ManifestTextExpander({}).expand("${{ if }}") == "${{ if }}"


class TestInvalidPlaceholder:
    @pytest.mark.parametrize(
        "case",
        INVALID_PLACEHOLDER_CASES,
        ids=lambda c: c.id,
    )
    def test_rejects_invalid_syntax(self, case: ErrorCase) -> None:
        with pytest.raises(OperatorError, match=case.match) as caught:
            ManifestTextExpander(case.env).expand(case.text)

        assert_operator(caught.value, contains=("Fix:",))


class TestMultiplePlaceholders:
    def test_adjacent_required_placeholders(self) -> None:
        assert ManifestTextExpander({"A": "1", "B": "2"}).expand("${A}${B}") == "12"

    def test_adjacent_defaults_when_unset(self) -> None:
        assert ManifestTextExpander({}).expand("${A:-x}${B:-y}") == "xy"

    def test_mixed_snippet(self) -> None:
        expanded = ManifestTextExpander(MIXED_PLACEHOLDERS_ENV).expand(
            MIXED_PLACEHOLDERS_TEXT
        )
        assert expanded == EXPECTED_EXPANDED_SNIPPET

    def test_expanded_text_is_valid_yaml_with_concrete_values(self) -> None:
        expanded = ManifestTextExpander(PLACEHOLDER_ENV, path="app.yaml").expand(
            PLACEHOLDER_MANIFEST
        )
        data = yaml.safe_load(expanded)
        assert data["metadata"]["name"] == "frontend-dev"
        assert data["spec"]["publicHost"] in ("", None)
        assert data["spec"]["group"] == "demo-stack"
        assert data["spec"]["ref"] == "abc123"
        assert data["spec"]["path"] == "apps/frontend-dev"
        assert "${" not in expanded
