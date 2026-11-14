"""Absent-container STATUS column (manual-stop / scaled / redeploying / not running)."""

from pathlib import Path
from typing import Optional

from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.core.models.state.scaling_store import ScalingStore
from .models import (
    STATUS_MANUAL_STOP,
    STATUS_NOT_RUNNING,
    STATUS_REDEPLOYING,
    STATUS_SCALED_TO_ZERO,
)


class AbsentStatus:
    """Resolve the human STATUS string when Compose has no container."""

    @staticmethod
    def for_app(root: Path, app_name: Optional[str]) -> str:
        if not app_name:
            return STATUS_NOT_RUNNING
        if RedeployingStore(root).is_redeploying(app_name):
            return STATUS_REDEPLOYING
        if ManualStopStore(root).is_manual_stop(app_name):
            return STATUS_MANUAL_STOP
        if ScalingStore(root).is_scaled_to_zero(app_name):
            return STATUS_SCALED_TO_ZERO
        return STATUS_NOT_RUNNING
