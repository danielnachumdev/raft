"""Named host-job flight / FIFO kinds (lock path segments)."""


class HostJobKinds:
    """Stable kind strings for ``FifoLock`` / ``HostOneshotFlight``."""

    DASHBOARD_REDEPLOY = "redeploy-dashboard"
    UPDATE = "update"
