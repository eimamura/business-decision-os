# Decision Log

| Date | Decision | Reason | Tradeoff | Status |
|---|---|---|---|---|
| 2026-05-17 | Final-form-first development | Prevents costly retrofits to DB schema, approval flow, audit log, and LLM abstraction | Higher up-front design effort | Accepted |
| 2026-05-17 | LLM provider: Anthropic Claude Sonnet 4.6 | Tool-calling stability and structured output | Vendor lock-in to Anthropic; mitigated by LLMClient abstraction | Accepted |
| 2026-05-17 | Agent runtime: custom lightweight loop on Claude Agent SDK | Full control of state and audit | Self-maintained vs framework community | Accepted |
| 2026-05-17 | Backend: FastAPI (Python, uv) | Aligns with simulation/optimization/ML stack | Less mature than Node/Spring for some integrations | Accepted |
| 2026-05-17 | Frontend: Next.js (npm) | Required for final-form UI scope (chat, dashboards, approval, audit) | Heavier than Streamlit/Gradio | Accepted |
| 2026-05-17 | DB: PostgreSQL + pgvector single store | Transactional consistency across state/audit/memory | Single point of contention at very large scale | Accepted |
| 2026-05-17 | Embeddings: Azure OpenAI text-embedding-3-small (1536d) | Aligned with Azure deploy | Vendor coupling with Azure | Accepted |
| 2026-05-17 | Job queue deferred to Phase 5 | Synchronous execution suffices for MVP | Sync calls block under load | Accepted |
| 2026-05-17 | IaC: Terraform on Azure + Docker Compose locally | Industry-standard cloud IaC; lightweight local dev | Two environments to maintain | Accepted |
| 2026-05-17 | Multi-agent from Day 1 (Orchestrator + 4 Specialists) | Specialist split needed per docs/domain.md for scaling to 10+ specialists | Higher initial complexity than single agent | Accepted |
| 2026-05-17 | Currency: USD system-wide | Standardization for future enterprise reuse | Not aligned with JPY-native users | Accepted |
| 2026-05-17 | Language: English for code/UI/docs/logs; Japanese for AI chat dialogue | Future enterprise reuse + natural-language UX | Mixed-language repo artifacts | Accepted |
| 2026-05-17 | Risk classification (Phase 1): 3-rule OR (>10k USD / >3x avg demand / Critical SKU) | Deterministic and auditable | Rigid; refined in Phase 7 with memory | Accepted |
| 2026-05-17 | Test strategy: pytest + Playwright + vcrpy + temperature=0 + nightly real-API E2E | Deterministic CI; real-API verification offline | Cassette maintenance burden | Accepted |
| 2026-05-17 | Observability: structlog + OpenTelemetry + Langfuse → Azure Monitor / App Insights from Day 1 | Final-form-first applies to observability too | Setup cost before features ship | Accepted |
| 2026-05-17 | Auth as bolt-on exception (Entra ID candidate) | Auth is genuinely low-risk to add later via API middleware | Risk of identity context leakage into business logic if not designed carefully | Accepted |


## Status Values

- Proposed
- Accepted
- Rejected
- Replaced
- Deprecated

---


| 2026-05-17 | Multi-agent split preserved in MVP via PromptBasedSpecialist | Interface fixed Day 1; AgentBasedSpecialist swap deferred to Phase 9 | Shared LLM context limits parallelism in MVP | Accepted |
| 2026-05-17 | Final-form-first means interface preservation, not implementation heaviness | Avoids over-engineering MVP while keeping Phase 9 swap clean | Risk that stub-vs-final divergence is missed; mitigated by schema conformance tests | Accepted |
| 2026-05-17 | Trade-off resolution is Orchestrator-owned | Cross-KPI judgment requires holistic view; Specialists by design have narrow focus | Orchestrator becomes the critical decision path | Accepted |
| 2026-05-17 | Optimizer returns ≥ 3 Pareto-feasible candidates | Single best hides trade-offs; alternatives enable user feedback for learning | More compute and UI surface than single-answer flow | Accepted |
| 2026-05-17 | Evaluator produces per-KPI scores (no collapsed weighted total) | Loss of per-KPI signal breaks trade-off reasoning and visualization | More data per recommendation | Accepted |
| 2026-05-17 | Recommendation always includes primary + ≥ 2 alternatives at different trade-off positions | Gives human approver agency; produces learning signal | UI must visualize multiple candidates | Accepted |
| 2026-05-17 | User policy memory captures weight vector preferences over time | Enables the learning loop in Phase 7 | Memory growth and privacy considerations later | Accepted |
| 2026-05-17 | Phase progression replaces implementations behind stable interfaces (no new modules) | Prevents bolt-on retrofit pain at Phase 9 scale | Higher initial design effort | Accepted |
| 2026-05-17 | Phases 2–9 are reorderable; only Phase 0+1 fixed | Business priority and data availability should drive ordering | Less predictable delivery sequence | Accepted |


