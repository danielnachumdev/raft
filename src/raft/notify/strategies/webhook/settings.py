"""Webhook channel settings validation."""

from typing import Any, Mapping

from ....errors.cta import OperatorError

DEFAULT_TIMEOUT_SECONDS = 10.0


class WebhookSettings:
    """Validate and read webhook strategy settings."""

    def validate(self, settings: Mapping[str, Any]) -> None:
        url = self.require_url(settings)
        self.assert_https(url, settings)
        self.assert_timeout(settings)
        self.assert_headers(settings)

    @staticmethod
    def require_url(settings: Mapping[str, Any]) -> str:
        url = str(settings.get("url") or "").strip()
        if not url:
            raise OperatorError(
                "webhook settings.url is required.\n"
                "Fix: set settings.url to an https://hooks.example.invalid/… URL",
                has_fix=False,
            )
        return url

    @staticmethod
    def assert_https(url: str, settings: Mapping[str, Any]) -> None:
        if url.lower().startswith("https://"):
            return
        if url.lower().startswith("http://") and bool(settings.get("allowInsecureHttp")):
            return
        raise OperatorError(
            "webhook settings.url must use https:// "
            "(or set allowInsecureHttp: true for lab http:// only).\n"
            "Fix: use https://hooks.example.invalid/raft",
            has_fix=False,
        )

    @staticmethod
    def assert_timeout(settings: Mapping[str, Any]) -> None:
        if "timeoutSeconds" not in settings or settings["timeoutSeconds"] is None:
            return
        try:
            value = float(settings["timeoutSeconds"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                "webhook settings.timeoutSeconds must be a number.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            ) from exc
        if value <= 0:
            raise OperatorError(
                "webhook settings.timeoutSeconds must be > 0.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            )

    @staticmethod
    def assert_headers(settings: Mapping[str, Any]) -> None:
        headers = settings.get("headers")
        if headers is None:
            return
        if not isinstance(headers, Mapping):
            raise OperatorError(
                "webhook settings.headers must be a mapping of string to string.\n"
                "Fix: set headers: {Authorization: Bearer …}",
                has_fix=False,
            )
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise OperatorError(
                    "webhook settings.headers values must be strings.\n"
                    "Fix: use string header names and values only",
                    has_fix=False,
                )

    @staticmethod
    def timeout(settings: Mapping[str, Any]) -> float:
        raw = settings.get("timeoutSeconds")
        if raw is None:
            return DEFAULT_TIMEOUT_SECONDS
        return float(raw)

    @staticmethod
    def headers(settings: Mapping[str, Any]) -> dict:
        headers = settings.get("headers") or {}
        return {str(k): str(v) for k, v in dict(headers).items()}
