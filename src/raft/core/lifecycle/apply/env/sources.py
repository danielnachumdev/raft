"""Merge process env → ``--env-file`` → ``--env`` (later wins)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from .assignment import EnvAssignment, EnvOverrides
from .dotenv import DotenvLoader


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
    ) -> "ApplyEnvSources":
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
