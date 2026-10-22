"""Apply-time ``--env`` / ``--env-file`` merge for ``raft apply``."""

from pathlib import Path
from typing import Optional, Sequence, Union

from raft.core.lifecycle.apply import ApplyEnvSources

from ..utils.argv import ApplyEnvOverrides

CONTROL_PLANE_REDEPLOY = frozenset(
    {
        "router",
        "raft-router",
        "dashboard",
        "raft-dashboard",
        "gate",
        "raft-gate",
        "controller",
        "raft-controller",
    }
)


class ApplyEnvCli:
    """Build preprocess env from process → file → peeled/Fire ``--env``."""

    @staticmethod
    def build(
        *,
        env_file: Optional[str],
        env: Optional[Union[str, Sequence[str]]],
    ) -> dict[str, str]:
        peeled = ApplyEnvOverrides.get()
        overrides: Union[None, str, Sequence[str]] = list(peeled) if peeled else env
        return ApplyEnvSources.from_apply(
            env_file=Path(env_file) if env_file else None,
            env_overrides=overrides,
        ).build()
