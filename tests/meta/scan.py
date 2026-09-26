"""Scan Python trees for file and function-body size.

Measurement rules
-----------------
* **File lines:** number of lines via ``Path.read_text().splitlines()``
  (trailing newline does not add a line; blank and comment lines count).
* **Function/method body lines:** AST ``FunctionDef`` / ``AsyncFunctionDef``
  only. Inclusive span from the first body statement's ``lineno`` through
  the last body's ``end_lineno``. Docstrings count; the ``def`` line and
  decorators do not. Nested defs are reported separately. Lambdas ignored.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_RAFT = REPO_ROOT / "src" / "raft"
TESTS_ROOT = REPO_ROOT / "tests"

MAX_FILE_LINES = 300
MAX_BODY_LINES = 20

FileOffender = Tuple[str, int]
BodyOffender = Tuple[str, int]


class CodebaseScanner:
    """Walk ``.py`` files and collect size-limit offenders."""

    def python_files(self, root: Path) -> List[Path]:
        return sorted(p for p in root.rglob("*.py") if p.is_file())

    def file_line_count(self, path: Path) -> int:
        return len(path.read_text(encoding="utf-8").splitlines())

    def file_offenders(self, root: Path, limit: int = MAX_FILE_LINES) -> List[FileOffender]:
        out: List[FileOffender] = []
        for path in self.python_files(root):
            n = self.file_line_count(path)
            if n >= limit:
                out.append((self._rel(path), n))
        return out

    def body_offenders(self, root: Path, limit: int = MAX_BODY_LINES) -> List[BodyOffender]:
        out: List[BodyOffender] = []
        for path in self.python_files(root):
            out.extend(self._bodies_in_file(path, limit))
        return out

    def _bodies_in_file(self, path: Path, limit: int) -> List[BodyOffender]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = self._rel(path)
        found: List[BodyOffender] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            n = self._body_line_count(node)
            if n > limit:
                found.append((f"{rel}:{node.name}", n))
        return found

    def _body_line_count(self, node: ast.AST) -> int:
        body = getattr(node, "body", None) or []
        if not body:
            return 0
        end = body[-1].end_lineno
        return (end or body[-1].lineno) - body[0].lineno + 1

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(REPO_ROOT))
