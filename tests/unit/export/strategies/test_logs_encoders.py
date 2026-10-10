"""Logs txt/json encoders."""

from __future__ import annotations

import json

from raft.export.attachment import ExportAttachment
from raft.export.strategies.logs_json import LogsJsonExporter
from raft.export.strategies.logs_txt import LogsTxtExporter

from tests.unit.base import RaftTestCase

_PAYLOAD = {"service": "site", "tail": 20, "text": "line1\nline2\n"}


class TestLogsTxtExporter(RaftTestCase):
    def test_encodes_utf8_text_with_trailing_newline(self) -> None:
        body = LogsTxtExporter().encode(_PAYLOAD)
        assert body == b"line1\nline2\n"

    def test_empty_and_non_dict_payloads(self) -> None:
        assert LogsTxtExporter().encode({"text": ""}) == b""
        assert LogsTxtExporter().encode(None) == b""

    def test_adds_newline_when_missing(self) -> None:
        body = LogsTxtExporter().encode({"text": "only"})
        assert body == b"only\n"


class TestLogsJsonExporter(RaftTestCase):
    def test_encodes_lines_array(self) -> None:
        data = json.loads(LogsJsonExporter().encode(_PAYLOAD))
        assert data == {"service": "site", "tail": 20, "lines": ["line1", "line2"]}

    def test_non_dict_payload_is_empty_document(self) -> None:
        data = json.loads(LogsJsonExporter().encode("nope"))
        assert data == {"service": "", "tail": 0, "lines": []}


class TestExportAttachment(RaftTestCase):
    def test_filename_sanitizes_service_stem(self) -> None:
        name = ExportAttachment.filename("raft-logs-demo/web", "txt")
        assert name == "raft-logs-demo-web.txt"