| 2026-05-17 | Docker Compose V2 for local dev | V1 is end-of-life | Slight learning curve for those used to legacy CLI | Accepted |
| 2026-05-17 | Git on GitHub Day 1 with Conventional Commits + branch protection | Standard collaboration baseline | Requires GitHub-specific workflow tooling | Accepted |
| 2026-05-17 | GitHub Actions CI/CD with Azure OIDC federated credentials | Eliminates long-lived secrets | OIDC trust must be configured up-front | Accepted |
| 2026-05-17 | Terraform pipeline split (image-build / acr-push / aca / shared / modules) | Decoupled change cadence; isolates stateful infra | More state files to manage | Accepted |
| 2026-05-17 | Azure region: US East 2 | Single deploy region for MVP | Latency penalty for far-region users | Accepted |
| 2026-05-17 | Backup disabled for MVP | Cost optimization; no data is critical | Recovery impossible until trigger met | Accepted |
| 2026-05-17 | Easy teardown: prevent_destroy=false, no resource locks | Enables MVP iteration | Risk of accidental destruction; mitigated by `shared/` isolation | Accepted |
| 2026-05-17 | Secrets via Azure Key Vault + Managed Identity | Zero credential in code or env vars | Requires Azure runtime; local dev uses `.env` | Accepted |
| 2026-05-17 | Single PostgreSQL + pgvector store | Transactional FK spine across audit/state/memory | Single scale ceiling; mitigated by repository swap-in | Accepted |
| 2026-05-17 | Repository pattern in packages/state/ | Swap-in optionality for future DB changes | Slight indirection cost | Accepted |
| 2026-05-17 | Production agent never queries Databricks directly | Decouples operational system from analytics platform | Phase 6 must write features back to PostgreSQL | Accepted |
| 2026-05-17 | Migration 0001 covers Phase 0–9 fields | Prevents additive migrations for new features | Higher up-front schema design effort | Accepted |
| 2026-05-17 | Confidentiality controls independent of backup policy | TLS, firewall, audit chain, no raw LLM context | Maintenance overhead | Accepted |
| 2026-05-17 | Phase 9+ future considerations recorded with explicit triggers | Documentation as decision provenance | Larger DECISIONS surface area | Accepted |


