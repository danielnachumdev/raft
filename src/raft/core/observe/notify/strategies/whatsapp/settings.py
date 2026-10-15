"""WhatsApp (GREEN-API) channel settings validation."""

from typing import Any, Mapping

from raft.core.core.errors.cta import OperatorError

DEFAULT_TIMEOUT_SECONDS = 10.0


class WhatsAppSettings:
    """Validate and read GREEN-API sendMessage settings."""

    def validate(self, settings: Mapping[str, Any]) -> None:
        self.require_https_url(settings, "apiUrl")
        self.require_id_instance(settings)
        self.require_token(settings)
        self.require_chat_id(settings)
        self.assert_timeout(settings)

    @staticmethod
    def require_https_url(settings: Mapping[str, Any], key: str) -> str:
        url = str(settings.get(key) or "").strip()
        if not url:
            raise OperatorError(
                f"whatsapp settings.{key} is required.\n"
                f"Fix: set {key}: https://api.green-api.com",
                has_fix=False,
            )
        if not url.lower().startswith("https://"):
            raise OperatorError(
                f"whatsapp settings.{key} must use https://.\n"
                f"Fix: set {key}: https://api.green-api.com",
                has_fix=False,
            )
        return url

    @staticmethod
    def require_id_instance(settings: Mapping[str, Any]) -> str:
        raw = settings.get("idInstance")
        if raw is None or str(raw).strip() == "":
            raise OperatorError(
                "whatsapp settings.idInstance is required.\n"
                "Fix: set idInstance from the GREEN-API console",
                has_fix=False,
            )
        return str(raw).strip()

    @staticmethod
    def require_token(settings: Mapping[str, Any]) -> str:
        token = settings.get("apiTokenInstance")
        if token is None or str(token).strip() == "":
            raise OperatorError(
                "whatsapp settings.apiTokenInstance is required.\n"
                "Fix: set apiTokenInstance from the GREEN-API console",
                has_fix=False,
            )
        if not isinstance(token, str):
            raise OperatorError(
                "whatsapp settings.apiTokenInstance must be a string.\n"
                "Fix: set apiTokenInstance as a string value",
                has_fix=False,
            )
        return token.strip()

    @staticmethod
    def require_chat_id(settings: Mapping[str, Any]) -> str:
        chat_id = str(settings.get("chatId") or "").strip()
        if not chat_id or "@" not in chat_id:
            raise OperatorError(
                "whatsapp settings.chatId must be a WhatsApp chat id "
                "(e.g. 79001234567@c.us or group@g.us).\n"
                "Fix: set chatId: 79001234567@c.us",
                has_fix=False,
            )
        return chat_id

    @staticmethod
    def assert_timeout(settings: Mapping[str, Any]) -> None:
        if "timeoutSeconds" not in settings or settings["timeoutSeconds"] is None:
            return
        try:
            value = float(settings["timeoutSeconds"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                "whatsapp settings.timeoutSeconds must be a number.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            ) from exc
        if value <= 0:
            raise OperatorError(
                "whatsapp settings.timeoutSeconds must be > 0.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            )

    @staticmethod
    def timeout(settings: Mapping[str, Any]) -> float:
        raw = settings.get("timeoutSeconds")
        if raw is None:
            return DEFAULT_TIMEOUT_SECONDS
        return float(raw)

    @staticmethod
    def send_url(settings: Mapping[str, Any]) -> str:
        api = str(settings["apiUrl"]).strip().rstrip("/")
        instance = str(settings["idInstance"]).strip()
        token = str(settings["apiTokenInstance"]).strip()
        return f"{api}/waInstance{instance}/sendMessage/{token}"
