"""Per-channel outcome after a dispatcher pass."""

from dataclasses import dataclass

from .delivery_result import DeliveryResult


@dataclass(frozen=True)
class ChannelDelivery:
    """Outcome for one channel after a dispatch pass."""

    channel_id: str
    type_id: str
    result: DeliveryResult
