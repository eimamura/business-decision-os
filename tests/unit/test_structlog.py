from __future__ import annotations

"""Unit tests for structured logging output.

Verifies that the structlog configuration used by the agent runtime and
orchestrator produces valid JSON with the expected structured fields.
"""

import json
import io
import logging

import pytest
import structlog
import structlog.testing


def _configure_structlog_for_test() -> None:
    """Configure structlog to use JSONRenderer for test assertions."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


class TestStructlogJsonOutput:
    """structlog outputs valid JSON with required fields."""

    def test_basic_log_produces_valid_json(self) -> None:
        """A structlog call with JSON renderer produces parseable JSON."""
        cap = io.StringIO()
        handler = logging.StreamHandler(cap)
        root_logger = logging.getLogger("test_structlog_basic")
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)

        _configure_structlog_for_test()

        log = structlog.get_logger("test_structlog_basic")
        log.info("test_event", session_id="sess-001", agent_role="inventory")

        output = cap.getvalue().strip()
        # There may be multiple lines; take the last non-empty one
        lines = [line for line in output.splitlines() if line.strip()]
        assert lines, "Expected at least one log line"

        parsed = json.loads(lines[-1])
        assert parsed["event"] == "test_event"
        assert parsed["session_id"] == "sess-001"
        assert "timestamp" in parsed

        root_logger.removeHandler(handler)

    def test_bound_fields_appear_in_json_output(self) -> None:
        """Fields bound via .bind() appear as top-level keys in JSON output."""
        cap = io.StringIO()
        handler = logging.StreamHandler(cap)
        root_logger = logging.getLogger("test_structlog_bind")
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)

        _configure_structlog_for_test()

        log = structlog.get_logger("test_structlog_bind").bind(
            session_id="sess-bound-001",
            agent_role="demand",
        )
        log.info("bound_event")

        output = cap.getvalue().strip()
        lines = [line for line in output.splitlines() if line.strip()]
        assert lines

        parsed = json.loads(lines[-1])
        assert parsed["session_id"] == "sess-bound-001"
        assert parsed["agent_role"] == "demand"
        assert parsed["event"] == "bound_event"

        root_logger.removeHandler(handler)

    def test_tool_name_field_captured_in_json(self) -> None:
        """tool_name bound as structured field appears in JSON output."""
        cap = io.StringIO()
        handler = logging.StreamHandler(cap)
        root_logger = logging.getLogger("test_structlog_tool")
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)

        _configure_structlog_for_test()

        log = structlog.get_logger("test_structlog_tool")
        log.info("tool_started", session_id="sess-002", tool_name="sql_query", agent_role="data_engineer")

        output = cap.getvalue().strip()
        lines = [line for line in output.splitlines() if line.strip()]
        assert lines

        parsed = json.loads(lines[-1])
        assert parsed["event"] == "tool_started"
        assert parsed["session_id"] == "sess-002"
        assert parsed["tool_name"] == "sql_query"
        assert parsed["agent_role"] == "data_engineer"

        root_logger.removeHandler(handler)

    def test_structlog_testing_capture_records_events(self) -> None:
        """structlog.testing.capture_logs captures log records in-process."""
        with structlog.testing.capture_logs() as cap:
            log = structlog.get_logger()
            log.info("captured_event", session_id="sess-003", agent_role="replenishment")

        assert len(cap) >= 1
        record = cap[-1]
        assert record["event"] == "captured_event"
        assert record["session_id"] == "sess-003"
        assert record["agent_role"] == "replenishment"
        assert record["log_level"] == "info"
