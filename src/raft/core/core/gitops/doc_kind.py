"""GitOps host-config document kinds (#310 / #317)."""

from enum import Enum


class GitopsDocKind(str, Enum):
    """Flat GitOps docs reconciled onto the host."""

    SETTINGS = "settings"
    FIREWALL = "firewall"
    ALERTS = "alerts"
    NOTIFICATIONS = "notifications"
    RBAC = "rbac"
