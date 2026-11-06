"""RbacAdmission subjects / allows / allowlist lines."""

from raft.core.core.rbac.admission import RbacAdmission
from raft.core.core.rbac.document import RbacDocument
from tests.unit.base import RaftTestCase

_DOC = {
    "version": 1,
    "roles": [
        {"id": "admin", "permissions": ["*:read", "*:write"]},
        {"id": "empty", "permissions": []},
        {"id": "viewer", "permissions": ["status:read"]},
    ],
    "bindings": [
        {"subject": "ops@example.com", "role": "admin"},
        {"subject": "Ops@Example.com", "role": "admin"},
        {"subject": "empty@example.com", "role": "empty"},
        {"subject": "viewer@example.com", "role": "viewer"},
    ],
}


class TestRbacAdmission(RaftTestCase):
    def test_subjects_require_at_least_one_permission(self) -> None:
        doc = RbacDocument.from_mapping(_DOC, path="host/rbac.yaml")
        subjects = RbacAdmission.subjects(doc)
        assert subjects == ("ops@example.com", "viewer@example.com")
        assert RbacAdmission.allows(doc, "ops@example.com")
        assert RbacAdmission.allows(doc, "VIEWER@example.com")
        assert not RbacAdmission.allows(doc, "empty@example.com")
        assert not RbacAdmission.allows(doc, None)
        assert RbacAdmission.lines_for_allowlist(doc) == list(subjects)
