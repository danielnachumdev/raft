"""Parse ``edge:`` (http/https/streams) from settings.yaml."""

from __future__ import annotations

from typing import Any, Optional

from raft.errors import OperatorError

from .settings_types import STREAM_PROTOCOLS, EdgeConfig, EdgeStream


class EdgeSettingsParser:
    """Validate and build :class:`EdgeConfig` from a settings mapping."""

    def parse(self, raw: Any) -> EdgeConfig:
        if raw is None:
            return EdgeConfig()
        if not isinstance(raw, dict):
            raise OperatorError("settings.yaml edge must be a mapping", has_fix=False)
        http = self._optional_port(raw.get("http", 80), field_name="http")
        https = self._optional_port(raw.get("https", 443), field_name="https")
        streams = self._parse_streams(raw.get("streams", []), http=http, https=https)
        return EdgeConfig(http=http, https=https, streams=tuple(streams))

    def _parse_streams(
        self,
        streams_raw: Any,
        *,
        http: Optional[int],
        https: Optional[int],
    ) -> list[EdgeStream]:
        if streams_raw is None:
            streams_raw = []
        if not isinstance(streams_raw, list):
            raise OperatorError("settings.yaml edge.streams must be a list", has_fix=False)
        return self._parse_stream_list(streams_raw, http=http, https=https)

    def _parse_stream_list(
        self, streams_raw: list, *, http: Optional[int], https: Optional[int]
    ) -> list[EdgeStream]:
        streams: list[EdgeStream] = []
        seen_names: set[str] = set()
        seen_ports: set[int] = set()
        for index, entry in enumerate(streams_raw):
            streams.append(
                self._parse_stream_entry(
                    entry,
                    index=index,
                    http=http,
                    https=https,
                    seen_names=seen_names,
                    seen_ports=seen_ports,
                )
            )
        return streams

    def _parse_stream_entry(
        self,
        entry: Any,
        *,
        index: int,
        http: Optional[int],
        https: Optional[int],
        seen_names: set[str],
        seen_ports: set[int],
    ) -> EdgeStream:
        if not isinstance(entry, dict):
            raise OperatorError(
                f"settings.yaml edge.streams[{index}] must be an object",
                has_fix=False,
            )
        name = self._stream_name(entry, index=index, seen_names=seen_names)
        port = self._stream_port(entry, name=name, http=http, https=https, seen_ports=seen_ports)
        protocol = str(entry.get("protocol", "tcp")).strip().lower() or "tcp"
        if protocol not in STREAM_PROTOCOLS:
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].protocol must be one of "
                f"{sorted(STREAM_PROTOCOLS)}, got {protocol!r}",
                has_fix=False,
            )
        return EdgeStream(name=name, port=port, protocol=protocol)

    @staticmethod
    def _stream_name(entry: dict, *, index: int, seen_names: set[str]) -> str:
        name = str(entry.get("name", "")).strip()
        if not name:
            raise OperatorError(
                f"settings.yaml edge.streams[{index}].name is required",
                has_fix=False,
            )
        if name in seen_names:
            raise OperatorError(
                f"settings.yaml edge.streams: duplicate name {name!r}",
                has_fix=False,
            )
        seen_names.add(name)
        return name

    @staticmethod
    def _stream_port(
        entry: dict,
        *,
        name: str,
        http: Optional[int],
        https: Optional[int],
        seen_ports: set[int],
    ) -> int:
        port = EdgeSettingsParser._coerce_stream_port(entry, name=name)
        EdgeSettingsParser._check_stream_port_conflicts(
            port, name=name, http=http, https=https, seen_ports=seen_ports
        )
        seen_ports.add(port)
        return port

    @staticmethod
    def _coerce_stream_port(entry: dict, *, name: str) -> int:
        if "port" not in entry:
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].port is required",
                has_fix=False,
            )
        try:
            port = int(entry["port"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].port must be an integer "
                f"(1–65535), got {entry['port']!r}.\n"
                f"Fix: use a numeric port in edge.streams[] in ~/.raft/settings.yaml"
            ) from exc
        if not (1 <= port <= 65535):
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].port out of range: {port}.\n"
                f"Fix: pick a port between 1 and 65535 in ~/.raft/settings.yaml"
            )
        return port

    @staticmethod
    def _check_stream_port_conflicts(
        port: int,
        *,
        name: str,
        http: Optional[int],
        https: Optional[int],
        seen_ports: set[int],
    ) -> None:
        if port in seen_ports:
            raise OperatorError(
                f"settings.yaml edge.streams: duplicate port {port}",
                has_fix=False,
            )
        if http is not None and port == http:
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].port {port} conflicts with edge.http",
                has_fix=False,
            )
        if https is not None and port == https:
            raise OperatorError(
                f"settings.yaml edge.streams[{name!r}].port {port} conflicts with edge.https",
                has_fix=False,
            )

    @staticmethod
    def _optional_port(raw: Any, *, field_name: str) -> Optional[int]:
        if raw is None:
            return None
        try:
            port = int(raw)
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml edge.{field_name} must be an integer port (1–65535) "
                f"or null, got {raw!r}.\n"
                f"Fix: set edge.{field_name} to a number (e.g. 80) or omit/null "
                f"in ~/.raft/settings.yaml"
            ) from exc
        if not (1 <= port <= 65535):
            raise OperatorError(
                f"settings.yaml edge.{field_name} out of range: {port}.\n"
                f"Fix: pick a port between 1 and 65535 in ~/.raft/settings.yaml"
            )
        return port
