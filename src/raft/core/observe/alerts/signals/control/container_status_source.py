"""control.container_status STATE source."""

from datetime import datetime
from typing import Any, Dict, List, Mapping

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.models.state.scaling_store import ScalingStore
from ...model.issues import ValidationIssue
from ..catalog_entries import container_status_catalog
from ..context import SignalContext
from ..metrics.samples import MetricsSampleCache
from ..series import SignalPoint, SubjectSeries, ValueType
from ..signal_source import SignalSource


class ContainerStatusSource(SignalSource):
    """Latest container status from resources.jsonl samples."""

    def __init__(self) -> None:
        self._cache = MetricsSampleCache()

    @property
    def type_id(self) -> str:
        return "control.container_status"

    @property
    def value_type(self) -> ValueType:
        return ValueType.STATE

    def catalog_entry(self) -> Dict[str, Any]:
        return container_status_catalog(self.type_id)

    def validate_select(
        self, select: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        target = select.get("target")
        if not isinstance(target, str) or not target:
            return [ValidationIssue(f"{path}.target", "target is required")]
        return []

    def query(
        self,
        select: Mapping[str, Any],
        *,
        window_seconds: int,
        ctx: SignalContext,
    ) -> List[SubjectSeries]:
        window = min(600, max(window_seconds, 120))
        path = MetricsPaths(ctx.home).resources()
        samples = self._cache.samples(ctx, path, window_seconds=window)
        target = str(select.get("target"))
        scaling = ScalingStore(ctx.home)
        if target == "*":
            names = [
                n for n in ctx.app_names if not scaling.is_scaled_to_zero(n)
            ]
            return [self._series(name, samples, wildcard=True) for name in names]
        if scaling.is_scaled_to_zero(target):
            return []
        return [self._series(target, samples, wildcard=False)]

    def describe(self, select: Mapping[str, Any]) -> str:
        return f"{select.get('target')} status"

    def _series(
        self, subject: str, samples: List[Dict[str, Any]], *, wildcard: bool
    ) -> SubjectSeries:
        points = []
        for sample in samples:
            ts = self._ts(sample.get("ts"))
            if ts is None:
                continue
            status = self._status(sample, subject)
            if status is not None:
                points.append(SignalPoint(ts, status))
        return SubjectSeries(subject, tuple(points), wildcard=wildcard)

    @staticmethod
    def _status(sample: Dict[str, Any], service: str):
        rows = sample.get("containers")
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and row.get("service") == service:
                status = row.get("status")
                return str(status) if status is not None else None
        return None

    @staticmethod
    def _ts(raw: Any):
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