| 2026-05-17 | Web UI stack: Next.js App Router + shadcn/ui + Radix + Tailwind + Recharts + TanStack Query + Zustand + Vercel AI SDK | Final-form UI scope; copy-in components; no lock-in | Heavier than Streamlit/Gradio; multi-package surface area | Accepted |
| 2026-05-17 | Light theme only at launch; English UI chrome / Japanese chat bodies; WCAG 2.1 AA | Avoid scope creep; clear language policy; accessibility from Day 1 | Dark theme deferred | Accepted |
| 2026-05-17 | UI chrome must be English; Japanese only in chat/agent narrative | SPEC L131; Phase 1 briefly shipped Japanese nav/placeholders — corrected, no new ADR | Agents must not reintroduce JP labels in components | Superseded |
| 2026-05-17 | All user-visible text in English (UI, chat, agent narrative) | Product requirement; supersedes Japanese chat dialogue policy | Prior JP-chat decisions in this table | Accepted |
| 2026-05-17 | Engineer debug visibility permanent, not dev-only | Bugs appear in production; debug surface must be available where bugs appear | Always-present UI surface area | Accepted |
| 2026-05-17 | Chat renders GFM Markdown with sanitization; tool calls show input, output, and executed SQL | Markdown captures structured agent output; executed SQL reveals intent-vs-execution drift | Larger frontend bundle; sanitization required | Accepted |
| 2026-05-17 | Compute routing: sync <5s in FastAPI; Phase 2-3 ACA Jobs; Phase 5 Celery+Redis; Phase 6 Databricks; Phase 8+ Databricks ETL | LLM never runs heavy compute; routing matched to workload class | More infra components to provision over time | Accepted |
| 2026-05-17 | Phase 3 optimizer: OR-Tools CP-SAT over MOQ multiples; nested simulation `JobRunner` jobs; dedicated ACA optimization job | Real optimizer milestone without multi-SKU MIP; audit trail for each simulation evaluation | Up to six `job_runs` rows per optimize; larger worker image | Accepted |
| 2026-05-17 | Azure Functions / AKS / Batch / ACI / Temporal-MVP / Azure-ML-Phase6 rejected | Documented triggers for reconsideration recorded | Loss of those platforms' specific strengths | Accepted |
| 2026-05-17 | LLM cost tracking via dedicated llm_usage and llm_pricing tables | Cost has different access patterns and identity vs agent_steps | Two more tables and a pricing seeding obligation | Accepted |
| 2026-05-17 | LLM pricing versioned with effective_from/to | Historical rows must survive pricing changes | Pricing inserts at seed time required | Accepted |
| 2026-05-17 | Cost-saving defaults enforced Day 1: prompt cache, temperature=0, prompt segmentation, summarization, vcrpy | Reduces baseline cost without restricting feature use | Caching pinning requires careful prompt design | Accepted |
| 2026-05-17 | Budget enforcement: observation-only Day 1; soft/hard ceiling Phase 4+ | Avoid user-facing failures during MVP development | Cost overruns possible during MVP | Accepted |
| 2026-05-17 | OpenTelemetry + Langfuse as LLM observability; structlog for app logs; sink to Azure Monitor / App Insights | Best-in-class LLM tracing alongside conventional logs | Two observability surfaces to manage | Accepted |


| 2026-05-17 | Sample dataset: 30 SKUs / 24 months with bucket composition documented | Reflects real-world variety needed to exercise trade-off engine | Hand-authored ground-truth file required | Accepted |
| 2026-05-17 | Ground-truth CSVs never enter PostgreSQL | Two-layer defense via path convention + SQL Tool allowlist | Evaluation harness must read CSV directly | Accepted |
| 2026-05-17 | Day-1 Tool Registry: SQL/Approval/Audit implemented; Forecast/Sim/Opt stubbed; Python Analysis and Report deferred | LLM + SQL Tool covers ad-hoc analysis; Markdown chat covers reports | Future tools must be added behind Tool Layer interface | Accepted |
| 2026-05-17 | Risk classification has three tiers (low / medium / high) with explicit thresholds | Avoids binary collapse and enables Phase 8 auto-execution ramp | More configuration surface area | Accepted |
| 2026-05-17 | KPI weight defaults: global CSV + per-SKU overrides CSV; runtime resolution session_goal → memory → overrides → default | Lowest-friction surface for user override; preserves Phase 7 memory hook | Two CSVs to maintain | Accepted |
| 2026-05-17 | Critical SKU service_level weight = 0.50 by default | Service level dominant for critical items | Other KPIs renormalized | Accepted |
| 2026-05-17 | Evaluator schemas versioned with schema_version="1" | Enables non-breaking evolution | Versioning discipline required | Accepted |
| 2026-05-17 | audit_log is the only authoritative tamper-evident chain | Single source of truth; tool_calls.audit_hash is a denormalized pointer | Pointer must be written in same transaction | Accepted |
| 2026-05-17 | MVP auth: X-Dev-User header middleware; Entra ID bolt-on later | Velocity > full auth for MVP | Real auth missing until bolt-on phase | Accepted |
| 2026-05-17 | Multi-session per user supported Day 1 | Real product requirement, not retrofitted | UI must manage session list and state | Accepted |
| 2026-05-17 | Optimistic concurrency on decision_sessions with idempotent orchestrator retry | Low collision probability in MVP; avoids deadlocks | Conflicts must be detected and retried correctly | Accepted |
| 2026-05-17 | CORS: localhost:3000 dev / env-injected prod FQDN; SSE excluded from credentials | Standard pattern; works with EventSource | Per-env config required | Accepted |
| 2026-05-17 | GitHub Actions OIDC subject-claim list and least-privilege role assignments locked | No long-lived secrets; minimum permissions | One-time Azure AD configuration | Accepted |
| 2026-05-17 | llm_pricing rates verified at seed time with ADR record | Pricing changes; ADR keeps history truthful | Manual verification step | Accepted |
| 2026-05-17 | KaTeX + Mermaid in Day-1 Markdown pipeline | Marginal cost is small; avoid re-testing later | Bundle size for lazy-loaded mermaid | Accepted |
| 2026-05-17 | Official docs in English; existing Japanese docs kept as source notes; chat responses in Japanese | AI agents read English most reliably; preserves domain reasoning | Mixed-language repo artifacts | Accepted |


