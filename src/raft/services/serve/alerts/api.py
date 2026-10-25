"""FastAPI handlers for alert rules CRUD + dry-run + status."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts import (
    AlertEngine,
    AlertRecommendations,
    AlertRulesService,
    AlertStatusView,
)
from raft.core.observe.alerts.catalog import AlertCatalog
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.service.rules_service import RuleConflict
from raft.core.observe.alerts.service.tester import AlertTester
from raft.core.observe.notify.delivery_status import DeliveryStatus


class ServeAlertsApi:
    """Localhost JSON API over ``host/alerts/rules.yaml``."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[AlertRulesService] = None,
        registries=None,
    ) -> None:
        self.stack = stack
        self._regs = registries or AlertCatalogs.default()
        self._service = service or AlertRulesService(stack.root, registries=self._regs)
        self._engine = AlertEngine(stack.root, registries=self._regs)
        self._recommendations = AlertRecommendations(
            stack.root, rules=self._service, registries=self._regs
        )

    def register(self, app) -> None:
        app.get("/api/alerts/rules")(self.api_list)
        app.get("/api/alerts/rules/{rule_id}")(self.api_get)
        app.post("/api/alerts/rules")(self.api_create)
        app.put("/api/alerts/rules/{rule_id}")(self.api_replace)
        app.post("/api/alerts/rules/{rule_id}/enabled")(self.api_enabled)
        app.delete("/api/alerts/rules/{rule_id}")(self.api_delete)
        app.post("/api/alerts/validate")(self.api_validate)
        app.post("/api/alerts/dry-run")(self.api_dry_run)
        app.post("/api/alerts/rules/{rule_id}/test")(self.api_test)
        app.get("/api/alerts/status")(self.api_status)
        app.get("/api/alerts/catalog")(self.api_catalog)
        app.get("/api/alerts/export")(self.api_export)
        app.post("/api/alerts/import")(self.api_import)
        app.get("/api/alerts/recommendations")(self.api_recommendations)
        app.post("/api/alerts/recommendations/{recommendation_id}/dismiss")(
            self.api_dismiss_recommendation
        )
        app.post("/api/alerts/recommendations/{recommendation_id}/apply")(
            self.api_apply_recommendation
        )

    def api_list(self) -> Dict[str, Any]:
        return self._service.document().to_public()

    def api_get(self, rule_id: str) -> Dict[str, Any]:
        try:
            return self._service.get(rule_id).to_public()
        except KeyError as exc:
            raise self._missing(rule_id) from exc

    def api_create(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._service.create(body).to_public()
        except RuleConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_replace(
        self, rule_id: str, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._service.replace(rule_id, body).to_public()
        except KeyError as exc:
            raise self._missing(rule_id) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_enabled(
        self, rule_id: str, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._service.set_enabled(
                rule_id, bool(body.get("enabled"))
            ).to_public()
        except KeyError as exc:
            raise self._missing(rule_id) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_delete(self, rule_id: str) -> Dict[str, Any]:
        try:
            self._service.delete(rule_id)
        except KeyError as exc:
            raise self._missing(rule_id) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc
        return {"ok": True, "deleted": rule_id}

    def api_validate(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        if "document" in body:
            return self._service.validate_document(body["document"]).to_public()
        return self._service.validate_rule(body.get("rule")).to_public()

    def api_dry_run(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            if "ruleId" in body:
                rule = self._service.get(str(body["ruleId"]))
            else:
                rule = self._service._parser.parse(body.get("rule") or {}, path="rule")
            return self._engine.dry_run(rule).to_public()
        except KeyError as exc:
            raise self._missing(str(body.get("ruleId"))) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_test(self, rule_id: str) -> Dict[str, Any]:
        try:
            deliveries = AlertTester(self.stack.root).send(rule_id)
        except KeyError as exc:
            raise self._missing(rule_id) from exc
        return self._test_response(deliveries)

    @staticmethod
    def _test_response(deliveries) -> Dict[str, Any]:
        rows = [
            {
                "channel_id": d.channel_id,
                "type_id": d.type_id,
                "status": d.result.status.value,
                "error": d.result.error,
            }
            for d in deliveries
        ]
        ok = any(d.result.status == DeliveryStatus.SUCCESS for d in deliveries)
        message = ServeAlertsApi._test_message(deliveries)
        return {"ok": ok, "deliveries": rows, "message": message}

    @staticmethod
    def _test_message(deliveries) -> str:
        if not deliveries:
            return "No deliverable channels"
        sent = sum(1 for d in deliveries if d.result.status == DeliveryStatus.SUCCESS)
        return f"Test sent to {sent} of {len(deliveries)} channels"

    def api_status(self) -> Dict[str, Any]:
        return AlertStatusView(self.stack.root).build()

    def api_catalog(self) -> Dict[str, Any]:
        apps = [a.name for a in self.stack.apps]
        return AlertCatalog.build(self._regs, apps)

    def api_export(self) -> Dict[str, Any]:
        return self._service.export_document()

    def api_import(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            summary = self._service.apply_document(
                body.get("document") or {}, prune=bool(body.get("prune"))
            )
            return summary.to_public()
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_recommendations(self) -> Dict[str, Any]:
        return self._recommendations.list_public()

    def api_dismiss_recommendation(self, recommendation_id: str) -> Dict[str, Any]:
        return self._recommendations.dismiss(recommendation_id)

    def api_apply_recommendation(self, recommendation_id: str) -> Dict[str, Any]:
        try:
            return self._recommendations.apply(recommendation_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"alert recommendation '{recommendation_id}' not found. "
                    f"Fix: GET /api/alerts/recommendations"
                ),
            ) from exc
        except RuleConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    @staticmethod
    def _missing(rule_id: str) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail=(
                f"alert rule '{rule_id}' not found. Fix: GET /api/alerts/rules"
            ),
        )

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
