"""Fire component: ``raft notifications …`` (channel CRUD + test-send)."""

from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.catalogs import NotificationCatalogs
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.core.observe.notify.tester import NotificationsTester

from .notifications_io import NotificationsCliIo
from .notifications_output import NotificationsCliOutput


class NotificationsCLI:
    """Manage ``notifications:`` channels in ``~/.raft/settings.yaml``.

    Same redaction and ``notifications.lock`` as Settings → Notifications.
    Test-send uses the shared ``NotificationsTester`` (serve API too).
    """

    def __init__(
        self,
        stack: Stack,
        *,
        registry: Optional[NotificationRegistry] = None,
        writer: Optional[NotificationsSettingsWriter] = None,
        tester: Optional[NotificationsTester] = None,
    ) -> None:
        self._stack = stack
        self._registry = registry or NotificationCatalogs.default()
        self._writer = writer or NotificationsSettingsWriter(
            stack.root, registry=self._registry
        )
        self._tester = tester or NotificationsTester(
            stack.root, registry=self._registry
        )
        self._out = NotificationsCliOutput()
        self._io = NotificationsCliIo()

    def list(self, json: bool = False) -> None:
        """List channels (secrets redacted as ``***``)."""
        payload = self._writer.list_public()
        if json:
            self._out.say_json(payload)
            return
        self._out.list_table(
            list(payload.get("channels") or []),
            enabled=bool(payload.get("enabled", True)),
        )

    def show(self, channel_id: str, json: bool = False) -> None:
        """Show one channel (secrets redacted)."""
        try:
            payload = self._writer.get_public(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        if json:
            self._out.say_json(payload)
            return
        self._out.say_yaml(payload)

    def strategies(self, json: bool = False) -> None:
        """List registered strategy types (catalog for forms / create)."""
        payload = {"strategies": self._registry.catalog()}
        if json:
            self._out.say_json(payload)
            return
        self._out.strategies_table(list(payload["strategies"]))

    def create(self, file: str) -> None:
        """Create a channel from a YAML/JSON file.

        Example::

            raft notifications create --file ops-webhook.yaml
        """
        path = self._io.require_file(file, command="create")
        created = self._writer.create(self._io.read_mapping(path))
        self._out.say(f"Created channel {created['id']} (type={created['type']}).")
        self._out.say_yaml(created)

    def update(self, channel_id: str, file: str) -> None:
        """Update a channel from a YAML/JSON patch file.

        Example::

            raft notifications update ops-webhook --file patch.yaml
        """
        path = self._io.require_file(file, command="update")
        try:
            updated = self._writer.update(channel_id, self._io.read_mapping(path))
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        self._out.say(f"Updated channel {updated['id']}.")
        self._out.say_yaml(updated)

    def delete(self, channel_id: str) -> None:
        """Delete a channel from ``settings.yaml``."""
        try:
            self._writer.delete(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        self._out.say(f"Deleted channel {channel_id}.")

    def enable(self, channel_id: str) -> None:
        """Enable a channel."""
        self._set_enabled(channel_id, True)

    def disable(self, channel_id: str) -> None:
        """Disable a channel."""
        self._set_enabled(channel_id, False)

    def test(self, channel_id: str, json: bool = False) -> None:
        """Send a safe probe through one channel (same as serve Send test).

        Example::

            raft notifications test ops-webhook
        """
        try:
            deliveries = self._tester.send(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        payload = self._tester.public_response(deliveries)
        if json:
            self._out.say_json(payload)
        else:
            self._out.print_deliveries(deliveries)
            self._out.say(payload["message"])
        ok = any(d.result.status == DeliveryStatus.SUCCESS for d in deliveries)
        if not ok:
            raise SystemExit(1)

    def _set_enabled(self, channel_id: str, enabled: bool) -> None:
        try:
            self._writer.update(channel_id, {"enabled": enabled})
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        verb = "Enabled" if enabled else "Disabled"
        self._out.say(f"{verb} channel {channel_id}.")

    @staticmethod
    def _missing(channel_id: str) -> OperatorError:
        return OperatorError(
            f"notification channel {channel_id!r} not found.\n"
            f"Fix: raft notifications list",
            has_fix=False,
        )
