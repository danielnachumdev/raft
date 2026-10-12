"""Raw SMTP transport for email delivery (no product vocabulary)."""

import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Optional

SmtpFactory = Callable[[str, int, float], Any]


class SmtpGateway:
    """Open SMTP, optional STARTTLS/login, send one message."""

    def __init__(self, *, factory: Optional[SmtpFactory] = None) -> None:
        self._factory = factory or self._default_smtp

    def send(
        self,
        host: str,
        port: int,
        timeout: float,
        message: EmailMessage,
        *,
        username: str = "",
        password: str = "",
        start_tls: bool = True,
    ) -> None:
        with self._factory(host, port, timeout) as smtp:
            if start_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)

    @staticmethod
    def _default_smtp(host: str, port: int, timeout: float) -> Any:
        return smtplib.SMTP(host, port, timeout=timeout)
