# DESIGN.md

## Purpose

This document defines the final target design of the supply chain optimization agent system.

The system spans multiple domains — demand, inventory, replenishment, procurement, production, logistics, and supplier risk — and supports human decision-making by combining operational data, business rules, and analytical results into an Agentic AI system.

This document does not define implementation steps, phases, task lists, or migration procedures.
Those are managed in separate documents.

The role of this document is to declare the target state that coding agents must approach during large-scale refactoring — without being constrained by the existing implementation.

---

## Terminology

This project uses the word "agent" in two distinct, non-overlapping contexts. Confusing them is a common source of misunderstanding.

### Product Agents (runtime)

Agents that **are** the Business Decision OS system. They run in production, process user requests, call tools, and generate decision-ready answers.

| Term used in this document | Examples |
|---|---|
| **SessionOrchestrator** | The central session-level orchestrator — intent classification, chat/QA handling, goal resolution, planning, routing, execution control, aggregation, response synthesis |
| **Domain Agent** | Demand Agent, Inventory Agent, Replenishment Agent, … |
| **Cross-Domain Agent** | Data Engineer Agent, Simulation Optimizer Agent, Evaluator Agent, Anomaly Detector Agent |

When this document says "agent" without qualification, it means a product agent.

### Coding Agents (development-time)

Claude Code subagents that **build and maintain** this system. They run inside the Claude Code harness during development and never appear in the production system.

| Term used in AGENTS.md | Role |
|---|---|
| `bdos-orchestrator` | Plans phases, decomposes tasks, routes to specialists, updates TASKS.md |
| `bdos-app-builder` | Writes application code — FastAPI, Python packages, Next.js |
| `bdos-infra` | Infrastructure, Docker Compose, CI/CD, Makefile |
| `bdos-test-review` | Writes tests, reviews code, verifies phase checkpoints |

When AGENTS.md says "agent" or "subagent", it means a coding agent.

**The product agents are what the coding agents are building.** They are different things.

---

## Design Principles

This system is designed as an agent system that supports business decision-making, not as a simple chatbot.

The core of an Agentic AI is the combination of the following components:

- Agent
- Tools
- Memory
- Loop
- Guardrails
- Workflow

Agents are responsible for judgment, decomposition, and selection.
Tools are responsible for data retrieval, calculation, analysis, simulation, and external actions.
Memory retains state, assumptions, decision history, and domain knowledge.
Loop enables continuous analysis, correction, and re-evaluation.
Guardrails control permissions, safety, approvals, and auditing.
Workflow defines the collaborative process between humans and agents.

This system prioritizes clear responsibility boundaries, Tools, Memory, and Guardrails over increasing the number of agents.

---

## Core Capabilities

The system receives business questions from users and generates decision-ready answers by combining the necessary data, business rules, KPI definitions, historical decisions, and analytical logic.

Core capabilities:

- Understanding user requests
- Decomposing requests into business tasks
- Routing to appropriate agents
- Retrieving required data and domain knowledge
- Detecting anomalies, risks, and opportunities
- Scenario analysis
- Prioritization
- Root cause analysis
- Organizing decision rationale
- Generating final answers
- Retaining decision history and audit logs

This system does not replace human judgment entirely.
It organizes operational data and analytical results to help humans make better decisions.

---

## Architecture Overview

The system is composed of the following layers:

1. User Interface Layer
2. Orchestration Layer
3. Agent Layer
4. Tool Layer
5. Memory Layer
6. Guardrail Layer
7. External Systems Layer

**User Interface Layer** handles user interaction, input, output, confirmations, and approvals.

**Orchestration Layer** is responsible for understanding user requests, planning, routing, state management, result aggregation, and final judgment.

**Agent Layer** is composed of domain-specific agents and cross-domain agents.

**Tool Layer** provides data retrieval, knowledge search, calculation, analysis, simulation, notification, and auditing capabilities that agents use.

**Memory Layer** retains short-term state, working state, decision history, domain knowledge, and user context.

**Guardrail Layer** is responsible for permissions, approvals, safety, auditing, and risk control.

**External Systems Layer** handles integration with databases, operational systems, documents, notification targets, and ticket systems.

---

## Orchestration Design

The center of this system is the SessionOrchestrator.

The SessionOrchestrator receives `SessionUserQuery` utterances within a user session, distinguishes between chat, question answering, exploration, consultation, and explicit goal-directed tasks, and when needed generates a `SessionGoal`, creates a plan, routes work to agents, controls execution, integrates results, and synthesizes the final `SessionResponse`.

In MVP and early configurations, Planner, Router, State Manager, and Aggregator are not separated into independent agents.
These are treated as internal responsibilities of the SessionOrchestrator.

