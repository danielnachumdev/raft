"""Host RBAC: permission catalog, document schema, and enforcer (#307)."""

from .admission import RbacAdmission
from .binding import RbacBinding
from .builtin import ADMIN_ROLE_ID, BuiltinAdminRole
from .decision import RbacDecision
from .document import RbacDocument
from .enforcer import RbacEnforcer
from .http_gate import RbacHttpGate
from .identity import (
    NONE_BOOTSTRAP_SUBJECT,
    PASSWORD_BOOTSTRAP_SUBJECT,
    RbacIdentity,
)
from .permissions import (
    WILDCARD_READ,
    WILDCARD_WRITE,
    Action,
    PermissionCodes,
    RBAC_RESOURCES,
)
from .role import RbacRole
from .subject import RbacSubject

__all__ = [
    "ADMIN_ROLE_ID",
    "Action",
    "BuiltinAdminRole",
    "NONE_BOOTSTRAP_SUBJECT",
    "PASSWORD_BOOTSTRAP_SUBJECT",
    "PermissionCodes",
    "RBAC_RESOURCES",
    "RbacAdmission",
    "RbacBinding",
    "RbacDecision",
    "RbacDocument",
    "RbacEnforcer",
    "RbacHttpGate",
    "RbacIdentity",
    "RbacRole",
    "RbacSubject",
    "WILDCARD_READ",
    "WILDCARD_WRITE",
]
