"""Read/replace the full operator ``settings.yaml`` document for serve/CLI."""

import os
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from raft.core.core.config.paths import RaftHome
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import SettingsLock

from .document import SettingsDocument
from .loader import SettingsLoader
from .operator_yaml import OperatorSettingsYaml
from .secrets_merge import SettingsSecretsMerge
from .section_meta import SettingsSectionMeta
from .side_effects import SettingsSideEffects
from .types import RaftConfig
from .yaml_dump import SettingsYamlDump


class OperatorSettingsService:
    """Validate via section parsers; persist under ``settings.lock``."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._path = RaftHome().settings_path(data_home)
        self._loader = SettingsLoader()
        self._document = SettingsDocument()
        self._secrets = SettingsSecretsMerge()
        self._effects = SettingsSideEffects()
        self._yaml_dump = SettingsYamlDump()
        self._sections = SettingsSectionMeta()
        self._yaml = OperatorSettingsYaml(
            loader=self._loader,
            document=self._document,
            secrets=self._secrets,
            dump=self._yaml_dump,
            sections=self._sections,
        )

    def get_public(self) -> Dict[str, Any]:
        cfg = self._loader.load(self._home)
        return self._response(cfg, notes=self._effects.for_get(cfg))

    def get_yaml_public(self) -> Dict[str, Any]:
        cfg = self._loader.load(self._home)
        payload = self._response(cfg, notes=self._effects.for_get(cfg))
        payload["yaml"] = self._yaml.dump_public(cfg)
        return payload

    def replace(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with SettingsLock(self._home):
            before = self._loader.load(self._home)
            document = self._extract_document(body)
            after = self._parse_merged(document, prior=before)
            self._persist(after)
            notes = self._effects.for_replace(before=before, after=after)
            return self._response(after, notes=notes)

    def replace_yaml(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        return self.replace({"document": self._yaml.mapping_from_body(body)})

    def encode_yaml(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        return self._yaml.encode(body)

    def decode_yaml(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        return self._yaml.decode(body)

    def _response(self, cfg: RaftConfig, *, notes: list) -> Dict[str, Any]:
        raw = self._document.to_raw(cfg)
        return {
            "path": str(self._path),
            "document": self._secrets.redact_document(raw),
            "sections": self._sections.for_config(cfg),
            "notes": notes,
        }

    def _extract_document(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        SettingsDocument.require_mapping(body, path="settings body")
        if "document" in body:
            return SettingsDocument.require_mapping(
                body["document"], path="settings.document"
            )
        return body

    def _parse_merged(
        self, document: Mapping[str, Any], *, prior: RaftConfig
    ) -> RaftConfig:
        parsed = self._loader.from_raw(dict(document))
        return RaftConfig(
            logging=parsed.logging,
            edge=parsed.edge,
            healing=parsed.healing,
            metrics=parsed.metrics,
            service_logs=parsed.service_logs,
            acme=parsed.acme,
            github=self._secrets.github(parsed.github, prior.github),
            notifications=self._secrets.notifications(
                parsed.notifications, prior.notifications
            ),
            alerts=parsed.alerts,
            dashboard=self._secrets.dashboard(parsed.dashboard, prior.dashboard),
        )

    def _persist(self, cfg: RaftConfig) -> None:
        root = self._load_root()
        for key, value in self._document.to_raw(cfg).items():
            root[key] = value
        root.pop("acl", None)  # retired flat ACL; firewall SoT only
        self._write_root(root)

    def _load_root(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot update settings.yaml: {self._path}\n"
                f"Fix: repair ~/.raft/host/settings.yaml then retry",
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml must be a YAML mapping.\n"
                "Fix: repair ~/.raft/host/settings.yaml",
                has_fix=False,
            )
        return raw

    def _write_root(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._yaml_dump.dump(data), encoding="utf-8")
        os.chmod(self._path, 0o600)
