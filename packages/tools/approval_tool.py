from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from packages.tools.base import ToolContext, ToolResult

_approval_store: dict[str, dict[str, Any]] = {}


class ApprovalTool:
    name = "request_approval"
    description = "Request human approval for a proposed action"
    requires_approval = True
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action_summary": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["action_summary"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "approval_id": {"type": "string"},
            "status": {"type": "string"},
            "expires_at": {"type": "string"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        approval_id = str(uuid4())
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=86400)).isoformat()

        record: dict[str, Any] = {
            "approval_id": approval_id,
            "status": "pending",
            "expires_at": expires_at,
            "session_id": str(ctx.session_id),
            "action_summary": input.get("action_summary", ""),
        }
        _approval_store[approval_id] = record

        return ToolResult(
            output={
                "approval_id": approval_id,
                "status": "pending",
                "expires_at": expires_at,
            },
            audit_payload={
                "approval_id": approval_id,
                "action_summary": input.get("action_summary", ""),
            },
        )
