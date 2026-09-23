"""Shared constants and cases for App-manifest ``${VAR}`` expansion tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

# ---------------------------------------------------------------------------
# Named cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpandCase:
    """One declarative expand example: input text + env → expected output."""

    id: str
    text: str
    env: Mapping[str, str]
    expected: str


@dataclass(frozen=True)
class ErrorCase:
    """One declarative expand failure: input text + env → error substring."""

    id: str
    text: str
    env: Mapping[str, str]
    match: str


DEFAULT_PLACEHOLDER_CASES: tuple[ExpandCase, ...] = (
    ExpandCase("unset", "${X:-hi}", {}, "hi"),
    ExpandCase("empty", "${X:-hi}", {"X": ""}, "hi"),
    ExpandCase("set", "${X:-hi}", {"X": "set"}, "set"),
    ExpandCase("unset_empty_default", "${X:-}", {}, ""),
    ExpandCase("empty_empty_default", "${X:-}", {"X": ""}, ""),
)

INVALID_PLACEHOLDER_CASES: tuple[ErrorCase, ...] = (
    ErrorCase("empty_name", "${}", {}, "invalid placeholder"),
    ErrorCase("numeric_name", "${123}", {}, "invalid placeholder"),
    ErrorCase("hyphen_in_name", "${FOO-bar}", {"FOO": "1"}, "invalid placeholder"),
    ErrorCase("colon_without_dash", "${FOO:}", {"FOO": "1"}, "invalid placeholder"),
    ErrorCase("colon_equals", "${FOO:=x}", {"FOO": "1"}, "invalid placeholder"),
    ErrorCase("unclosed_required", "${FOO", {"FOO": "1"}, "invalid placeholder"),
    ErrorCase("unclosed_default", "${FOO:-bar", {"FOO": "1"}, "invalid placeholder"),
    ErrorCase("leading_dash", "${-x}", {}, "invalid placeholder"),
)

# ---------------------------------------------------------------------------
# Sample manifest snippets / env maps (unit expander)
# ---------------------------------------------------------------------------

PLACEHOLDER_MANIFEST = """\
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

PLACEHOLDER_ENV: dict[str, str] = {
    "RAFT_APP_NAME": "frontend-dev",
    "RAFT_APP_GROUP": "limudpsanter-dev",
    "RAFT_APP_REF": "abc123",
    "RAFT_APP_PATH": "apps/frontend-dev",
}

MIXED_PLACEHOLDERS_TEXT = "name: ${NAME}\nhost: ${HOST:-fallback}\nliteral: $${NAME}\n"

EXPECTED_EXPANDED_SNIPPET = """\
name: web
host: a.example
literal: ${NAME}
"""

MIXED_PLACEHOLDERS_ENV: dict[str, str] = {
    "NAME": "web",
    "HOST": "a.example",
}

# ---------------------------------------------------------------------------
# Apply-path manifests (file / git sources)
# ---------------------------------------------------------------------------

PLACEHOLDER_FILE_MANIFEST = """\
apiVersion: raft/v1
kind: App
metadata:
  name: ${RAFT_APP_NAME}
spec:
  publicHost: ${RAFT_APP_HOST:-web.test}
  source: local
  path: apps/${RAFT_APP_NAME}
  ref: main
  www: true
  ports:
    - name: http
      containerPort: 80
      expose: http
  build:
    context: .
"""

MISSING_VAR_FILE_MANIFEST = """\
apiVersion: raft/v1
kind: App
metadata:
  name: ${MISSING}
spec:
  publicHost: web.test
  source: local
  path: apps/x
  ref: main
  ports:
    - name: http
      containerPort: 80
      expose: http
  build: {context: .}
"""

PLACEHOLDER_GIT_MANIFEST = """\
apiVersion: raft/v1
kind: App
metadata:
  name: ${APP_NAME}
spec:
  publicHost: git.test
  source: git
  path: apps/${APP_NAME}
  ports:
    - name: http
      containerPort: 80
      expose: http
  build: {context: .}
"""

MISSING_VAR_GIT_MANIFEST = """\
apiVersion: raft/v1
kind: App
metadata:
  name: ${MISSING}
spec:
  publicHost: git.test
  source: git
  path: apps/x
  ports:
    - name: http
      containerPort: 80
      expose: http
  build: {context: .}
"""


def clone_writes_manifest(text: str) -> Callable[..., None]:
    """Return a git side_effect that writes ``.raft/app.yaml`` on clone."""

    def clone(*args, **kwargs):
        if "clone" not in args:
            return
        target = Path(args[-1])
        (target / ".raft").mkdir(parents=True, exist_ok=True)
        (target / ".raft" / "app.yaml").write_text(text, encoding="utf-8")

    return clone


clone_writes_placeholder_manifest = clone_writes_manifest(PLACEHOLDER_GIT_MANIFEST)
clone_writes_missing_var_manifest = clone_writes_manifest(MISSING_VAR_GIT_MANIFEST)
