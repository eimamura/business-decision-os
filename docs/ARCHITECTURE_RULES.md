# ARCHITECTURE_RULES.md

## Purpose

Define what each layer MAY and MUST NOT do.
These rules are the enforcement complement to DESIGN.md's structural description.
When a code review or arch test fails, this file is the authoritative source.

---

## Rule format

Each rule uses one of:
- `MAY` — explicitly permitted (resolves ambiguity)
- `MUST` — required
- `MUST NOT` — forbidden; violation is a defect, not a style issue

---

## Orchestration Layer

**`packages/agent/orchestrator/`**

- Orchestrator MAY route, plan, aggregate results, detect conflicts, score decisions, and generate responses.
- Orchestrator MUST delegate specialized domain analysis to Domain Agents or Analytical Agents.
- Orchestrator MUST NOT own domain-specific calculations, supply chain thresholds, or business rules.
- Orchestrator MUST NOT call the database directly; data access goes through Tools.
- Orchestrator MUST NOT call the LLM provider SDK directly; all LLM calls go through `packages/agent/llm/`.

---

## Agent Layer — Domain Agents

**`packages/agent/specialists/` — domain-scoped agents (demand, inventory, replenishment, procurement, supplier, production, logistics)**

- Domain Agents MAY reason over their domain context and invoke Tools to retrieve data or run calculations.
- Domain Agents MAY hold domain-specific business rules as reasoning input (not as executable code).
- Domain Agents MUST NOT implement data access directly; all reads go through Tool Layer.
- Domain Agents MUST NOT route requests between agents or aggregate multi-domain results.
- Domain Agents MUST NOT call the LLM provider SDK directly.

---

## Agent Layer — Analytical Agents

**`packages/agent/specialists/` — cross-domain agents (exception, scenario, ranking, root_cause)**

- Analytical Agents MAY operate across domain boundaries by invoking Tools.
- Analytical Agents MUST NOT own domain-specific business rules; they consume domain data, not domain logic.
- Analytical Agents MUST NOT route or aggregate in a way that duplicates Orchestrator responsibilities.

---

## Tool Layer

**`packages/tools/`**

- Tools MAY execute data access, calculations, external API calls, simulations, and audit writes.
- Tools MUST expose a clear input/output schema conforming to the `Tool` base class in `packages/tools/base.py`.
- Tools MUST raise `RuntimeError` on missing configuration (API keys, DB connection); never silently degrade to a no-op or stub.
- Tools MUST NOT decide business strategy or routing; they are execution primitives, not decision-makers.
- Tools MUST NOT route requests between agents.
- Tools MUST NOT bypass `LLMClient` to call the provider SDK directly.

---

## Memory Layer

**`packages/memory/`**

- Memory MUST be accessed through typed store classes: `ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`.
- Agents MUST NOT pass raw dicts as "memory" between components; use the Memory Layer API.
- Agents MUST NOT read or write memory belonging to another agent's domain without going through the Memory Layer API.
- Memory MUST NOT be used solely as raw conversation history; it holds state, context, and decision records.

---

## Guardrail Layer

- All external actions (database writes with business impact, notifications, approval requests) MUST pass through Guardrail before execution.
- Guardrail logic MUST NOT be scattered as ad-hoc `if permission` or `if approval` checks inside Agent or Tool code.
- Guardrail MUST expose a stable API: `can_execute()`, `needs_approval()`, `audit_required()`.
- Agents MUST surface low-confidence or high-risk decisions to Guardrail; never silently degrade or self-approve.
- Approval rows in terminal states (`approved`, `rejected`, `needs_revision`, `expired`) MUST NOT be mutated by any layer.

---

## Cross-cutting Rules

These apply everywhere, regardless of layer:

| Rule | Rationale |
|------|-----------|
| Only `packages/agent/llm/` may call the LLM provider SDK | Centralizes rate limiting, cost tracking, and failover |
| Only `packages/tools/` and `packages/persistence/` may hold SQLAlchemy models or execute queries | Prevents hidden data access paths |
| `data/sample/ground_truth/` MUST NOT be read by any agent or tool | Test-data isolation |
| Public interfaces (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) MUST NOT change without an ADR | Preserves integration contracts |
| No smart stubs: stubs MUST conform to schema, not approximate real behavior | Prevents false-passing tests |
| No fail-silent fallbacks: missing config raises `RuntimeError` at the call site | Prevents silent degradation in production |

---

## What These Rules Do NOT Govern

- Internal naming conventions within a file (style guide concern)
- Number of files or classes within a layer (implementation detail)
- Test structure (see TESTING.md)
- Migration order (see MIGRATION_PLAN.md)
- Which decisions are deferred (see DEFERRED.md)
