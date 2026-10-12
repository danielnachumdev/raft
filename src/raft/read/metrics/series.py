"""ABC for shaping metrics JSONL samples into chart series."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set


class MetricsSeriesStrategy(ABC):
    """Open-closed series builder — one concrete strategy per metrics kind."""

    @abstractmethod
    def build(
        self,
        samples: List[Dict[str, Any]],
        *,
        wanted: Optional[Set[str]],
    ) -> Dict[str, Dict[str, Any]]:
        """Named series id → meta + points for the sample window."""

    @abstractmethod
    def available(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Series descriptors present in ``samples`` (for SPA pickers)."""

    @staticmethod
    def downsample(series: Dict[str, Any], *, max_points: int) -> Dict[str, Any]:
        points = series["points"]
        if max_points < 1 or len(points) <= max_points:
            return series
        step = len(points) / float(max_points)
        picked = [points[min(len(points) - 1, int(i * step))] for i in range(max_points)]
        out = dict(series)
        out["points"] = picked
        return out

    @staticmethod
    def as_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return out if out == out else None  # NaN check

    @staticmethod
    def as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}
