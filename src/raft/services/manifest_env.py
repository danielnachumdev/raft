"""Expand ``${VAR}`` placeholders in App manifest text before YAML parse.

Expansion is apply-time only (``raft apply --file`` / ``--git``). Registry
files store the expanded concrete document — render/redeploy/doctor never
re-expand. ``--env-file`` / ``--env`` feed this expander only; they are not
Compose / container environment.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from raft.errors import OperatorError

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ASSIGN = re.compile(
    r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)

# ---------------------------------------------------------------------------
# Public entrypoints (skim here first)
# ---------------------------------------------------------------------------


def expand_manifest_text(
    text: str,
    env: Mapping[str, str],
    *,
    path: Union[Path, str, None] = None,
) -> str:
    """Expand placeholders in ``text`` using ``env``; raise ``OperatorError`` on failure."""
    return ManifestTextExpander(env, path=path).expand(text)


def build_apply_env(
    *,
    environ: Optional[Mapping[str, str]] = None,
    env_file: Optional[Path] = None,
    env_overrides: Union[None, str, Sequence[str]] = None,
) -> dict[str, str]:
    """Build the env map used for one ``raft apply`` (process → file → flags)."""
    return ApplyEnvSources(
        environ=os.environ if environ is None else environ,
        env_file=env_file,
        overrides=normalize_env_flags(env_overrides),
    ).build()


def parse_env_assignment(raw: str) -> tuple[str, str]:
    """Parse a single ``KEY=VALUE`` (optional ``export``) from ``--env``."""
    match = _ASSIGN.match(raw.strip())
    if match is None:
        raise _bad_env_assignment(raw)
    return match.group(1), match.group(2)


def normalize_env_flags(env: Union[None, str, Sequence[str]]) -> list[str]:
    """Fire may pass a single ``--env`` as str or repeated flags as a sequence."""
    if env is None:
        return []
    if isinstance(env, str):
        return [env]
    return list(env)


# ---------------------------------------------------------------------------
# Env merge: process → --env-file → --env
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyEnvSources:
    """Merge process env → ``--env-file`` → ``--env`` (later wins)."""

    environ: Mapping[str, str]
    env_file: Optional[Path] = None
    overrides: Sequence[str] = ()

    def build(self) -> dict[str, str]:
        merged = dict(self.environ)
        self._merge_dotenv(merged)
        self._merge_flag_overrides(merged)
        return merged

    def _merge_dotenv(self, merged: dict[str, str]) -> None:
        if self.env_file is None:
            return
        merged.update(DotenvLoader(self.env_file).load())

    def _merge_flag_overrides(self, merged: dict[str, str]) -> None:
        for item in self.overrides:
            key, value = parse_env_assignment(item)
            merged[key] = value


# ---------------------------------------------------------------------------
# Dotenv file loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DotenvLoader:
    """Parse a dotenv-style file into a flat string map (later keys win)."""

    path: Path

    def load(self) -> dict[str, str]:
        text = self._read_text()
        return self.parse(text, path=self.path)

    def _read_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise _bad_env_file(self.path, str(exc)) from exc

    @staticmethod
    def parse(text: str, *, path: Optional[Path] = None) -> dict[str, str]:
        out: dict[str, str] = {}
        label = path if path is not None else Path("<env-file>")
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            parsed = _parse_dotenv_line(raw_line, lineno=lineno, label=label)
            if parsed is None:
                continue
            key, value = parsed
            out[key] = value
        return out


def _parse_dotenv_line(
    raw_line: str,
    *,
    lineno: int,
    label: Path,
) -> Optional[tuple[str, str]]:
    """Return ``(key, value)``, ``None`` for blank/comment, or raise on bad syntax."""
    line = raw_line.strip()
    if _is_blank_or_comment(line):
        return None
    match = _ASSIGN.match(line)
    if match is None:
        raise _bad_dotenv_line(lineno, label, raw_line)
    return match.group(1), _strip_matching_quotes(match.group(2).strip())


def _is_blank_or_comment(line: str) -> bool:
    return not line or line.startswith("#")


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Manifest text expansion (${NAME} / ${NAME:-default} / $${)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestTextExpander:
    """Pure ``${…}`` / ``$${`` expander over raw manifest text."""

    env: Mapping[str, str]
    path: Union[Path, str, None] = None

    def expand(self, text: str) -> str:
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text.startswith("$${", i):
                out.append("${")
                i += 3
                continue
            if text.startswith("${", i):
                value, end = self._expand_placeholder(text, i)
                out.append(value)
                i = end
                continue
            out.append(text[i])
            i += 1
        return "".join(out)

    def _expand_placeholder(self, text: str, start: int) -> tuple[str, int]:
        """Parse and resolve one ``${…}`` starting at ``start``; return ``(value, end)``."""
        name, cursor = self._parse_placeholder_name(text, start)
        if cursor < len(text) and text[cursor] == "}":
            return self._required(name), cursor + 1
        if text.startswith(":-", cursor):
            default, end = self._parse_default_body(text, start, cursor + 2)
            return self._with_default(name, default), end
        raise _invalid_manifest_placeholder(text[start:], path=self.path)

    def _parse_placeholder_name(self, text: str, start: int) -> tuple[str, int]:
        """Return ``(name, cursor_after_name)``; ``start`` points at ``${``."""
        name_match = _NAME.match(text, start + 2)
        if name_match is None:
            raise _invalid_manifest_placeholder(text[start:], path=self.path)
        return name_match.group(0), name_match.end()

    def _parse_default_body(
        self,
        text: str,
        start: int,
        default_start: int,
    ) -> tuple[str, int]:
        """Return ``(default, end_after_closing_brace)`` for ``${NAME:-default}``."""
        close = text.find("}", default_start)
        if close < 0:
            raise _invalid_manifest_placeholder(text[start:], path=self.path)
        return text[default_start:close], close + 1

    def _required(self, name: str) -> str:
        value = self._lookup(name)
        if value is None:
            raise _undefined_manifest_var(name, path=self.path)
        return value

    def _with_default(self, name: str, default: str) -> str:
        value = self._lookup(name)
        return default if value is None else value

    def _lookup(self, name: str) -> Optional[str]:
        """Return the env value, or ``None`` when unset or empty (shell-style)."""
        value = self.env.get(name)
        if value is None or value == "":
            return None
        return value


# ---------------------------------------------------------------------------
# Operator errors
# ---------------------------------------------------------------------------


def _source_label(path: Union[Path, str, None]) -> str:
    if path is None or path == "":
        return "manifest"
    return f"manifest at {path}"


def _snippet(near: str, *, limit: int = 40) -> str:
    if len(near) <= limit:
        return near
    return near[: limit - 3] + "..."


def _undefined_manifest_var(
    name: str,
    *,
    path: Union[Path, str, None] = None,
) -> OperatorError:
    return OperatorError(
        f"{_source_label(path)}: undefined variable {name} in ${{{name}}}\n"
        f"Fix: export {name}=… or pass --env-file / --env {name}=…"
    )


def _invalid_manifest_placeholder(
    near: str,
    *,
    path: Union[Path, str, None] = None,
) -> OperatorError:
    return OperatorError(
        f"{_source_label(path)}: invalid placeholder near {_snippet(near)!r}\n"
        f"Fix: use ${{NAME}}, ${{NAME:-default}}, or $${{ for a literal ${{"
    )


def _bad_env_assignment(raw: str) -> OperatorError:
    return OperatorError(
        f"invalid --env value {raw!r} (expected KEY=VALUE)\n"
        f"Fix: pass --env NAME=value (NAME matching [A-Za-z_][A-Za-z0-9_]*)"
    )


def _bad_env_file(path: Path, detail: str) -> OperatorError:
    return OperatorError(
        f"cannot read apply --env-file {path}: {detail}\n"
        f"Fix: pass a readable dotenv file (KEY=VALUE lines; # comments)"
    )


def _bad_dotenv_line(lineno: int, label: Path, raw_line: str) -> OperatorError:
    return OperatorError(
        f"invalid line {lineno} in --env-file {label}: {raw_line!r}\n"
        f"Fix: use KEY=VALUE (# comments and blank lines ok)"
    )
