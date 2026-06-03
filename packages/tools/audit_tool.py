from __future__ import annotations

from typing import Any, Literal

from packages.persistence.audit_log_repo import compute_hash
from packages.tools.base import ToolContext, ToolResult

_audit_store: list[dict[str, Any]] = []


class AuditLogTool:
    name = "write_audit_log"
    description = "Write a tamper-evident audit log entry"
    safety_level: Literal["read_only", "write", "hitl"] = "write"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "event_type": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["event_type", "payload"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "audit_hash": {"type": "string"},
            "recorded": {"type": "boolean"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        prev_hash = _audit_store[-1]["audit_hash"] if _audit_store else None
        payload = input.get("payload", {})
        audit_hash = compute_hash(payload, prev_hash)

        record: dict[str, Any] = {
            "audit_hash": audit_hash,
            "prev_hash": prev_hash,
            "event_type": input.get("event_type", ""),
            "payload": payload,
            "session_id": str(ctx.session_id),
        }
        _audit_store.append(record)

        return ToolResult(
            output={"audit_hash": audit_hash, "recorded": True},
            audit_payload={"audit_hash": audit_hash, "event_type": input.get("event_type", "")},
        )
