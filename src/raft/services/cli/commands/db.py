"""Fire component: ``raft db`` (SQLite durable-state foundation)."""

from typing import Optional

from raft.core.core.db import DurableDbService
from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay


class DbCLI:
    """Schema upgrade and migrate-from-files for ``raft.sqlite`` (#317)."""

    def __init__(
        self, stack: Stack, *, service: Optional[DurableDbService] = None
    ) -> None:
        self._stack = stack
        self._service = service or DurableDbService(stack.root)

    def migrate(self, force: bool = False) -> None:
        """Create/upgrade ``raft.sqlite`` and import core files into tables.

        Imports settings, apps registry, deploy pins, and firewall (idempotent
        unless ``--force``). PEMs, secrets bodies, and ``generated/`` stay on
        disk. Files remain the live SoT until cutover (#320).

        Example::

            raft db migrate
            raft db migrate --force
        """
        result = self._service.migrate_from_files(force=force)
        self._print_result(result)

    def status(self) -> None:
        """Show SQLite path and Alembic revision for this data home."""
        path = self._service.db_path()
        revision = self._service.schema_revision()
        OperatorSay.say(f"db: {path}")
        OperatorSay.say(f"revision: {revision or '(none — run raft db migrate)'}")
        OperatorSay.say(f"exists: {path.is_file()}")

    @staticmethod
    def _print_result(result) -> None:
        if result.already_done:
            OperatorSay.say(f"db migrate already complete ({result.db_path})")
            return
        OperatorSay.say(
            f"db migrate → {result.db_path} "
            f"(settings={result.settings_imported}, "
            f"apps={result.apps_imported}, "
            f"firewall_rules={result.firewall_rules_imported})"
        )
