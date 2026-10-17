"""Bundled signal + rule-kind registries."""

from dataclasses import dataclass

from .kinds.kind_registry import RuleKindRegistry
from .signals.signal_registry import SignalRegistry


@dataclass
class AlertRegistries:
    """Composition root for signal sources and rule kinds."""

    signals: SignalRegistry
    kinds: RuleKindRegistry
