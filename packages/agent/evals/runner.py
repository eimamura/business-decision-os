from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from packages.agent.evals.eval_case import EvalCase, load_eval_cases

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    passed: bool
    tools_called: list[str]
    missing_required_tools: list[str]
    prohibited_tools_called: list[str]
    response_text: str
    assertion_hits: list[str]
    assertion_misses: list[str]
    must_not_contain_violations: list[str]
    failure_type: str | None


# ---------------------------------------------------------------------------
# Assertion helper
# ---------------------------------------------------------------------------


def check_assertions(
    response_text: str,
    case: EvalCase,
) -> tuple[list[str], list[str], list[str]]:
    """Check response_text against case assertions.

    Returns:
        (assertion_hits, assertion_misses, must_not_contain_violations)
    """
    lower = response_text.lower()

    assertion_hits: list[str] = []
    assertion_misses: list[str] = []
    for pattern in case.response_assertions.must_contain:
        if pattern.lower() in lower:
            assertion_hits.append(pattern)
        else:
            assertion_misses.append(pattern)

    must_not_contain_violations: list[str] = []
    for pattern in case.response_assertions.must_not_contain:
        if pattern.lower() in lower:
            must_not_contain_violations.append(pattern)

    return assertion_hits, assertion_misses, must_not_contain_violations


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def classify_failure(result: EvalResult) -> str | None:
    """Classify the failure type for an EvalResult.

    Returns None if the result passed.  First-match taxonomy:
      routing    — wrong tool called AND required tool missed
      pollution  — wrong tool called, but required tool was also called
      retrieval  — required tool not called at all
      reasoning  — degenerate response pattern (must_not_contain violation) or fallback
      output     — tools correct but response content wrong
    """
    if result.passed:
        return None

    has_prohibited = bool(result.prohibited_tools_called)
    has_missing = bool(result.missing_required_tools)

    if has_prohibited and has_missing:
        return "routing"

    if has_prohibited:
        return "pollution"

    if has_missing:
        return "retrieval"

    if result.must_not_contain_violations:
        return "reasoning"

    if result.assertion_misses:
        return "output"

    # Fallback: tools were called but response still wrong
    return "reasoning"


# ---------------------------------------------------------------------------
# Stub result for unreachable API
# ---------------------------------------------------------------------------


def _stub_result(case: EvalCase) -> EvalResult:
    missing = list(case.required_tools)
    result = EvalResult(
        case_id=case.id,
        passed=False,
        tools_called=[],
        missing_required_tools=missing,
        prohibited_tools_called=[],
        response_text="",
        assertion_hits=[],
        assertion_misses=list(case.response_assertions.must_contain),
        must_not_contain_violations=[],
        failure_type=None,
    )
    # Classify and return with the failure_type filled in
    failure_type = classify_failure(result)
    return EvalResult(**{**result.model_dump(), "failure_type": failure_type})


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_POLL_INTERVAL_S = 2.0
_POLL_TIMEOUT_S = 30.0
_TERMINAL_EVENT_TYPES = {"done", "awaiting_input", "error"}


