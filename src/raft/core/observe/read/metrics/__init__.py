"""Historical metrics readers shared by serve Trends and CLI consumers."""

from .http import HttpMetricsRead
from .jsonl import MetricsJsonlReader
from .resources import MetricsRead
from .series import MetricsSeriesStrategy
from .strategies import HttpMetricsSeriesBuilder, MetricsSeriesBuilder
from .window import (
    DEFAULT_MAX_POINTS,
    DEFAULT_WINDOW_SECONDS,
    PRESET_WINDOW_SECONDS,
    WINDOW_CHOICES,
    MetricsHistoryBounds,
    MetricsRangeQuery,
    ResolvedMetricsRange,
)

__all__ = [
    "DEFAULT_MAX_POINTS",
    "DEFAULT_WINDOW_SECONDS",
    "HttpMetricsRead",
    "HttpMetricsSeriesBuilder",
    "MetricsHistoryBounds",
    "MetricsJsonlReader",
    "MetricsRangeQuery",
    "MetricsRead",
    "MetricsSeriesBuilder",
    "MetricsSeriesStrategy",
    "PRESET_WINDOW_SECONDS",
    "ResolvedMetricsRange",
    "WINDOW_CHOICES",
]
