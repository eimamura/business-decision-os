# ADR: Eval-Driven Context Engineering — Activate ContextBuilder

- Date: 2026-06-13
- Status: Accepted (supersedes: §Escalation Trigger in docs/adr/2026-06-13-context-engineering-prompt-builder.md)
- Phases: P112, P113, P114, P115
- Decision owner: User (approved 2026-06-13)

## Context

The P100 judge campaign measured response quality across all 10 SPEC questions and
revealed context pollution as the primary failure mode: 7 of 10 questions produced
duplicate tool calls, and 8 of 10 exceeded the `num_ctx` limit of 16,384 tokens.

The prior ADR (`2026-06-13-context-engineering-prompt-builder.md`) deferred a
`ContextBuilder` class until **any two** of the following became true: user permissions
changing the tool subset, screen state injected into the prompt, RAG retrieval feeding
a prompt section, or conversation summary injected as a prompt section (not as messages).

The P100 failure data re-frames the escalation trigger. The real threshold is not "have
two out of four architectural features landed?" but rather "do we have measurable evidence
that static intent-level tool selection causes quality degradation?" — and we do. The
judge campaign produces exactly that evidence: defect D-013 (FP-012 duplicate-call
pattern) is directly attributable to the tool set being too wide at the intent level.
`supply_chain` always includes 20+ tools, and the LLM selects wrong or repeated tools
under context pressure. The prior trigger criteria were one framing of when the
engineering overhead is justified; the eval-driven framing is more direct and better
aligned with the project's quality-measurement discipline.

## Decision

Activate `ContextBuilder` now. The refactor introduces the following across P112–P115:

1. **Formal golden cases per SPEC question** as the authoritative quality definition
   (P112) — `data/evals/spec10_golden_cases.yaml`
2. **ContextPack typed schemas per use case** — `required_tools`, `prohibited_tools`,
   `skill_keys` declared in `packages/schemas/context_packs.py` (P113)
3. **ContextBuilder** that classifies user input to a specific use case and narrows the
   tool set passed to `control_agent.py` via `tool_subset_override` (P113)
4. **Context trace logging** for post-hoc failure analysis (P114)
5. **Automated eval runner** making quality measurement repeatable and comparable across
   iterations (P115)

## Rationale

The core insight is that static intent-level tool selection keeps the full
`_INTENT_TOOL_SUBSET` (20+ tools for `supply_chain`) in the LLM's context at all times.
Under context pressure — especially when `num_ctx` is tight — the LLM's tool selection
degrades: it calls wrong tools (e.g. `list_stockout_risk` for a forward supply adequacy
question) or repeats the same call to fill a perceived coverage gap.

Use-case-level selection directly addresses defect D-013 (root cause FP-012):

- Q6 ("forward supply shortage next week") gets only `nl_query` — not `list_stockout_risk`,
  which answers a different question (on-hand risk, not forward adequacy).
- Q9 ("demand changes by customer/region") gets only `detect_demand_shift` — not
  `segment_demand` or `compare_demand_periods`, which operate on the SKU axis.

Narrowing the tool set per use case eliminates the ambiguity that triggers duplicate
calls and reduces per-call token count, directly addressing the `num_ctx` overflow.

The prior escalation triggers (user permissions, screen state, RAG, conversation summary)
remain valid architectural signals for future `ContextBuilder` extensions. They were
not wrong; they were one framing of when the indirection is justified. The eval-driven
framing — "do the golden cases and failure classification show a quality defect attributable
to context selection?" — is more direct and measurable, and it triggered first.

## Consequences

- `_INTENT_TOOL_SUBSET` remains the pool from which `ContextBuilder` selects a
  per-use-case subset; it is not removed.
- `ContextBuilder` is MVP keyword-based; vector similarity matching over the user's
  input is Post-MVP.
- The eval runner (P115) measures whether `ContextBuilder` improves routing accuracy
  against the golden cases in `spec10_golden_cases.yaml`.
- The prior ADR's `render_*` functions are preserved; `ContextBuilder` determines WHAT
  to include in context, while the `render_*` functions determine HOW to render it as
  prompt text.
- The `§Escalation Trigger` section of the prior ADR is superseded by this decision;
  the remaining sections of the prior ADR remain in effect.
