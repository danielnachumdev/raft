"""Docker / Compose classifiers and message builders."""

from typing import Optional

from .cta import CtaFormatter
from .operator_error import OperatorError

__all__ = ["DockerMessages"]


class DockerMessages:
    """Docker daemon / compose / nginx CTA text and classifiers."""

    @staticmethod
    def looks_like_docker_daemon_down(exc: BaseException) -> bool:
        text = CtaFormatter.exc_blob(exc)
        return (
            "cannot connect to the docker daemon" in text
            or "is the docker daemon running" in text
            or "permission denied while trying to connect to the docker api" in text
        )

    @staticmethod
    def looks_like_port_in_use(exc: BaseException) -> bool:
        text = CtaFormatter.exc_blob(exc)
        return (
            "address already in use" in text
            or "port is already allocated" in text
            or "bind: address already in use" in text
        )

    @staticmethod
    def looks_like_image_missing(exc: BaseException) -> bool:
        text = CtaFormatter.exc_blob(exc)
        return (
            "not found" in text
            or "manifest unknown" in text
            or "no such image" in text
            or "pull access denied" in text
        )

    @staticmethod
    def docker_daemon_message(*, detail: str = "") -> str:
        return CtaFormatter.format(
            "cannot talk to the Docker daemon.",
            (
                "start Docker (e.g. sudo systemctl start docker)",
                "ensure your user is in the docker group, then re-login",
                "raft doctor",
            ),
            detail=detail,
            tag="docker",
        )

    @staticmethod
    def port_in_use_message(*, detail: str = "") -> str:
        return CtaFormatter.format(
            "a published port is already in use on this VPS.",
            (
                "stop the other process, or change edge ports in ~/.raft/host/settings.yaml",
                "raft redeploy gate   # after edge port changes",
                "raft doctor",
            ),
            detail=detail,
            tag="docker",
        )

    @staticmethod
    def compose_failure_message(
        action: str,
        *,
        detail: str = "",
        hint: str = "",
    ) -> str:
        return CtaFormatter.format(
            f"docker compose failed while trying to {action}.",
            (
                "raft doctor",
                "docker compose -f ~/.raft/compose.yaml ps",
                "docker compose -f ~/.raft/compose.yaml logs --tail=80 gate router",
            ),
            detail=detail,
            tag="docker",
            hint=hint,
        )

    @staticmethod
    def docker_pull_failure_message(
        image: str,
        *,
        detail: str = "",
        app: Optional[str] = None,
    ) -> str:
        svc = app or "<app-name>"
        return CtaFormatter.format(
            f"docker pull failed for {image!r}.",
            (
                "docker login <registry>   # if the image is private",
                f"raft sync {svc}",
                "raft doctor",
            ),
            detail=detail,
            tag="docker",
        )

    @staticmethod
    def docker_failure_message(
        action: str,
        *,
        detail: str = "",
        hint: str = "",
    ) -> str:
        return CtaFormatter.format(
            f"docker failed while trying to {action}.",
            ("raft doctor", "docker ps -a"),
            detail=detail,
            tag="docker",
            hint=hint,
        )

    @staticmethod
    def nginx_rejected_message(role: str, detail: str = "") -> str:
        headline = f"{role} nginx rejected the config."
        if detail.strip():
            return f"{headline}\n{detail.strip()}\nFix: raft render && raft doctor"
        return f"{headline}\nFix: raft render && raft doctor"

    @staticmethod
    def nginx_reload_failed_message(role: str, detail: str = "") -> str:
        if role == "gate":
            fix = "Fix: raft redeploy gate"
        else:
            fix = "Fix: docker compose -f ~/.raft/compose.yaml restart router"
        body = f"{role} nginx config was valid but reload failed.\n"
        if detail.strip():
            body += f"{detail.strip()}\n"
        return body + fix

    @classmethod
    def nginx_rejected(cls, role: str, detail: str = "") -> OperatorError:
        return OperatorError(cls.nginx_rejected_message(role, detail))

    @classmethod
    def nginx_reload_failed(cls, role: str, detail: str = "") -> OperatorError:
        return OperatorError(cls.nginx_reload_failed_message(role, detail))
