"""Safe per-channel delivery outcome."""

from dataclasses import dataclass

from .delivery_status import DeliveryStatus


@dataclass(frozen=True)
class DeliveryResult:
    """Safe per-channel outcome. ``error`` must never carry raw secrets."""

    status: DeliveryStatus
    error: str = ""

    @classmethod
    def success(cls) -> "DeliveryResult":
        return cls(DeliveryStatus.SUCCESS)

    @classmethod
    def skipped(cls, reason: str = "") -> "DeliveryResult":
        return cls(DeliveryStatus.SKIPPED, error=reason)

    @classmethod
    def failed(cls, error: str) -> "DeliveryResult":
        return cls(DeliveryStatus.FAILED, error=error)
