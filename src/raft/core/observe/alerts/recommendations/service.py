"""Alert setup recommendations: catalog + dismiss + apply."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from raft.core.core.models.state.recommendation_dismissals import AlertDismissalStore
from raft.core.observe.alerts.registries import AlertRegistries
from raft.core.observe.alerts.service.rules_service import AlertRulesService

from .catalog import AlertRecommendationCatalog


class AlertRecommendations:
    """Default alert-setup suggestions with dismiss persistence."""

    def __init__(
        self,
        home: Path,
        *,
        rules: Optional[AlertRulesService] = None,
        registries: Optional[AlertRegistries] = None,
    ) -> None:
        self._home = home
        self._dismissals = AlertDismissalStore(home)
        self._rules = rules or AlertRulesService(home, registries=registries)

    def list_public(self) -> Dict[str, Any]:
        dismissed = self._dismissals.list_ids()
        existing = [r.to_export() for r in self._rules.document().rules]
        items = [
            item
            for item in AlertRecommendationCatalog.candidates()
            if item["id"] not in dismissed
            and not AlertRecommendationCatalog.covers(existing, item)
        ]
        return {"recommendations": items}

    def dismiss(self, recommendation_id: str) -> Dict[str, Any]:
        self._dismissals.dismiss(recommendation_id)
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
