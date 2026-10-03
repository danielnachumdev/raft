"""TDD: directives use ``${VAR}`` + quotes; pipeline resolves if before expand."""

from __future__ import annotations

import pytest
import yaml

from raft.errors import OperatorError
from raft.services.apply.manifest_preprocess import ManifestPreprocessor, ManifestYamlLoader

from ....cta_asserts import assert_operator

ON = {"FLAG": "on", "MODE": "edge"}
OFF = {"FLAG": "off", "MODE": "edge"}


def _resolve(env: dict, text: str, *, path=None) -> str:
    return ManifestPreprocessor(env, path=path).resolve_directives(text)


class TestIfBlocks:
    def test_keeps_block_when_true(self) -> None:
        text = "a: 1\n${{ if ${FLAG} == 'on' }}\nextra: true\n${{ endif }}\nb: 2\n"
        assert _resolve(ON, text) == "a: 1\nextra: true\nb: 2\n"

    def test_drops_block_when_false(self) -> None:
        text = "a: 1\n${{ if ${FLAG} == 'on' }}\nextra: true\n${{ endif }}\nb: 2\n"
        assert _resolve(OFF, text) == "a: 1\nb: 2\n"

    def test_literal_on_left(self) -> None:
        text = "${{ if 'on' == ${FLAG} }}\nx: 1\n${{ endif }}\n"
        assert _resolve(ON, text) == "x: 1\n"

    def test_combined_and_or(self) -> None:
        text = "${{ if ${FLAG} == 'on' && ${MODE} == 'edge' }}\nok\n${{ endif }}\n"
        assert _resolve(ON, text) == "ok\n"
        assert _resolve({"FLAG": "on", "MODE": "off"}, text) == ""


class TestNestedIf:
    def test_nested_both_true(self) -> None:
        text = (
            "${{ if ${FLAG} == 'on' }}\n"
            "outer\n"
            "${{ if ${MODE} == 'edge' }}\n"
            "inner\n"
            "${{ endif }}\n"
            "${{ endif }}\n"
        )
        assert _resolve(ON, text) == "outer\ninner\n"

    def test_nested_outer_false(self) -> None:
        text = (
            "${{ if ${FLAG} == 'on' }}\n"
            "outer\n"
            "${{ if ${MODE} == 'edge' }}\n"
            "inner\n"
            "${{ endif }}\n"
            "${{ endif }}\n"
            "tail\n"
        )
        assert _resolve(OFF, text) == "tail\n"


class TestPipelineOrder:
    def test_directives_resolve_env_refs_before_body_expand(self) -> None:
        """Body ``${HOST}`` expands after if; condition uses ``${FLAG}`` itself."""
        raw = (
            "host: ${HOST}\n"
            "${{ if ${FLAG} == 'on' }}\n"
            "x: ${X}\n"
            "${{ endif }}\n"
        )
        out = ManifestPreprocessor({"HOST": "h", "FLAG": "on", "X": "1"}).preprocess(raw)
        assert out == "host: h\nx: 1\n"

    def test_env_value_with_spaces_in_condition(self) -> None:
        raw = "${{ if ${NAME} == 'Acme Corp' }}\nok\n${{ endif }}\n"
        out = ManifestPreprocessor({"NAME": "Acme Corp"}).preprocess(raw)
        assert out == "ok\n"

    def test_false_branch_does_not_require_body_vars(self) -> None:
        raw = "${{ if ${FLAG} == 'on' }}\nx: ${MISSING}\n${{ endif }}\ny: 1\n"
        out = ManifestPreprocessor({"FLAG": "off"}).preprocess(raw)
        assert out == "y: 1\n"


_OPTIONAL = """\
spec:
  publicHost: ${HOST}
  ${{ if ${INCLUDE_SCALING} == 'true' }}
  scaling:
    idleSeconds: ${IDLE}
    wakeTimeoutSeconds: 60
    minUpSeconds: 60
  ${{ endif }}
  ports: []
"""


