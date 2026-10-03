"""TDD: directive expressions — quoted strings + ``${VAR}`` env refs only."""

from __future__ import annotations

from typing import Dict, Optional

import pytest

from raft.errors import OperatorError
from raft.services.apply.manifest_expr import DirectiveExpression

from ....cta_asserts import assert_operator

ENV = {"FLAG": "on", "MODE": "edge", "OTHER": "on", "WEIRD": "a b/c"}


def _eval(expr: str, env: Optional[Dict[str, str]] = None) -> bool:
    return DirectiveExpression(env if env is not None else ENV).evaluate(expr)


class TestComparisons:
    def test_env_ref_eq_literal(self) -> None:
        assert _eval("${FLAG} == 'on'") is True
        assert _eval("${FLAG} == 'off'") is False

    def test_literal_eq_env_ref(self) -> None:
        assert _eval("'on' == ${FLAG}") is True
        assert _eval("'off' == ${FLAG}") is False

    def test_env_ref_eq_env_ref(self) -> None:
        assert _eval("${FLAG} == ${OTHER}") is True
        assert _eval("${FLAG} == ${MODE}") is False

    def test_literal_eq_literal(self) -> None:
        assert _eval("'a' == 'a'") is True
        assert _eval("'a' == 'b'") is False

    def test_ne_both_sides(self) -> None:
        assert _eval("${FLAG} != 'off'") is True
        assert _eval("'off' != ${FLAG}") is True
        assert _eval("${FLAG} != ${OTHER}") is False

    def test_double_quoted_literals(self) -> None:
        assert _eval('${FLAG} == "on"') is True
        assert _eval('"on" == ${FLAG}') is True

    def test_empty_default_and_literal(self) -> None:
        # Same empty-as-unset rules as manifest ``${VAR:-default}``.
        assert _eval("${EMPTY:-} == ''", env={}) is True
        assert _eval("${FLAG} == ''") is False

    def test_env_value_need_not_be_identifier_shaped(self) -> None:
        assert _eval("${WEIRD} == 'a b/c'") is True
        assert _eval("'a b/c' == ${WEIRD}") is True

    def test_env_default_syntax(self) -> None:
        assert _eval("${MISSING:-fallback} == 'fallback'", env={}) is True
        assert _eval("${FLAG:-x} == 'on'") is True


class TestBooleanCombine:
    def test_and_or_parentheses(self) -> None:
        assert _eval("${FLAG} == 'on' && ${MODE} == 'edge'") is True
        assert _eval("${FLAG} == 'on' && ${MODE} == 'off'") is False
        assert _eval("${FLAG} == 'off' || ${MODE} == 'edge'") is True
        assert _eval("${FLAG} == 'off' || ${MODE} == 'off'") is False
        assert _eval("${FLAG} == 'off' || ${MODE} == 'edge' && ${OTHER} == 'on'") is True
        assert _eval("(${FLAG} == 'off' || ${MODE} == 'edge') && ${OTHER} == 'on'") is True
        assert _eval("(${FLAG} == 'off' || ${MODE} == 'off') && ${OTHER} == 'on'") is False


class TestErrors:
    def test_bare_ident_rejected(self) -> None:
        with pytest.raises(OperatorError, match="invalid") as caught:
            _eval("FLAG == 'on'")
        assert_operator(caught.value, contains=("Fix:", "${"))

    def test_bareword_literal_rejected(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("${FLAG} == on")

    def test_undefined_env_ref(self) -> None:
        with pytest.raises(OperatorError, match="undefined variable MISSING") as caught:
            _eval("${MISSING} == 'x'", env={})
        assert_operator(caught.value, contains=("--env", "MISSING"))

    def test_empty_expression(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("")

    def test_trailing_junk(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("${FLAG} == 'on' 'extra'")

    def test_unbalanced_paren(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("(${FLAG} == 'on'")

    def test_path_label_in_error(self) -> None:
        with pytest.raises(OperatorError, match="manifest at app.yaml") as caught:
            DirectiveExpression({}, path="app.yaml").evaluate("${MISSING} == 'x'")
        assert_operator(caught.value, contains=("Fix:",))

    def test_bare_env_ref_is_not_a_condition(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("${FLAG}")

    def test_cannot_compare_bool_subexpr_to_string(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("${FLAG} == (${MODE} == 'edge')")

    def test_unexpected_operator_as_primary(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("== 'on'")

    def test_missing_rhs(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _eval("${FLAG} ==")

    def test_long_bad_token_truncated(self) -> None:
        junk = "@" * 60
        with pytest.raises(OperatorError, match=r"\.\.\.") as caught:
            _eval(junk)
        assert_operator(caught.value, contains=("Fix:",))
