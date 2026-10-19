"""YAML view/edit helpers for :class:`OperatorSettingsService`."""

from typing import Any, Dict, Mapping

import yaml

from raft.core.core.errors.cta import OperatorError

from .document import SettingsDocument
from .loader import SettingsLoader
from .secrets_merge import SettingsSecretsMerge
from .section_meta import SettingsSectionMeta
from .yaml_dump import SettingsYamlDump


class OperatorSettingsYaml:
    """Encode/decode settings documents as YAML without a second source of truth."""

    def __init__(
        self,
        *,
        loader: SettingsLoader,
        document: SettingsDocument,
        secrets: SettingsSecretsMerge,
        dump: SettingsYamlDump,
        sections: SettingsSectionMeta,
    ) -> None:
        self._loader = loader
        self._document = document
        self._secrets = secrets
        self._dump = dump
        self._sections = sections

    def dump_public(self, cfg) -> str:
        raw = self._secrets.redact_document(self._document.to_raw(cfg))
        return self._dump.dump(raw)

    def encode(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        document = self._extract_document(body)
        cfg = self._loader.from_raw(dict(document))
        raw = self._document.to_raw(cfg)
        return {
            "yaml": self._dump.dump(raw),
            "document": raw,
            "sections": self._sections.for_config(cfg),
        }

    def decode(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        cfg = self._loader.from_raw(self.mapping_from_body(body))
        raw = self._document.to_raw(cfg)
        return {
            "document": raw,
            "sections": self._sections.for_config(cfg),
        }

    def mapping_from_body(self, body: Mapping[str, Any]) -> dict[str, Any]:
        text = self._extract_yaml(body)
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OperatorError(
                f"invalid settings YAML: {exc}\n"
                f"Fix: repair the YAML document then retry Save",
                has_fix=False,
            ) from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise OperatorError(
                "settings YAML must be a mapping (key/value document).\n"
                "Fix: use a full settings.yaml shape with section keys",
                has_fix=False,
            )
        return data

    def _extract_yaml(self, body: Mapping[str, Any]) -> str:
        SettingsDocument.require_mapping(body, path="settings yaml body")
        raw = body.get("yaml", body.get("text"))
        if not isinstance(raw, str) or not raw.strip():
            raise OperatorError(
                "settings YAML body requires a non-empty string field `yaml`.\n"
                "Fix: PUT {\"yaml\": \"logging:\\n  level: INFO\\n…\"}",
                has_fix=False,
            )
        return raw

    def _extract_document(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        SettingsDocument.require_mapping(body, path="settings body")
        if "document" in body:
            return SettingsDocument.require_mapping(
                body["document"], path="settings.document"
            )
        return body
