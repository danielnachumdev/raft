"""Unit tests for App-manifest ``${VAR}`` expansion."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from raft.errors import OperatorError
from raft.services.manifest_env import (
    ApplyEnvSources,
    DotenvLoader,
    ManifestTextExpander,
    build_apply_env,
    expand_manifest_text,
    normalize_env_flags,
    parse_env_assignment,
)


class TestExpandManifestText:
    def test_required_default_and_escape(self) -> None:
        env = {"NAME": "web", "HOST": "a.example"}
        text = "name: ${NAME}\nhost: ${HOST:-fallback}\nliteral: $${NAME}\n"
        assert expand_manifest_text(text, env) == (
            "name: web\nhost: a.example\nliteral: ${NAME}\n"
        )

    def test_default_used_when_unset_or_empty(self) -> None:
        assert expand_manifest_text("${X:-hi}", {}) == "hi"
        assert expand_manifest_text("${X:-hi}", {"X": ""}) == "hi"
        assert expand_manifest_text("${X:-}", {}) == ""
        assert expand_manifest_text("${X:-}", {"X": ""}) == ""

    def test_required_fails_when_unset_or_empty(self) -> None:
        with pytest.raises(OperatorError, match=r"undefined variable FOO in \$\{FOO\}"):
            expand_manifest_text("x: ${FOO}", {})
        with pytest.raises(OperatorError, match="undefined variable FOO"):
            expand_manifest_text("x: ${FOO}", {"FOO": ""})
        err = expand_manifest_text
        with pytest.raises(OperatorError, match="manifest at /tmp/app.yaml") as ctx:
            err("${FOO}", {}, path="/tmp/app.yaml")
        assert "export FOO=" in str(ctx.value)
        assert "--env-file" in str(ctx.value)

    def test_escape_does_not_expand_following_name(self) -> None:
        # $${NAME} → literal ${NAME}; NAME is not looked up.
        assert expand_manifest_text("$${NAME}", {"NAME": "nope"}) == "${NAME}"
        assert expand_manifest_text("pre$${NAME}post", {}) == "pre${NAME}post"
        # Escaped open then a real placeholder: $${ → ${, then ${REAL} expands.
        assert expand_manifest_text("$${${REAL}}", {"REAL": "ok"}) == "${ok}"

    def test_dollar_without_braces_untouched(self) -> None:
        assert expand_manifest_text("cost is $5 and $FOO", {"FOO": "x"}) == (
            "cost is $5 and $FOO"
        )

    def test_invalid_placeholders(self) -> None:
        cases = [
            "${}",
            "${123}",
            "${FOO-bar}",
            "${FOO:}",
            "${FOO:=x}",
            "${FOO",
            "${FOO:-bar",
            "${-x}",
        ]
        for raw in cases:
            with pytest.raises(OperatorError, match="invalid placeholder") as ctx:
                expand_manifest_text(raw, {"FOO": "1"})
            assert "$${ for a literal" in str(ctx.value) or "$${" in str(ctx.value)

    def test_default_closes_at_first_brace(self) -> None:
        # First `}` ends the placeholder — nested `${…}` in defaults is not supported.
        # Unset A → default literal `${B` plus leftover `}` → `${B}`.
        assert expand_manifest_text("${A:-${B}}", {"B": "inner"}) == "${B}"
        # Set A → value plus leftover closing brace from the inner-looking default.
        assert expand_manifest_text("${A:-${B}}", {"A": "set", "B": "inner"}) == "set}"

    def test_multiple_placeholders_and_adjacent(self) -> None:
        env = {"A": "1", "B": "2"}
        assert expand_manifest_text("${A}${B}", env) == "12"
        assert expand_manifest_text("${A:-x}${B:-y}", {}) == "xy"

    def test_yaml_remains_valid_after_expand(self) -> None:
        raw = """\
apiVersion: raft/v1
kind: App
metadata:
  name: ${RAFT_APP_NAME}
spec:
  publicHost: ${RAFT_APP_PUBLIC_HOST:-}
  group: ${RAFT_APP_GROUP}
  source: docker
  image: ghcr.io/example/app
  ref: ${RAFT_APP_REF}
  path: ${RAFT_APP_PATH}
  ports:
    - name: http
      containerPort: 80
      expose: http
"""
        env = {
            "RAFT_APP_NAME": "frontend-dev",
            "RAFT_APP_GROUP": "limudpsanter-dev",
            "RAFT_APP_REF": "abc123",
            "RAFT_APP_PATH": "apps/frontend-dev",
        }
        expanded = expand_manifest_text(raw, env, path="app.yaml")
        data = yaml.safe_load(expanded)
        assert data["metadata"]["name"] == "frontend-dev"
        # Empty default expands to empty text; YAML may load that as null.
        assert data["spec"]["publicHost"] in ("", None)
        assert data["spec"]["group"] == "limudpsanter-dev"
        assert data["spec"]["ref"] == "abc123"

    def test_expander_class_matches_function(self) -> None:
        env = {"N": "v"}
        text = "x: ${N}"
        assert ManifestTextExpander(env).expand(text) == expand_manifest_text(text, env)


class TestDotenvAndApplyEnv:
    def test_dotenv_comments_quotes_and_override(self, tmp_path: Path) -> None:
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

    def test_dotenv_missing_and_bad_line(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.env"
        with pytest.raises(OperatorError, match="cannot read apply --env-file"):
            DotenvLoader(missing).load()
        bad = tmp_path / "bad.env"
        bad.write_text("not-an-assignment\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="invalid line 1"):
            DotenvLoader(bad).load()

    def test_parse_env_assignment_and_normalize(self) -> None:
        assert parse_env_assignment("FOO=bar") == ("FOO", "bar")
        assert parse_env_assignment("export FOO=bar") == ("FOO", "bar")
        with pytest.raises(OperatorError, match="invalid --env value"):
            parse_env_assignment("nope")
        assert normalize_env_flags(None) == []
        assert normalize_env_flags("A=1") == ["A=1"]
        assert normalize_env_flags(["A=1", "B=2"]) == ["A=1", "B=2"]

    def test_precedence_environ_file_then_flags(self, tmp_path: Path) -> None:
        path = tmp_path / "e.env"
        path.write_text("A=from-file\nB=from-file\nC=from-file\n", encoding="utf-8")
        merged = ApplyEnvSources(
            environ={"A": "from-process", "B": "from-process", "D": "proc"},
            env_file=path,
            overrides=["B=from-flag", "E=flag"],
        ).build()
        assert merged == {
            "A": "from-file",
            "B": "from-flag",
            "C": "from-file",
            "D": "proc",
            "E": "flag",
        }

    def test_build_apply_env_uses_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAFT_SMOKE", "yes")
        env = build_apply_env(env_overrides=["EXTRA=1"])
        assert env["RAFT_SMOKE"] == "yes"
        assert env["EXTRA"] == "1"
