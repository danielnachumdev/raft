"""Parse a dotenv-style file into a flat string map (later keys win)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...errors.cta import OperatorError
from .assignment import ASSIGN_RE


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
        match = ASSIGN_RE.match(line)
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