class TestLoader:
    def test_optional_block(self) -> None:
        env = {"HOST": "site.example.com", "INCLUDE_SCALING": "true", "IDLE": "300"}
        data = ManifestYamlLoader(env).load(_OPTIONAL, path="app.yaml")
        assert data["spec"]["scaling"]["idleSeconds"] == 300

    def test_omitted_block(self) -> None:
        env = {"HOST": "site.example.com", "INCLUDE_SCALING": "false", "IDLE": "300"}
        data = ManifestYamlLoader(env).load(_OPTIONAL, path="app.yaml")
        assert "scaling" not in data["spec"]


class TestEscapeAndEdges:
    def test_dollar_dollar_brace_brace_escape(self) -> None:
        text = "$${{ if ${FLAG} == 'on' }}\n"
        assert _resolve(ON, text) == "${{ if ${FLAG} == 'on' }}\n"

    def test_inline_keeps_text(self) -> None:
        text = "v: ${{ if ${FLAG} == 'on' }}yes${{ endif }}\n"
        assert _resolve(ON, text) == "v: yes\n"

    def test_indented_directive_lines(self) -> None:
        text = "  ${{ if ${FLAG} == 'on' }}  \n  x: 1\n  ${{ endif }}\n"
        assert _resolve(ON, text) == "  x: 1\n"

    def test_directive_at_eof(self) -> None:
        text = "  ${{ if ${FLAG} == 'on' }}\n  x: 1\n  ${{ endif }}"
        assert _resolve(ON, text) == "  x: 1\n"

    def test_same_line_trailing_after_if(self) -> None:
        text = "${{ if ${FLAG} == 'on' }} keep\n${{ endif }}\n"
        assert _resolve(ON, text) == " keep\n"

    def test_false_branch_skips_escape(self) -> None:
        text = "${{ if ${FLAG} == 'on' }}\n$${{ kept }}\nhidden\n${{ endif }}\nlater\n"
        assert _resolve(OFF, text) == "later\n"

    def test_expand_passes_through_leftover_directive_escape(self) -> None:
        raw = "$${{ if ${FLAG} == 'on' }}\n"
        out = ManifestPreprocessor(ON).preprocess(raw)
        assert out == "${{ if on == 'on' }}\n"


class TestErrors:
    def test_bare_ident_in_directive_rejected(self) -> None:
        with pytest.raises(OperatorError, match="invalid") as caught:
            _resolve(ON, "${{ if FLAG == 'on' }}\na\n${{ endif }}\n")
        assert_operator(caught.value, contains=("Fix:",))

    def test_unmatched_endif(self) -> None:
        with pytest.raises(OperatorError, match="endif") as caught:
            _resolve(ON, "${{ endif }}\n")
        assert_operator(caught.value, contains=("Fix:", "if"))

    def test_unclosed_if(self) -> None:
        with pytest.raises(OperatorError, match="without matching"):
            _resolve(ON, "${{ if ${FLAG} == 'on' }}\nx\n")

    def test_endif_trailing_junk(self) -> None:
        with pytest.raises(OperatorError, match="unknown directive"):
            _resolve(ON, "${{ if ${FLAG} == 'on' }}\na\n${{ endif please }}\n")

    def test_unknown_directive(self) -> None:
        with pytest.raises(OperatorError, match="unknown directive"):
            _resolve(ON, "${{ else }}\n")

    def test_unclosed_directive(self) -> None:
        with pytest.raises(OperatorError, match="unclosed"):
            _resolve(ON, "${{ if ${FLAG} == 'on' ")

    def test_empty_if(self) -> None:
        with pytest.raises(OperatorError, match="invalid"):
            _resolve(ON, "${{ if }}\na\n${{ endif }}\n")

    def test_path_on_endif_error(self) -> None:
        with pytest.raises(OperatorError, match="manifest at app.yaml"):
            _resolve(ON, "${{ endif }}\n", path="app.yaml")

    def test_long_near_truncated(self) -> None:
        near = "${{ endif " + ("x" * 80) + " }}"
        with pytest.raises(OperatorError, match=r"\.\.\."):
            _resolve(ON, near + "\n")
