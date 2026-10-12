"""ABC for subprocess failure classification strategies."""

from abc import ABC, abstractmethod
import subprocess

from ..classify_ctx import SubprocessCtx
from ..operator_error import OperatorError


class SubprocessRule(ABC):
    """One match/build strategy for ``SubprocessClassifier``."""

    name: str

    @abstractmethod
    def match(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> bool:
        """Return True when this rule owns ``exc``."""

    @abstractmethod
    def build(
        self, exc: subprocess.CalledProcessError, ctx: SubprocessCtx, detail: str
    ) -> OperatorError:
        """Build the OperatorError for a matched failure."""
