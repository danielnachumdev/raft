"""metrics.resources signal source."""

from datetime import datetime
from typing import Any, Dict, List, Mapping

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.read.metrics.strategies.resources_series import (
    HOST_SERIES_ID,
    MetricsSeriesBuilder,
)

from ...model.issues import ValidationIssue
from ..catalog_entries import metric_source_catalog
from ..context import SignalContext
from ..series import SignalPoint, SubjectSeries, ValueType
from ..signal_source import SignalSource
from .metric_keys import RESOURCE_METRICS
from .samples import MetricsSampleCache


class ResourcesMetricSource(SignalSource):
    """Resource utilization from resources.jsonl."""

    def __init__(self) -> None:
        self._cache = MetricsSampleCache()
        self._builder = MetricsSeriesBuilder()
        self._by_key = {m.key: m for m in RESOURCE_METRICS}

    @property
    def type_id(self) -> str:
        return "metrics.resources"

    @property
    def value_type(self) -> ValueType:
        return ValueType.NUMERIC

    def catalog_entry(self) -> Dict[str, Any]:
        return metric_source_catalog(
            type_id=self.type_id,
            label="Resource metrics",
            metrics=RESOURCE_METRICS,
        )

    def validate_select(
        self, select: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        target = select.get("target")
        metric = select.get("metric")
        if not isinstance(target, str) or not target:
            issues.append(ValidationIssue(f"{path}.target", "target is required"))
        if metric not in self._by_key:
            issues.append(ValidationIssue(f"{path}.metric", f"unknown metric {metric!r}"))
            return issues
        scope = self._scope(str(target) if isinstance(target, str) else "")
        if scope and scope not in self._by_key[str(metric)].scopes:
            issues.append(
                ValidationIssue(
                    f"{path}.metric",
                    f"metric {metric!r} not valid for scope {scope}",
                )
            )
        return issues

    def query(
        self,
        select: Mapping[str, Any],
        *,
        window_seconds: int,
        ctx: SignalContext,
    ) -> List[SubjectSeries]:
        path = MetricsPaths(ctx.home).resources()
        samples = self._cache.samples(ctx, path, window_seconds=window_seconds)
        built = self._builder.build(samples, wanted=None)
        metric = str(select.get("metric"))
        target = str(select.get("target"))
        return self._series_for(built, target=target, metric=metric)

    def describe(self, select: Mapping[str, Any]) -> str:
        return f"{select.get('target')} {select.get('metric')}"

    def _series_for(
        self, built: Dict[str, Any], *, target: str, metric: str
    ) -> List[SubjectSeries]:
        if target == "*":
            return [
                self._one(sid, series, metric, wildcard=True)
                for sid, series in built.items()
                if series.get("role") == "app"
            ]
        series = built.get(target)
        if series is None:
            return [SubjectSeries(target, (), wildcard=False)]
        return [self._one(target, series, metric, wildcard=False)]

    def _one(
        self, subject: str, series: Dict[str, Any], metric: str, *, wildcard: bool
    ) -> SubjectSeries:
        points = []
        for point in series.get("points") or []:
            ts = self._ts(point.get("t"))
            if ts is None:
                continue
            points.append(SignalPoint(ts, point.get(metric)))
        return SubjectSeries(subject, tuple(points), wildcard=wildcard)

    @staticmethod
    def _scope(target: str) -> str:
        if target == "host":
            return "host"
        if target == "*":
            return "service"
        return "service"

    @staticmethod
    def _ts(raw: Any) -> Any:
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
