"""Persist ``host/rbac.yaml`` under settings flock (#307 temp override)."""

from pathlib import Path
from typing import Any, Dict, Mapping

from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.temporary_override import TemporaryOverrideWarn
from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.store import RbacStore
from raft.core.platform.locking import SettingsLock


class RbacDocumentWriter:
    """Validate + write RBAC document (temporary host override)."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._store = RbacStore(data_home)

    def get(self) -> Dict[str, Any]:
        doc = self._store.load()
        if doc is None:
            return RbacDocument.empty().to_export()
        return doc.to_export()

    def put(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with SettingsLock(self._home):
            document = RbacDocument.from_mapping(body, path="host/rbac.yaml")
            self._store.save(document)
            return {
                "document": document.to_export(),
                "gitops": {
                    "temporary_override": TemporaryOverrideWarn.write_message(
                        GitopsDocKind.RBAC
                    )
                },
            }
