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

import yaml

from raft.errors import OperatorError

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ASSIGN = re.compile(
    r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)

EnvOverrides = Union[None, str, Sequence[str]]


# ---------------------------------------------------------------------------
# KEY=VALUE parsing (--env flags / dotenv lines)
# ---------------------------------------------------------------------------


class EnvAssignment:
    """Parse and normalize ``KEY=VALUE`` assignments from CLI / dotenv text."""

    @classmethod
    def parse(cls, raw: str) -> tuple[str, str]:
        """Parse a single ``KEY=VALUE`` (optional ``export``) from ``--env``."""
        match = _ASSIGN.match(raw.strip())
        if match is None:
            raise cls._bad_assignment(raw)
        return match.group(1), match.group(2)

    @classmethod
    def normalize_flags(cls, env: EnvOverrides) -> list[str]:
        """Fire may pass a single ``--env`` as str or repeated flags as a sequence."""
        if env is None:
            return []
        if isinstance(env, str):
            return [env]
        return list(env)

    @staticmethod
    def _bad_assignment(raw: str) -> OperatorError:
        return OperatorError(
            f"invalid --env value {raw!r} (expected KEY=VALUE)\n"
            f"Fix: pass --env NAME=value (NAME matching [A-Za-z_][A-Za-z0-9_]*)"
        )


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
            raise self._bad_env_file(str(exc)) from exc

    @classmethod
    def parse(cls, text: str, *, path: Optional[Path] = None) -> dict[str, str]:
        out: dict[str, str] = {}
        label = path if path is not None else Path("<env-file>")
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            parsed = cls._parse_line(raw_line, lineno=lineno, label=label)
            if parsed is None:
                continue
            key, value = parsed
            out[key] = value
        return out

    @classmethod
    def _parse_line(
        cls,
        raw_line: str,
        *,
        lineno: int,
        label: Path,
    ) -> Optional[tuple[str, str]]:
        line = raw_line.strip()
        if cls._is_blank_or_comment(line):
            return None
        match = _ASSIGN.match(line)
        if match is None:
            raise cls._bad_line(lineno, label, raw_line)
        return match.group(1), cls._strip_matching_quotes(match.group(2).strip())

    @staticmethod
    def _is_blank_or_comment(line: str) -> bool:
        return not line or line.startswith("#")

    @staticmethod
    def _strip_matching_quotes(value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            return value[1:-1]
        return value

    def _bad_env_file(self, detail: str) -> OperatorError:
        return OperatorError(
            f"cannot read apply --env-file {self.path}: {detail}\n"
            f"Fix: pass a readable dotenv file (KEY=VALUE lines; # comments)"
        )

    @staticmethod
    def _bad_line(lineno: int, label: Path, raw_line: str) -> OperatorError:
        return OperatorError(
            f"invalid line {lineno} in --env-file {label}: {raw_line!r}\n"
            f"Fix: use KEY=VALUE (# comments and blank lines ok)"
        )


# ---------------------------------------------------------------------------
# Env merge: process → --env-file → --env
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyEnvSources:
    """Merge process env → ``--env-file`` → ``--env`` (later wins)."""

    environ: Mapping[str, str]
    env_file: Optional[Path] = None
    overrides: Sequence[str] = ()

    @classmethod
    def from_apply(
        cls,
        *,
        environ: Optional[Mapping[str, str]] = None,
        env_file: Optional[Path] = None,
        env_overrides: EnvOverrides = None,
    ) -> ApplyEnvSources:
        """Build sources for one ``raft apply`` from process / file / flag inputs."""
        return cls(
            environ=os.environ if environ is None else environ,
            env_file=env_file,
            overrides=EnvAssignment.normalize_flags(env_overrides),
        )

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
            key, value = EnvAssignment.parse(item)
            merged[key] = value


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
        raise self._invalid_placeholder(text[start:])

    def _parse_placeholder_name(self, text: str, start: int) -> tuple[str, int]:
        """Return ``(name, cursor_after_name)``; ``start`` points at ``${``."""
        name_match = _NAME.match(text, start + 2)
        if name_match is None:
            raise self._invalid_placeholder(text[start:])
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
            raise self._invalid_placeholder(text[start:])
        return text[default_start:close], close + 1

    def _required(self, name: str) -> str:
        value = self._lookup(name)
        if value is None:
            raise self._undefined(name)
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

    def _source_label(self) -> str:
        if self.path is None or self.path == "":
            return "manifest"
        return f"manifest at {self.path}"

    @staticmethod
    def _snippet(near: str, *, limit: int = 40) -> str:
        if len(near) <= limit:
            return near
        return near[: limit - 3] + "..."

    def _undefined(self, name: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: undefined variable {name} in ${{{name}}}\n"
            f"Fix: export {name}=… or pass --env-file / --env {name}=…"
        )

    def _invalid_placeholder(self, near: str) -> OperatorError:
        return OperatorError(
            f"{self._source_label()}: invalid placeholder near "
            f"{self._snippet(near)!r}\n"
            f"Fix: use ${{NAME}}, ${{NAME:-default}}, or $${{ for a literal ${{"
        )


# ---------------------------------------------------------------------------
# Expand then YAML-load (apply path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestYamlLoader:
    """Expand apply-time placeholders, then ``yaml.safe_load`` the result."""

    env: Mapping[str, str]

    def load(self, raw: str, *, path: Union[Path, str]):
        expanded = ManifestTextExpander(self.env, path=path).expand(raw)
        return yaml.safe_load(expanded)
