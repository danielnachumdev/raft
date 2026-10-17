"""Evaluate one alert rule to subject outcomes."""

import logging
from typing import List, Optional, Tuple

from raft.core.core.errors.cta import OperatorError

from ..model.rule import AlertRule
from ..registries import AlertRegistries
from ..signals.context import SignalContext
from .condition_evaluator import ConditionEvaluator
from .leaf_result import SubjectOutcome

logger = logging.getLogger(__name__)


class AlertRuleEvaluator:
    """Evaluate one rule; convert source errors into a rule error."""

    def __init__(self, registries: AlertRegistries) -> None:
        self._conditions = ConditionEvaluator(registries)

    def evaluate(
        self, rule: AlertRule, ctx: SignalContext
    ) -> Tuple[Optional[str], List[SubjectOutcome]]:
        try:
            return None, self._conditions.evaluate(rule, ctx)
        except OperatorError as exc:
            return str(exc).split("\n")[0], []
        except OSError as exc:
            return f"{type(exc).__name__}: {exc}", []
