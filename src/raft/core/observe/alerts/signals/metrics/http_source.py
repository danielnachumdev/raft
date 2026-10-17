"""metrics.http signal source."""

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.read.metrics.strategies.http_series import (
    EDGE_SERIES_ID,
    HttpMetricsSeriesBuilder,
)

from ...model.issues import ValidationIssue
from ..catalog_entries import metric_source_catalog
from ..context import SignalContext
from ..series import SignalPoint, SubjectSeries, ValueType
from ..signal_source import SignalSource
from .metric_keys import HTTP_METRICS
from .samples import MetricsSampleCache

_DERIVED = {
    "error_rate_5xx": ("status_5xx", "requests"),
    "error_rate_4xx": ("status_4xx", "requests"),
}


class HttpMetricSource(SignalSource):
    """HTTP edge/service metrics from http.jsonl."""

    def __init__(self) -> None:
        self._cache = MetricsSampleCache()
        self._builder = HttpMetricsSeriesBuilder()
        self._by_key = {m.key: m for m in HTTP_METRICS}

    @property
    def type_id(self) -> str:
        return "metrics.http"

    @property
    def value_type(self) -> ValueType:
        return ValueType.NUMERIC

    def catalog_entry(self) -> Dict[str, Any]:
        return metric_source_catalog(
            type_id=self.type_id,
            label="HTTP metrics (gate)",
            metrics=HTTP_METRICS,
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
        scope = "edge" if target == "edge" else "service"
        if target == "*":
            scope = "service"
        if scope not in self._by_key[str(metric)].scopes:
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
        path = MetricsPaths(ctx.home).http()
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
                if sid != EDGE_SERIES_ID
            ]
        key = EDGE_SERIES_ID if target == "edge" else target
        series = built.get(key)
        if series is None:
            return [SubjectSeries(target if target != "edge" else "edge", (), False)]
        subject = "edge" if target == "edge" else target
        return [self._one(subject, series, metric, wildcard=False)]

    def _one(
        self, subject: str, series: Dict[str, Any], metric: str, *, wildcard: bool
    ) -> SubjectSeries:
        points = []
        for point in series.get("points") or []:
            ts = self._ts(point.get("t"))
            if ts is None:
                continue
            points.append(SignalPoint(ts, self._value(point, metric)))
        return SubjectSeries(subject, tuple(points), wildcard=wildcard)

    def _value(self, point: Dict[str, Any], metric: str) -> Optional[float]:
        if metric in _DERIVED:
            num_key, den_key = _DERIVED[metric]
            num = point.get(num_key)
            den = point.get(den_key)
            if not isinstance(num, (int, float)) or not isinstance(den, (int, float)):
                return None
            if den == 0:
                return None
            return float(num) / float(den)
        value = point.get(metric)
        return float(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _ts(raw: Any):
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
