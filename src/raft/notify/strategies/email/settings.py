"""Email channel settings validation."""

from typing import Any, Mapping

from ....errors.cta import OperatorError

DEFAULT_PORT = 587
DEFAULT_TIMEOUT_SECONDS = 10.0


class EmailSettings:
    """Validate and read email strategy settings."""

    def validate(self, settings: Mapping[str, Any]) -> None:
        self.require_address(settings, "to")
        self.require_address(settings, "from")
        self.require_host(settings)
        self.assert_port(settings)
        self.assert_timeout(settings)
        self.assert_auth(settings)

    @staticmethod
    def require_address(settings: Mapping[str, Any], key: str) -> str:
        value = str(settings.get(key) or "").strip()
        if not value or "@" not in value:
            raise OperatorError(
                f"email settings.{key} must be an address "
                f"(e.g. ops@example.com).\n"
                f"Fix: set settings.{key}: ops@example.com",
                has_fix=False,
            )
        return value

    @staticmethod
    def require_host(settings: Mapping[str, Any]) -> str:
        host = str(settings.get("smtpHost") or "").strip()
        if not host:
            raise OperatorError(
                "email settings.smtpHost is required.\n"
                "Fix: set smtpHost: smtp.example.com",
                has_fix=False,
            )
        return host

    @staticmethod
    def assert_port(settings: Mapping[str, Any]) -> None:
        if "smtpPort" not in settings or settings["smtpPort"] is None:
            return
        try:
            port = int(settings["smtpPort"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                "email settings.smtpPort must be an integer.\n"
                "Fix: set smtpPort: 587",
                has_fix=False,
            ) from exc
        if not 1 <= port <= 65535:
            raise OperatorError(
                "email settings.smtpPort must be 1–65535.\n"
                "Fix: set smtpPort: 587",
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
                "email settings.timeoutSeconds must be a number.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            ) from exc
        if value <= 0:
            raise OperatorError(
                "email settings.timeoutSeconds must be > 0.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            )

    @staticmethod
    def assert_auth(settings: Mapping[str, Any]) -> None:
        username = str(settings.get("username") or "").strip()
        password = settings.get("password")
        if username and password is None:
            raise OperatorError(
                "email settings.password is required when username is set.\n"
                "Fix: set password (redacted in serve API)",
                has_fix=False,
            )
        if password is not None and not isinstance(password, str):
            raise OperatorError(
                "email settings.password must be a string.\n"
                "Fix: set password as a string value",
                has_fix=False,
            )

    @staticmethod
    def port(settings: Mapping[str, Any]) -> int:
        raw = settings.get("smtpPort")
        return DEFAULT_PORT if raw is None else int(raw)

    @staticmethod
    def timeout(settings: Mapping[str, Any]) -> float:
        raw = settings.get("timeoutSeconds")
        return DEFAULT_TIMEOUT_SECONDS if raw is None else float(raw)

    @staticmethod
    def truthy(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
