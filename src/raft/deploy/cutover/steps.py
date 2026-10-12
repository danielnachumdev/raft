"""Ordered dual-run cutover plan (previous-image tmp → stable)."""

from .session import CutoverSession
from .step import Step

DEPLOY_CUTOVER: tuple[Step, ...] = (
    Step(
        "snapshot_previous_image",
        "Remember the currently running image hash",
        CutoverSession.snapshot_previous_image,
    ),
    Step(
        "start_tmp_from_previous",
        "Run that hash as <app>_tmp",
        CutoverSession.start_tmp_from_previous,
    ),
    Step(
        "shift_traffic_to_tmp",
        "Nginx → tmp, reload, drain",
        CutoverSession.shift_traffic_to_tmp,
    ),
    Step(
        "rebuild_stable_service",
        "Build/recreate the stable Compose service",
        CutoverSession.rebuild_stable_service,
    ),
    Step(
        "shift_traffic_to_stable",
        "Nginx → stable name, reload, drain",
        CutoverSession.shift_traffic_to_stable,
    ),
    Step("remove_tmp", "Delete the temporary container", CutoverSession.remove_tmp),
)
