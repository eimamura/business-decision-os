from __future__ import annotations

"""Integration tests for the HITL end-to-end flow.

These tests require a live server and are marked @pytest.mark.e2e.
They are skipped in unit/CI runs.
"""

import pytest


@pytest.mark.e2e
async def test_hitl_session_transitions_to_awaiting_approval() -> None:
    """Create a session that triggers a hitl tool; assert status becomes awaiting_approval."""
    # Scaffold — requires running server
    pass


@pytest.mark.e2e
async def test_hitl_approve_transitions_to_completed() -> None:
    """Approve a pending HITL approval; assert session transitions to completed."""
    # Scaffold — requires running server
    pass


@pytest.mark.e2e
async def test_hitl_reject_transitions_to_failed() -> None:
    """Reject a pending HITL approval; assert session transitions to failed."""
    # Scaffold — requires running server
    pass
