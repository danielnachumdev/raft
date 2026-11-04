"""Alert setup recommendations: catalog + apply; gated by ``disable_tips``."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from raft.core.observe.alerts.registries import AlertRegistries
from raft.core.observe.alerts.service.rules_service import AlertRulesService

from .catalog import AlertRecommendationCatalog


class AlertRecommendations:
    """Default alert-setup suggestions; gated by document ``disable_tips``."""

    def __init__(
        self,
        home: Path,
        *,
        rules: Optional[AlertRulesService] = None,
        registries: Optional[AlertRegistries] = None,
    ) -> None:
        self._home = home
        self._rules = rules or AlertRulesService(home, registries=registries)

    def list_public(self) -> Dict[str, Any]:
        document = self._rules.document()
        if document.disable_tips:
            return {"recommendations": []}
        existing = [r.to_export() for r in document.rules]
        items = [
            item
            for item in AlertRecommendationCatalog.candidates()
            if not AlertRecommendationCatalog.covers(existing, item)
        ]
        return {"recommendations": items}

    def dismiss(self, recommendation_id: str) -> Dict[str, Any]:
        del recommendation_id
        return self.list_public()

    def apply(self, recommendation_id: str) -> Dict[str, Any]:
        item = self._require(recommendation_id)
        rule = self._rules.create(item["rule"])
        return {
            "rule": rule.to_public(),
            "recommendations": self.list_public()["recommendations"],
        }

    def _require(self, recommendation_id: str) -> Dict[str, Any]:
        for item in AlertRecommendationCatalog.candidates():
            if item["id"] == recommendation_id:
                return item
        raise KeyError(recommendation_id)

    def preview_ids(self) -> List[str]:
        return [item["id"] for item in AlertRecommendationCatalog.candidates()]