The SessionOrchestrator is responsible for:

- Intent Classification
- Chat / QA Handling
- Goal Resolution
- Intent Analysis
- Planning
- Routing
- Execution Control
- State Management
- Result Aggregation
- Conflict Detection
- Decision Scoring
- Response Generation

The SessionOrchestrator does not execute all specialized processing itself.
Specialized analysis and business judgment are delegated to Domain Agents or Cross-Domain Agents.

When results from multiple agents conflict, the SessionOrchestrator detects the conflict and, if necessary, requests additional confirmation, re-analysis, or escalation to a human.

---

## Agent Classification

The agents in this system are classified into three types:

### SessionOrchestrator

The central session-level orchestrator responsible for intent classification, chat/QA handling, goal resolution, planning, routing, execution control, aggregation, response synthesis, and final judgment across the entire system.

### Domain Agents

Agents that handle specialized judgment for each business domain: demand, inventory, replenishment, procurement, production, logistics, and supplier.

### Cross-Domain Agents

Agents that provide cross-domain execution and analytical capabilities — operational data gathering, simulation and optimization, evaluation, and anomaly detection — not confined to a specific business domain.

Domain Agents own responsibility for a business area.
Cross-Domain Agents own responsibility for reusable capabilities that support multiple business areas.

---

## Agent Design

| Agent | Purpose | Role | Available Toolset | Primary Input | Output | Memory |
|---|---|---|---|---|---|---|
| SessionOrchestrator | Orchestrate user sessions across chat, QA, exploration, consultation, and explicit goal-directed tasks | Intent classification, chat/QA handling, goal resolution, planning, routing, execution control, state management, result aggregation, response synthesis | Data Access, Knowledge, Analysis, Memory, Guardrail, Summary | User utterance, session state, working state, past decisions, agent results | Direct answer, execution plan, delegation instructions, aggregated result, final response | Working Memory, Decision Memory, User Memory |
| Demand Agent | Support demand-related judgment | Analyze demand trends, forecast deviations, demand fluctuations, and demand risk | Data Access, Metric Definition, Trend Analysis, Forecast Analysis | Demand actuals, forecasts, products, customers, period, KPI definitions | Demand insights, demand risk, forecast deviations | Domain Memory, Decision Memory |
| Inventory Agent | Support inventory-related judgment | Analyze inventory levels, stockout risk, excess inventory, and inventory health | Data Access, Inventory Calculation, Data Quality, Business Rules | Inventory data, demand, supply, service level, inventory rules | Inventory risk, recommended review points, inventory decision inputs | Domain Memory, Working Memory |
| Replenishment Agent | Support replenishment judgment | Analyze when, where, and how much to replenish | Data Access, Calculation, Simulation, Business Rules | Inventory, demand, lead time, replenishment constraints, location information | Replenishment candidates, replenishment risk, replenishment rationale | Working Memory, Decision Memory |
| Procurement Agent | Support procurement judgment | Analyze orders, purchase quantities, timing, and constraints | Data Access, Business Rules, Supplier Data, Calculation | Purchase history, demand, inventory, supplier terms, pricing | Procurement decision inputs, order candidates, constraint notes | Domain Memory, Decision Memory |
| Supplier Agent | Judge supplier risk | Analyze delivery performance, quality, supply stability, and supplier risk | Data Access, Risk Analysis, Knowledge Retrieval, Audit | Supplier information, delivery history, quality data, contract terms, supply risk | Supplier risk, alternative candidates, notes | Domain Memory, Decision Memory |
| Production Agent | Support production planning judgment | Analyze production capacity, constraints, and plan change impacts | Data Access, Capacity Analysis, Scenario, Business Rules | Demand, inventory, production capacity, process constraints, plan information | Production risk, constraints, plan change impacts | Working Memory, Domain Memory |
| Logistics Agent | Support logistics judgment | Analyze shipping, inter-location transfers, logistics constraints, and delivery risk | Data Access, Route/Network Analysis, Cost Analysis, Business Rules | Shipment information, locations, delivery conditions, logistics cost, deadline constraints | Logistics risk, delivery decision inputs, transfer candidates | Domain Memory, Decision Memory |
| Data Engineer Agent | Gather operational facts for the decision | Query operational data tables and retrieve factual context needed by other agents | Data Access, Forecast, Knowledge Retrieval | User goal, requested entities, operational tables, allowed tools | Data summary, retrieved facts, query results | Working Memory, Audit Memory |
| Simulation Optimizer Agent | Generate candidate plans | Run simulation and optimization tools and compare scenarios across supply chain domains | Simulation, Optimization, Calculation, Summary | Goal, data summaries, constraints, assumptions, comparison axes | Candidate plans, scenario comparison, optimization rationale | Working Memory, Decision Memory |
| Evaluator Agent | Evaluate candidate plans | Score each candidate plan against all KPIs independently | Evaluation, Scoring, Metric Definition, Audit | Candidate list, KPI definitions, weights, constraints, risk information | Per-KPI scores, evaluation rationale, audit notes | Working Memory, Decision Memory |
| Anomaly Detector Agent | Detect anomalies and items requiring attention | Detect missing data, outliers, sudden changes, rule violations, and abnormal patterns across domains; surface root cause candidates | Data Quality, Anomaly Detection, Data Access, Knowledge Retrieval | Operational data, KPIs, thresholds, rules, historical trends | Anomaly list, severity, root cause candidates, review rationale | Working Memory, Audit Memory |

