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


def _source_label(path: Union[Path, str, None]) -> str:
    if path is None or path == "":
        return "manifest"
    return f"manifest at {path}"


def undefined_manifest_var(
    name: str,
    *,
    path: Union[Path, str, None] = None,
) -> OperatorError:
    return OperatorError(
        f"{_source_label(path)}: undefined variable {name} in ${{{name}}}\n"
        f"Fix: export {name}=… or pass --env-file / --env {name}=…"
    )


def invalid_manifest_placeholder(
    near: str,
    *,
    path: Union[Path, str, None] = None,
) -> OperatorError:
    snippet = near if len(near) <= 40 else near[:37] + "..."
    return OperatorError(
        f"{_source_label(path)}: invalid placeholder near {snippet!r}\n"
        f"Fix: use ${{NAME}}, ${{NAME:-default}}, or $${{ for a literal ${{"
    )


def bad_env_assignment(raw: str) -> OperatorError:
    return OperatorError(
        f"invalid --env value {raw!r} (expected KEY=VALUE)\n"
        f"Fix: pass --env NAME=value (NAME matching [A-Za-z_][A-Za-z0-9_]*)"
    )


def bad_env_file(path: Path, detail: str) -> OperatorError:
    return OperatorError(
        f"cannot read apply --env-file {path}: {detail}\n"
        f"Fix: pass a readable dotenv file (KEY=VALUE lines; # comments)"
    )


@dataclass(frozen=True)
class DotenvLoader:
    """Parse a dotenv-style file into a flat string map (later keys win)."""

    path: Path

    def load(self) -> dict[str, str]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise bad_env_file(self.path, str(exc)) from exc
        return self.parse(text, path=self.path)

    @staticmethod
    def parse(text: str, *, path: Optional[Path] = None) -> dict[str, str]:
        out: dict[str, str] = {}
        label = path if path is not None else Path("<env-file>")
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = _ASSIGN.match(line)
            if match is None:
                raise OperatorError(
                    f"invalid line {lineno} in --env-file {label}: {raw_line!r}\n"
                    f"Fix: use KEY=VALUE (# comments and blank lines ok)"
                )
            key, value = match.group(1), match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[key] = value
        return out


@dataclass(frozen=True)
class ApplyEnvSources:
    """Merge process env → ``--env-file`` → ``--env`` (later wins)."""

    environ: Mapping[str, str]
    env_file: Optional[Path] = None
    overrides: Sequence[str] = ()

    def build(self) -> dict[str, str]:
        merged = dict(self.environ)
        if self.env_file is not None:
            merged.update(DotenvLoader(self.env_file).load())
        for item in self.overrides:
            key, value = parse_env_assignment(item)
            merged[key] = value
        return merged


def parse_env_assignment(raw: str) -> tuple[str, str]:
    match = _ASSIGN.match(raw.strip())
    if match is None:
        raise bad_env_assignment(raw)
    return match.group(1), match.group(2)


def normalize_env_flags(env: Union[None, str, Sequence[str]]) -> list[str]:
    """Fire may pass a single ``--env`` as str or repeated flags as a sequence."""
    if env is None:
        return []
    if isinstance(env, str):
        return [env]
    return list(env)


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
        # start points at "${"
        body_start = start + 2
        name_match = _NAME.match(text, body_start)
        if name_match is None:
            raise invalid_manifest_placeholder(text[start:], path=self.path)
        name = name_match.group(0)
        cursor = name_match.end()
        if cursor < len(text) and text[cursor] == "}":
            return self._required(name), cursor + 1
        if text.startswith(":-", cursor):
            default_start = cursor + 2
            close = text.find("}", default_start)
            if close < 0:
                raise invalid_manifest_placeholder(text[start:], path=self.path)
            default = text[default_start:close]
            return self._with_default(name, default), close + 1
        raise invalid_manifest_placeholder(text[start:], path=self.path)

    def _required(self, name: str) -> str:
        value = self.env.get(name)
        if value is None or value == "":
            raise undefined_manifest_var(name, path=self.path)
        return value

    def _with_default(self, name: str, default: str) -> str:
        value = self.env.get(name)
        if value is None or value == "":
            return default
        return value


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