class EvalRunner:
    """Runs eval cases against the live dev API and collects EvalResults."""

    def __init__(self, api_base_url: str = "http://localhost:8002") -> None:
        self.api_base_url = api_base_url.rstrip("/")

    def load_cases(self, yaml_path: Path) -> list[EvalCase]:
        """Load and validate evaluation cases from *yaml_path*."""
        return load_eval_cases(yaml_path)

    async def run_case(
        self,
        case: EvalCase,
        client: httpx.AsyncClient,
    ) -> EvalResult:
        """Run a single eval case against the live API and return EvalResult.

        Steps:
          1. POST /api/v1/sessions              → session_id
          2. POST /api/v1/sessions/{id}/messages → starts async processing
          3. Poll GET /api/v1/sessions/{id}/events until a terminal event appears
             or the 30-second timeout fires.
          4. Extract tool names and reply text; build and return EvalResult.

        If the API is unreachable (ConnectError / TimeoutException), returns a
        stub EvalResult with passed=False so the runner can continue in dry-run mode.
        """
        try:
            session_id = await self._create_session(client)
            _log.info("case=%s session=%s — created", case.id, session_id)

            await self._post_message(client, session_id, case.spec_question)
            _log.info("case=%s session=%s — message sent", case.id, session_id)

            events = await self._poll_events(client, session_id)
            _log.info("case=%s session=%s — collected %d events", case.id, session_id, len(events))

            return self._extract_from_events(events, case)

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _log.warning(
                "case=%s — API unreachable (%s); returning stub result",
                case.id,
                exc,
            )
            return _stub_result(case)

    def _extract_from_events(
        self,
        events: list[dict[str, Any]],
        case: EvalCase,
    ) -> EvalResult:
        """Extract tools_called and response_text from session events, then score.

        Events from GET /api/v1/sessions/{id}/events have the shape:
            {"event_type": str, "payload": dict, "created_at": str}

        Tool calls are recorded as graph_node events with kind="tool".
        The final reply is in the "done" event's payload["reply"].
        As a fallback, text_delta payloads are concatenated.
        """
        tools_called: list[str] = []
        response_text = ""
        delta_buffer = ""

        for event in events:
            event_type: str = event.get("event_type", "")
            raw_payload = event.get("payload", {})
            payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}

            match event_type:
                case "graph_node":
                    # Tool calls: kind="tool", event="start" carries the tool name
                    if payload.get("kind") == "tool" and payload.get("event") == "start":
                        tool_name = payload.get("name", "")
                        if tool_name and tool_name not in tools_called:
                            tools_called.append(tool_name)
                case "done":
                    reply = payload.get("reply")
                    if reply:
                        response_text = reply
                case "text_delta":
                    delta_buffer += payload.get("delta", "")
                case _:
                    pass

        # Fall back to accumulated text_delta if done event had no reply
        if not response_text and delta_buffer:
            response_text = delta_buffer

        required = set(case.required_tools)
        prohibited = set(case.must_not_use_tools)
        called_set = set(tools_called)

        missing_required_tools = sorted(required - called_set)
        prohibited_tools_called = sorted(prohibited & called_set)

        assertion_hits, assertion_misses, must_not_contain_violations = check_assertions(
            response_text, case
        )

        passed = (
            not missing_required_tools
            and not prohibited_tools_called
            and not assertion_misses
            and not must_not_contain_violations
        )

        result = EvalResult(
            case_id=case.id,
            passed=passed,
            tools_called=tools_called,
            missing_required_tools=missing_required_tools,
            prohibited_tools_called=prohibited_tools_called,
            response_text=response_text,
            assertion_hits=assertion_hits,
            assertion_misses=assertion_misses,
            must_not_contain_violations=must_not_contain_violations,
            failure_type=None,
        )
        failure_type = classify_failure(result)
        return EvalResult(**{**result.model_dump(), "failure_type": failure_type})

    async def run_all(
        self,
        cases: list[EvalCase],
        client: httpx.AsyncClient,
    ) -> list[EvalResult]:
        """Run all cases sequentially and return the collected results."""
        results: list[EvalResult] = []
        for case in cases:
            result = await self.run_case(case, client)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_session(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.api_base_url}/api/v1/sessions",
            json={"goal": "eval run"},
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return str(data["session_id"])

    async def _post_message(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        content: str,
    ) -> None:
        resp = await client.post(
            f"{self.api_base_url}/api/v1/sessions/{session_id}/messages",
            json={"content": content},
        )
        resp.raise_for_status()

    async def _poll_events(
        self,
        client: httpx.AsyncClient,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Poll the events endpoint until a terminal event is seen or timeout fires."""
        deadline = asyncio.get_event_loop().time() + _POLL_TIMEOUT_S
        while True:
            resp = await client.get(
                f"{self.api_base_url}/api/v1/sessions/{session_id}/events",
                params={"limit": 200},
            )
            resp.raise_for_status()
            events: list[dict[str, Any]] = resp.json()

            # Check for terminal event in the fetched list
            for event in events:
                if event.get("event_type") in _TERMINAL_EVENT_TYPES:
                    return events

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                _log.warning(
                    "session=%s — poll timed out after %.0fs with %d events",
                    session_id,
                    _POLL_TIMEOUT_S,
                    len(events),
                )
                return events

            await asyncio.sleep(min(_POLL_INTERVAL_S, remaining))
