from __future__ import annotations

import logging

import asyncpg

from packages.persistence.context_log import ContextLogRepository
from packages.persistence.db import get_pool
from packages.schemas.context_packs import GENERIC_PACK, USE_CASE_PACKS, ContextPack

_log = logging.getLogger(__name__)

# Keywords per use case for MVP classification.
# Order matters — first match wins.  More specific keywords are listed first.
_USE_CASE_KEYWORDS: dict[str, list[str]] = {
    "Q3": ["exception", "today", "human judgment", "requires attention", "what needs",
           "action required", "needs attention", "priority today", "alerts"],
    "Q6": ["supply shortage", "face shortage", "supply shortfall", "next week", "next month",
           "supply gap", "supply adequacy", "not enough supply", "future shortage"],
    "Q1": ["stockout", "at risk", "run out", "stock out",
           "running low", "inventory risk", "will we run out", "shortage risk"],
    "Q2": ["excess", "overstock", "surplus", "too much inventory", "excess inventory",
           "too much stock", "overstocked"],
    "Q4": ["delay", "unshipped", "late shipment", "shipment delay", "delivery delay",
           "behind schedule", "not shipped", "past due"],
    "Q5": ["forecast gap", "forecast deviation", "actual vs", "vs actual", "why is forecast",
           "actual vs forecast", "off vs", "over-forecast", "under-forecast", "forecast accuracy"],
    "Q7": ["production plan", "overproduction", "underproduction", "production adjustment",
           "plan adjustment", "capacity mismatch"],
    "Q8": [
        "purchase", "buy earlier", "push out", "order timing",
        "purchased earlier", "purchased later",
    ],
    "Q9": ["demand shift", "customer demand", "region demand", "demand change",
           "shift in demand", "regional demand", "customer sales"],
    "Q10": ["constraint", "bottleneck", "binding", "biggest impact", "limiting",
            "capacity constraint", "throughput"],
}


class ContextBuilder:
    """Classify user input to a SPEC use case and return the appropriate ContextPack.

    MVP: keyword-based classification.  First-match-wins over _USE_CASE_KEYWORDS.
    Falls back to GENERIC_PACK when no keyword matches.
    """

    async def build(
        self,
        intent: str,
        user_input: str,
        session_id: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> ContextPack:
        """Return the ContextPack for the given intent and user input.

        Args:
            intent: Resolved intent category (e.g. "supply_chain", "domain_analysis").
            user_input: The user's raw message text.
            session_id: Optional session ID; when provided together with conn, the
                selected ContextPack is logged to the context_log table.

        Returns:
            ContextPack with required_tools, prohibited_tools, skill_keys, routing_hint.
        """
        lowered = user_input.lower()
        use_case_id = self._classify(lowered)
        pack = USE_CASE_PACKS.get(use_case_id, GENERIC_PACK)

        _log.debug(
            "ContextBuilder: use_case=%s intent=%s required_tools=%s prohibited_tools=%s",
            pack.use_case_id,
            intent,
            pack.required_tools,
            pack.prohibited_tools,
        )

        if session_id is not None:
            if conn is not None:
                # Test injection path: use the provided connection directly.
                try:
                    await ContextLogRepository().create(
                        session_id=session_id,
                        use_case_id=pack.use_case_id,
                        intent=intent,
                        required_tools=pack.required_tools,
                        prohibited_tools=pack.prohibited_tools,
                        context_pack_json=pack.model_dump(),
                        conn=conn,
                    )
                except Exception:
                    _log.warning("ContextBuilder: failed to log context pack", exc_info=True)
            else:
                # Production path: acquire a connection from the pool.
                # The pool may not be initialized in unit tests — catch all exceptions,
                # log WARNING, and never raise (fail-open).
                try:
                    pool = await get_pool()
                    async with pool.acquire() as _acquired:
                        await ContextLogRepository().create(
                            session_id=session_id,
                            use_case_id=pack.use_case_id,
                            intent=intent,
                            required_tools=pack.required_tools,
                            prohibited_tools=pack.prohibited_tools,
                            context_pack_json=pack.model_dump(),
                            conn=_acquired,
                        )
                except Exception:
                    _log.warning("ContextBuilder: failed to log context pack", exc_info=True)

        return pack

    def _classify(self, lowered_input: str) -> str:
        """Return the use_case_id (Q1–Q10) or 'GENERIC' for the given lowercased input."""
        for use_case_id, keywords in _USE_CASE_KEYWORDS.items():
            if any(kw in lowered_input for kw in keywords):
                return use_case_id
        return "GENERIC"
