"""SSH key layout and config-file management for raft deploy keys."""

from __future__ import annotations

import os
import re
from pathlib import Path

from raft.errors import OperatorError

from ...adapters.shell import Shell
from .urls import default_ssh_dir

_BEGIN = "# BEGIN raft:{name}"
_END = "# END raft:{name}"


class SshDeployKeys:
    """Own ``~/.ssh/raft`` keys and Host blocks in ``~/.ssh/config``."""

    def __init__(self, shell: Shell) -> None:
        self.sh = shell
        self.ssh_dir = default_ssh_dir()
        self.keys_dir = self.ssh_dir / "raft"
        self.config_path = self.ssh_dir / "config"

    def key_path(self, service: str) -> Path:
        return self.keys_dir / f"{service}_ed25519"

    def pub_path(self, service: str) -> Path:
        return Path(str(self.key_path(service)) + ".pub")

    def is_configured(self, service: str) -> bool:
        return self.key_path(service).is_file() and self.pub_path(service).is_file()

    def list_services(self) -> list[str]:
        if not self.keys_dir.is_dir():
            return []
        names: list[str] = []
        for pub in sorted(self.keys_dir.glob("*_ed25519.pub")):
            name = pub.name[: -len("_ed25519.pub")]
            if self.key_path(name).is_file():
                names.append(name)
        return names

    def ensure_layout(self) -> None:
        self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.ssh_dir, 0o700)
        self.keys_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.keys_dir, 0o700)
        if not self.config_path.exists():
            self.config_path.touch(mode=0o600)
        os.chmod(self.config_path, 0o600)

    def ensure_key(self, service: str, *, force: bool, title: str) -> None:
        if self.is_configured(service) and not force:
            return
        if force and self.is_configured(service):
            self.key_path(service).unlink(missing_ok=True)
            self.pub_path(service).unlink(missing_ok=True)
        self._generate_key(service, comment=title)

    def _generate_key(self, service: str, *, comment: str) -> None:
        try:
            self.sh.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-f",
                    str(self.key_path(service)),
                    "-N",
                    "",
                    "-C",
                    comment,
                    "-q",
                ],
                capture=True,
            )
        except Exception as exc:
            raise OperatorError(
                f"ssh-keygen failed while creating a deploy key for {service!r}.\n"
                f"Fix: install openssh-client, ensure ~/.ssh/raft is writable, "
                f"then: raft auth setup {service}"
            ) from exc
        os.chmod(self.key_path(service), 0o600)
        os.chmod(self.pub_path(service), 0o644)

    def upsert_ssh_config(self, service: str, *, alias: str, hostname: str) -> None:
        self.ensure_layout()
        block = self._host_block(service, alias=alias, hostname=hostname)
        text = self._strip_block(self.config_path.read_text(encoding="utf-8"), service)
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        self.config_path.write_text(text + block, encoding="utf-8")
        os.chmod(self.config_path, 0o600)

    def _host_block(self, service: str, *, alias: str, hostname: str) -> str:
        return "\n".join(
            [
                _BEGIN.format(name=service),
                f"Host {alias}",
                f"  HostName {hostname}",
                "  User git",
                f"  IdentityFile {self.key_path(service)}",
                "  IdentitiesOnly yes",
                _END.format(name=service),
                "",
            ]
        )

    def remove_ssh_config(self, service: str) -> None:
        if not self.config_path.is_file():
            return
        text = self._strip_block(self.config_path.read_text(encoding="utf-8"), service)
        self.config_path.write_text(text, encoding="utf-8")
        os.chmod(self.config_path, 0o600)

    def remove_key_files(self, service: str) -> None:
        self.key_path(service).unlink(missing_ok=True)
        self.pub_path(service).unlink(missing_ok=True)

    @staticmethod
    def _strip_block(text: str, service: str) -> str:
        begin = _BEGIN.format(name=service)
        end = _END.format(name=service)
        pattern = re.compile(
            re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
            re.DOTALL,
        )
        return pattern.sub("", text)
