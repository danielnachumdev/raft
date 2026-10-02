"""TraceContext scope, nesting, and TraceIdFilter."""

from __future__ import annotations

import logging
import re
from io import StringIO
from unittest.mock import patch

from raft.config.logging import TraceIdFilter
from raft.config.trace_context import TraceContext

from ..base import RaftTestCase

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class TestTraceContextScope(RaftTestCase):
    def teardown_method(self) -> None:
        assert TraceContext.current() is None

    def test_root_scope_sets_current_and_clears_on_exit(self) -> None:
        assert TraceContext.current() is None
        with TraceContext() as tid:
            assert _UUID_RE.match(tid)
            assert TraceContext.current() == tid
        assert TraceContext.current() is None

    def test_nested_child_changes_current_and_restores_parent(self) -> None:
        with TraceContext() as parent:
            assert TraceContext.current() == parent
            with TraceContext(parent) as child:
                assert _UUID_RE.match(child)
                assert child != parent
                assert TraceContext.current() == child
            assert TraceContext.current() == parent

    def test_current_available_without_passing_tid_as_argument(self) -> None:
        def read_active():
            return TraceContext.current()

        with TraceContext() as tid:
            assert read_active() == tid

    def test_child_with_parent_emits_debug_branch_log(self) -> None:
        with patch("raft.config.trace_context.logger.debug") as debug:
            with TraceContext() as parent:
                with TraceContext(parent) as child:
                    pass
        debug.assert_called_once()
        args, _kwargs = debug.call_args
        message = args[0] % args[1:]
        assert parent in message
        assert child in message
        assert "branch" in message.lower()

    def test_exit_without_enter_is_noop(self) -> None:
        ctx = TraceContext()
        assert ctx.__exit__(None, None, None) is None
        assert TraceContext.current() is None


class TestTraceIdFilter(RaftTestCase):
    def test_injects_dash_outside_scope(self) -> None:
        record = logging.LogRecord(
            name="raft.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="outside",
            args=(),
            exc_info=None,
        )
        assert TraceIdFilter().filter(record) is True
        assert record.tid == "-"  # type: ignore[attr-defined]

    def test_injects_active_tid_inside_scope(self) -> None:
        record = logging.LogRecord(
            name="raft.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="inside",
            args=(),
            exc_info=None,
        )
        with TraceContext() as tid:
            assert TraceIdFilter().filter(record) is True
            assert record.tid == tid  # type: ignore[attr-defined]

    def test_formatter_includes_tid_on_emitted_line(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(TraceIdFilter())
        handler.setFormatter(logging.Formatter("%(tid)s %(message)s"))
        log = logging.getLogger("raft.test.tid.format")
        log.handlers.clear()
        log.propagate = False
        log.setLevel(logging.INFO)
        log.addHandler(handler)
        try:
            with TraceContext() as tid:
                log.info("correlated")
            log.info("uncorrelated")
        finally:
            log.handlers.clear()
        text = stream.getvalue()
        assert f"{tid} correlated" in text
        assert "- uncorrelated" in text