---

## Tool Design

Tools define the execution capabilities of agents.

Agents retrieve data, perform calculations, run analyses, and interact with external systems through Tools.
Data retrieval and calculation logic must not be embedded directly in agents.

Tools are classified into the following categories:

- Data Access Tools
- Knowledge Tools
- Calculation Tools
- Analysis Tools
- Optimization Tools
- Simulation Tools
- Communication Tools
- Action Tools
- Memory / Audit Tools
- Guardrail Tools

Specific specifications, arguments, return values, permissions, and failure handling for each tool are defined in a separate document.

In DESIGN.md, only the purpose and responsibility boundaries of tools are defined.

---

## Memory Design

Memory is not simply conversation history.

In this system, Memory is the layer that retains the following:

- Conversation history
- Working state
- Intermediate results
- Decision history
- Domain knowledge
- KPI definitions
- Business rules
- User context
- Past decisions

Memory is classified as follows:

### Short-term Memory

Retains temporary information needed only during the current interaction.

### Working Memory

Retains intermediate state, in-progress calculations, and shared state between agents needed to complete the current task.

### Long-term Memory

Retains knowledge and context to be reused in future decisions.

### Decision Memory

Retains decision rationale, alternatives, rejection reasons, preconditions, and past decisions.

### User Memory

Retains user goals, preferences, decision tendencies, and usage context.

### Domain Memory

Retains business rules, KPI definitions, domain knowledge, and historical cases.

Memory is used not only for response quality but also for accountability, reproducibility, and auditability.

---

## Guardrail Design

The Guardrail Layer controls the scope of agent execution, safety, permissions, approvals, and auditing.

This system does not permit agents to freely execute external actions.
Important operations, high-impact proposals, writes to external systems, notifications, and approval requests all require explicit permissions and confirmations.

The Guardrail Layer is responsible for:

- Verifying user permissions
- Verifying data access permissions
- Controlling external actions
- Determining which processes require approval
- Detecting high-risk proposals
- Recording audit logs
- Retaining decision rationale
- Separating executable operations from proposal-only operations

When confidence is low or business risk is high, agents prioritize requesting human confirmation.

---

## Workflow Design

The basic workflow of this system is as follows:

1. User submits a business question
2. SessionOrchestrator understands the intent
3. SessionOrchestrator decomposes the required work
4. SessionOrchestrator selects the appropriate agents
5. Each agent uses the necessary tools to analyze
6. SessionOrchestrator integrates the results
7. Detect conflicts, risks, and missing information
8. Request additional confirmation or re-analysis as needed
9. Generate the final response
10. Save decision history and important assumptions

This system is structured to support not just one-time answers, but re-evaluation, additional analysis, condition changes, and scenario comparison as needed.

---

## Response Design

Responses from this system are not simple explanatory text — they have a structure usable for decision-making.

Responses include the following as needed:

- Conclusion
- Decision rationale
- Supporting data
- Preconditions
- Risks
- Alternatives
- Priority
- Next items to review
- Points requiring human approval

However, not all elements need to be included in every response.
Response depth is adjusted based on the user's question, business risk, and required decision granularity.

---

## Scope Management

This DESIGN.md defines the design of the entire product but does not require all features to be implemented simultaneously.

Agent definitions are treated as a Capability Map.
All agents do not need to be implemented as independent execution units from the start.

In implementation, multiple capabilities may be consolidated into a smaller number of runtime agents as needed.
However, the agent definitions as responsibility boundaries must be maintained.

Rather than perpetuating the existing structure for implementation convenience, the priority is to align with the responsibility separation, orchestration, tool design, memory design, and guardrail design defined in this DESIGN.md.

---

## Relationship to Other Documents

This DESIGN.md defines the declarative design of the entire product.

Details are separated into the following documents:

