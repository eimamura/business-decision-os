from __future__ import annotations

# HITLPause was removed in T-066.
# HITL is now implemented via LangGraph interrupt() in AgentRuntime.
# The prepare_hitl → wait_for_approval → execute_tools graph nodes replace
# the old exception-based approach.
