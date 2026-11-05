"""Permission codes ``{resource}:{read|write}`` (+ action wildcards)."""

from enum import StrEnum


class Action(StrEnum):
    READ = "read"
    WRITE = "write"


WILDCARD_READ = "*:read"
WILDCARD_WRITE = "*:write"

# Serve / SPA surfaces that participate in RBAC (#307).
RBAC_RESOURCES: tuple[str, ...] = (
    "alerts",
    "events",
    "firewall",
    "github",
    "inbox",
    "logs",
    "metrics",
    "notifications",
    "rbac",
    "runtime",
    "service",
    "settings",
    "status",
    "update",
)


class PermissionCodes:
    """Parse and match permission code strings."""

    @classmethod
    def catalog(cls) -> tuple[str, ...]:
        codes: list[str] = [WILDCARD_READ, WILDCARD_WRITE]
        for resource in RBAC_RESOURCES:
            codes.append(f"{resource}:{Action.READ}")
            codes.append(f"{resource}:{Action.WRITE}")
        return tuple(codes)

    @staticmethod
    def is_valid(code: str) -> bool:
        if code in (WILDCARD_READ, WILDCARD_WRITE):
            return True
        parts = code.rsplit(":", 1)
        if len(parts) != 2:
            return False
        resource, action = parts
        return bool(resource) and action in (Action.READ, Action.WRITE)

    @staticmethod
    def matches(granted: str, required: str) -> bool:
        if granted == required:
            return True
        if granted == WILDCARD_READ and required.endswith(f":{Action.READ}"):
            return True
        if granted == WILDCARD_WRITE and required.endswith(f":{Action.WRITE}"):
            return True
        return False

    @classmethod
    def allows(cls, granted: frozenset[str], required: str) -> bool:
        return any(cls.matches(code, required) for code in granted)