- SPEC.md: What to achieve
- DESIGN.md: What structure to achieve it with
- TASKS.md: What to implement
- DECISIONS.md: Why those decisions were made
- TESTING.md: How to verify
- TOOLS.md: Tool specifications
- MEMORY.md: Memory specifications
- GUARDRAILS.md: Permission, safety, approval, and audit specifications
- AGENTS.md: Detailed responsibilities per agent

DESIGN.md does not absorb too much detail.
Frequently changing concrete specifications, implementation tasks, API details, table definitions, and code structure are managed in separate documents.

---

## Non-Goals

The following are not defined in this DESIGN.md:

- Implementation tasks
- Phases
- Milestones
- Source code structure details
- Database table definitions
- API specifications
- UI details
- Individual tool arguments and return values
- Test case lists
- Deployment procedures

These are managed in separate documents.

---

## Monorepo Layout

The canonical directory structure that all agents must treat as authoritative.
Adding new top-level packages outside this layout requires an ADR.

```
packages/
  agent/
    orchestrator/   ← SessionOrchestrator (intent classification, chat/QA, goal
                      resolution, planning, routing, execution control, aggregation)
    domain/         ← Domain Agents (demand, inventory, replenishment, procurement,
                       supplier, production, logistics)
    cross_domain/   ← Cross-Domain Agents (data_engineer, simulation_optimizer,
                       evaluator, anomaly_detector)
    llm/            ← LLM client — only entry point to LLM provider SDK
    runner/         ← Celery job runner infrastructure
  tools/            ← Tool Layer (all execution capabilities)
  memory/           ← Memory Layer (six typed stores)
  persistence/      ← DB session management and all repository classes
  knowledge/        ← Domain knowledge: KPI definitions, business rules
  simulation/       ← Simulation compute engine (used by simulation_tool.py)
  optimization/     ← Optimization compute engine (used by optimizer_tool.py)
  prediction/       ← Prediction compute engine (used by forecast_tool.py)
  schemas/          ← Pydantic schemas shared across Python packages
  schemas-ts/       ← TypeScript schemas shared with apps/web
  lakehouse/        ← Bronze / Silver / Gold data lake layers
apps/
  api/              ← FastAPI application (entry point)
  web/              ← Next.js frontend (entry point)
  simulation-worker/    ← Celery worker for simulation jobs
  optimization-worker/  ← Celery worker for optimization jobs
```

---

## Public Interfaces

The following interfaces may not change signature without an ADR filed in `docs/ADR/`.
An interface change that is not backed by an ADR will be rejected at code review.

| Interface | Location |
|---|---|
| `LLMClient` | `packages/agent/llm/` |
| `Tool` (base class) | `packages/tools/base.py` |
| `JobRunner` | `packages/agent/runner/` |
| `MemoryStore` (the six typed classes) | `packages/memory/` |
| `Orchestrator` protocol | `packages/agent/orchestrator/` |
| `SessionOrchestrator` | `packages/agent/orchestrator/` |
| `SessionUserQuery`, `SessionIntent`, `AgentRoute`, `SessionResponse` | `packages/agent/orchestrator/` |
| `Specialist` (base protocol) | `packages/agent/base.py` |

---

## Phase Progression

Implementation follows the phase order in `docs/MIGRATION_PLAN.md`.
Do not begin Phase N+1 work while Phase N checkpoint is unverified.

| Phase | Goal |
|---|---|
| Phase R | Structural Rename — align package names with this document's vocabulary |
| Phase 0 | Protect — lock external contracts before touching internals |
| Phase 1 | Tool Layer Isolation — no agent calls DB or LLM SDK directly |
| Phase 2 | Memory Formalization — six typed memory stores, no raw dict |
| Phase 3 | Guardrail Separation — permission logic consolidated in one module |
| Phase 4 | Agent Reclassification — specialists → domain/ + cross_domain/ |
| Phase 5 | Orchestrator Cleanup — no domain logic in orchestrator |
| Phase 6 | Final Validation — full system matches this document |

---

## Final State Definition

The final system has a structure where user utterances are received by the SessionOrchestrator, processing is delegated to the necessary Domain Agents and Cross-Domain Agents, and decision-ready answers are generated through the Shared Tools, Memory Layer, and Guardrail Layer.

What matters in this design is not the number of agents.

What matters is:

- SessionOrchestrator handles intent classification, chat/QA, goal resolution, planning, routing, execution control, aggregation, and response synthesis
- Domain Agents hold responsibility for each business area
- Cross-Domain Agents hold reusable execution and analytical capabilities
- Tools provide execution capabilities
- Memory retains state, context, and decision history
- Guardrails handle safety, permissions, approvals, and auditing
- Workflow defines human-agent collaboration

The goal of refactoring is not to preserve the existing structure, but to move toward this final state.
