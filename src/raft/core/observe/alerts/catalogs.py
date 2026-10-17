"""Default alert registries composition root."""

from .kinds import EventCountKind, RuleKindRegistry, StateMatchKind, ThresholdKind
from .registries import AlertRegistries
from .signals import SignalRegistry
from .signals.control import ContainerStatusSource, GraphEventsSource
from .signals.metrics import HttpMetricSource, ResourcesMetricSource


class AlertCatalogs:
    """Build the default signal + kind registries."""

    @staticmethod
    def default() -> AlertRegistries:
        signals = SignalRegistry()
        for source in (
            ResourcesMetricSource(),
            HttpMetricSource(),
            ContainerStatusSource(),
            GraphEventsSource(),
        ):
            signals.register(source)
        kinds = RuleKindRegistry()
        for kind in (ThresholdKind(), StateMatchKind(), EventCountKind()):
            kinds.register(kind)
        return AlertRegistries(signals=signals, kinds=kinds)
