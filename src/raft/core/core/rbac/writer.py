"""Persist ``host/rbac.yaml`` under settings flock (#307 temp override)."""

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.temporary_override import TemporaryOverrideWarn
from raft.core.core.rbac.builtin import BuiltinAdminRole
from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.store import RbacStore
from raft.core.platform.locking import SettingsLock


class RbacDocumentWriter:
    """Validate + write RBAC document (temporary host override)."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._store = RbacStore(data_home)

    def export_document(self) -> Dict[str, Any]:
        doc = self._store.load()
        exported = (doc or RbacDocument.empty()).to_export()
        return BuiltinAdminRole.normalize_mapping(exported)

    def replace(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with SettingsLock(self._home):
            document = RbacDocument.from_mapping(
                BuiltinAdminRole.normalize_mapping(body),
                path="host/rbac.yaml",
            )
            self._store.save(document)
            return {
                "document": document.to_export(),
                "gitops": {
                    "temporary_override": TemporaryOverrideWarn.write_message(
                        GitopsDocKind.RBAC
                    )
                },
            }

    def encode_yaml(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        document = RbacDocument.from_mapping(
            BuiltinAdminRole.normalize_mapping(body),
            path="host/rbac.yaml",
        )
        return {
            "document": document.to_export(),
            "yaml": self._dump(document),
        }

    def decode_yaml(self, text: str) -> Dict[str, Any]:
        raw = self._load_yaml(text)
        document = RbacDocument.from_mapping(
            BuiltinAdminRole.normalize_mapping(raw if isinstance(raw, Mapping) else {}),
            path="host/rbac.yaml",
        )
        return {"document": document.to_export()}

    @staticmethod
    def _dump(document: RbacDocument) -> str:
        return yaml.safe_dump(
            document.to_export(),
            sort_keys=False,
            default_flow_style=False,
        )

    @staticmethod
    def _load_yaml(text: str) -> Any:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OperatorError(
                "RBAC YAML is invalid.\nFix: correct the YAML syntax and retry",
                has_fix=False,
            ) from exc
