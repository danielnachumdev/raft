"""Short TTL + single-flight coalesce for serve ``/api/status`` payloads."""

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

# Under SPA STATUS_POLL_MS (2s) so overlapping polls share one collect.
DEFAULT_STATUS_PAYLOAD_TTL_SECONDS = 1.0


class StatusPayloadCache:
    """In-process cache: brief TTL plus waiters sharing one in-flight load."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_STATUS_PAYLOAD_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self._payload: Optional[Dict[str, Any]] = None
        self._expires_at = 0.0
        self._flight: Optional[Tuple[threading.Event, Dict[str, Any]]] = None

    def get_or_load(self, loader: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            if self._payload is not None and self._clock() < self._expires_at:
                return self._payload
            wait, event, box = self._claim_or_join_locked()
        if wait:
            return self._await_flight(event, box)
        return self._run_loader(loader, event, box)

    def clear(self) -> None:
        with self._lock:
            self._payload = None
            self._expires_at = 0.0

    def _claim_or_join_locked(
        self,
    ) -> Tuple[bool, threading.Event, Dict[str, Any]]:
        if self._flight is not None:
            return True, self._flight[0], self._flight[1]
        event = threading.Event()
        box: Dict[str, Any] = {}
        self._flight = (event, box)
        return False, event, box

    def _await_flight(
        self, event: threading.Event, box: Dict[str, Any]
    ) -> Dict[str, Any]:
        event.wait()
        error = box.get("error")
        if error is not None:
            raise error
        payload = box.get("payload")
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("status payload flight finished without a payload")

    def _run_loader(
        self,
        loader: Callable[[], Dict[str, Any]],
        event: threading.Event,
        box: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            payload = loader()
            with self._lock:
                self._payload = payload
                self._expires_at = self._clock() + self._ttl_seconds
                box["payload"] = payload
            return payload
        except Exception as exc:
            with self._lock:
                box["error"] = exc
            raise
        finally:
            with self._lock:
                self._flight = None
            event.set()