| 2026-05-17 | Demand noise: Negative Binomial (dispersion = base_demand * 0.3) | Real retail demand is overdispersed; Poisson underestimates tail | Slightly more complex generator | Accepted |
| 2026-05-17 | Lead time: lognormal (σ = 0.3) | Right-skewed shape mirrors real supply chains; no negative values | Lognormal less intuitive than normal | Accepted |
| 2026-05-17 | Initial inventory computed from daily_demand, lead_time, safety_stock=14 | Self-consistent; no orphaned constants | Tied to base_demand tuning | Accepted |
| 2026-05-17 | Random seed: default 42; --seed N for alternates | Reproducibility across developers and CI | Single dataset realization by default | Accepted |
| 2026-05-17 | Missing data: 3 SKUs targeted (deterministic), 2% NULL rate, one 7-day contiguous gap | Forces detection logic vs interpolation around scattered NULLs | Test surface only on 3 SKUs | Accepted |
| 2026-05-17 | Ground-truth retains unmasked values for evaluation | Evaluation harness needs true values to score forecast error | Two parallel datasets to maintain | Accepted |


| 2026-05-17 | Interfaces codified Day 1 (LLMClient / Tool / JobRunner / MemoryStore / Orchestrator / Specialist) | Final-form-first requires interface lock before implementation; ADR required for any change | Higher up-front design effort | Accepted |
| 2026-05-17 | Cost tracking is middleware inside LLMClient, not call-site logging | Non-bypassable; call-site logging drifts | Single class becomes critical-path | Accepted |
| 2026-05-17 | Approval revisions create new rows with parent_approval_id; never mutate closed rows | Preserves audit chain of what original approver saw | Slightly more rows; chain traversal needed for history view | Accepted |
| 2026-05-17 | KPI definitions live in one module (packages/domain/kpi.py); Evaluator and Simulator share it | Trade-off correctness requires identical KPI semantics | Coupling between Evaluator and Simulator via shared module | Accepted |
| 2026-05-17 | JobSpec.idempotency_key required Day 1 in sync JobRunner | Enables transparent Phase 5 Celery swap | Callers must compute the key | Accepted |
| 2026-05-17 | Schema parity Pydantic ↔ Zod via codegen + CI equivalence check | Hand-mirroring drifts silently | Codegen tooling required | Accepted |
| 2026-05-17 | DB-level CHECK constraints for status enums; ORM mirrors DB | Application enums drift from DB during partial migrations | Duplicate definition burden | Accepted |
| 2026-05-17 | Stubs are intentionally trivial; tests assert schema conformance only | Smart stubs hide schema mismatches; trivial stubs exercise the contract | No numerical realism in Phase 1 | Accepted |
| 2026-05-17 | Web Docker image is real Next.js standalone (not Phase 0 `ok` HTTP stub); Compose build context = repo root | Agents and CI must not ship a fake port-3000 server; documented in AGENTS.md § Web Docker image — anti-regression | Rebuild required when Dockerfile changes; `NEXT_PUBLIC_*` baked at build time | Accepted |
| 2026-05-17 | Branch protection: 1 reviewer; required checks lint-test + terraform-plan; no force-push; linear history | Single-developer ergonomics + safety baseline | Tightening required on team expansion | Accepted |
| 2026-05-17 | Conventional Commits scope list locked to 16 scopes | Predictable changelog generation | New scopes need DECISIONS update | Accepted |

