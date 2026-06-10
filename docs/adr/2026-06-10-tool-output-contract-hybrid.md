# ADR: Tool Output Contract — Hybrid Resolution of the Context Pack Divergence

Date: 2026-06-10
Status: Accepted
Phase: P76

## Context

DESIGN.md §Tool Design Constraints mandated that every tool return a **Context Pack**
(`summary`, `schema`, `key_metrics`, `missing_data`, `artifact_id`), with raw rows stored
as blob artifacts. The P75 full audit (2026-06-10) found this contract is implemented by
**0 of 35 tools**: every tool returns a domain-specific dict conforming to its declared
`output_schema`; `nl_query` returns up to 100 raw rows directly; `missing_data` is never
populated; two supply-order tools run unbounded queries.

The divergence is total and original — the Context Pack clause was never implemented at
any point in the tool layer's history. Per AGENTS.md §When in Doubt, code is the runtime
truth and docs are the design truth; an ADR must resolve the conflict before either side
changes.

Two concrete harms were identified, both independent of the full Context Pack:

1. **Data-gap ambiguity.** Tools signal absent source data via `None` fields or `error`
   strings. The LLM cannot distinguish "no cost data available" from "no cost impact",
   which is a hallucination vector.
2. **Context flooding.** `get_open_supply_orders` and `get_delayed_supply_orders` have no
   `LIMIT`; a large `supply_orders` table would stream hundreds of rows into the context
   of a local 12B model.

Arguments against full Context Pack implementation now:

- There is a **single consumer** (`ControlAgent`; `VALID_AGENT_ROLES == {"control"}`).
  Tool outputs feed one LangChain tool loop that demonstrably consumes the current dicts
  (795 unit tests green, response quality gates passing).
- Most tools return small scalar dicts that **are** their own key metrics; wrapping them
  adds tokens, not information. `schema` duplicates the declared `output_schema`.
  `summary` requires either templates (no information gain) or extra LLM calls
  (unacceptable latency/cost on local models).
- `artifact_id` requires a blob artifact store that does not exist; building it for a
  problem solved by row caps is disproportionate.

## Decision

**Hybrid (option c).** The domain-dict contract is codified as official; the two real
holes are closed surgically; full Context Pack is deferred behind explicit escalation
criteria.

### 1. Official output contract

A tool returns a **domain-specific dict** that conforms to its declared `output_schema`
(`Tool` Protocol unchanged). The Context Pack 5-field mandate is removed from DESIGN.md
§Tool Design Constraints (T-485).

### 2. `missing_data` requirement (new)

Every DB-accessing tool MUST include `missing_data: list[str]` in its output:

- When a required source (master row, history rows, cost record) is unavailable, append a
  short human-readable entry, e.g. `"no cost_master row for SKU-123"`.
- When all required data was found, the field is present and empty (`[]`).
- `missing_data` describes **data gaps**, not execution failures; connection/query errors
  keep the existing `error` key semantics.

### 3. Row-cap rule (new)

Tools returning row arrays MUST bound them and signal truncation:

- `get_open_supply_orders`, `get_delayed_supply_orders`: add `LIMIT 100` and a
  `truncated: bool` output field (T-479).
- Existing caps are retained as-is (`nl_query` 100-row sanitizer, `list_stockout_risk`
  limit param, demand tools' aggregate outputs). No cap values change in P76.

### 4. Shared helpers module

`_classify_stockout_risk` (duplicated in 2 files with a comment acknowledging the copy)
and `_db_error_message` (~16 copies) move to a shared module under `packages/tools/`
(T-480). Threshold changes must have exactly one edit site.

### 5. DOS → DOI merge

`calculate_days_of_supply` is merged into `calculate_days_of_inventory` (T-483):

- Identical formula (`on_hand / avg_daily_demand`, same 30-day lookback, same reorder
  signal); DOI is the warehouse-aware superset.
- DOI gains the DOS-unique `stockout_date_estimate` output. No capability is lost.
- `supply_days_tool.py` is deleted; registry entry removed; `_INTENT_TOOL_SUBSET` and the
  ControlAgent system prompt reference `calculate_days_of_inventory` instead.

### 6. Escalation criteria — when to revisit full Context Pack

Re-open this decision (new ADR) when ANY of:

- Specialist agents are promoted to runtime units and tool outputs flow between agents
  (standardized inter-agent payloads become valuable).
- Communication/Report tools (Post-MVP) make large-artifact handoff routine.
- A blob artifact store is introduced for any other reason (marginal cost of
  `artifact_id` drops to near zero).

## Consequences

- DESIGN.md §Tool Design Constraints is amended (T-485); the raw-rows prohibition is
  restated as the row-cap rule; the "Context Pack" term is removed from the normative
  constraints.
- 28 DB tools gain a `missing_data` field — additive; existing consumers (ControlAgent
  prompt assembly, tests) are unaffected by an extra key.
- One LLM-visible tool name disappears (`calculate_days_of_supply`). Tests asserting
  subset membership and the AGENT_ARCHITECTURE.md tier table are updated in the same
  phase (T-485, T-486).
- The `Tool` Protocol (public interface) is unchanged; no signature migration.
