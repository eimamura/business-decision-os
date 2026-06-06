# ADR: Start with an Integrated Supply Chain Control Agent

**Date:** 2026-06-05  
**Status:** Accepted  
**Phase:** MVP

---

## Background

Supply chain operational questions (stockout risk, shipment delays, today's exceptions) cannot be answered from a single domain. A typical question like "why is this SKU at risk?" requires cross-referencing inventory, demand, inbound schedule, open orders, and production plan simultaneously. If the system is built from the start as a set of separated specialist agents (Inventory Agent, Demand Agent, Production Agent, …), each agent sees only its slice of the data and the root cause is fragmented.

---

## Decision

The MVP is built around a single **Supply Chain Control Agent** that has read access to all operational data domains:

```text
Supply Chain Control Agent
  ├─ demand data
  ├─ inventory data
  ├─ order data
  ├─ shipment data
  ├─ production data
  ├─ purchasing data
  └─ finance / margin data
```

This agent is responsible for:

1. Detecting today's exceptions
2. Cross-joining data from multiple domains
3. Narrowing root cause candidates
4. Prioritizing by business impact
5. Producing recommended next actions

---

## Options Considered

**Option A — Integrated Control Agent first (chosen)**  
One agent, full data access. Domain agents are added later only when depth in a specific area demands it. Keeps MVP simple, preserves cross-domain visibility, and defers complexity until the need is proven.

**Option B — Specialist agents from day one**  
Separate agents per domain from the start. Rejected for MVP: supply chain problems do not resolve within a single domain. Splitting too early fragments root cause analysis, multiplies coordination overhead, and adds complexity before value is proven.

---

## When to Add Specialist Agents

Specialist agents should be introduced when analysis depth in a specific domain outgrows what the Control Agent can provide. The trigger is depth, not taxonomy.

| Specialist Agent | Trigger for introduction |
| --- | --- |
| Demand Planning Agent | Forecast accuracy analysis, error decomposition, demand sensing |
| Inventory Agent | Safety stock optimization, replenishment logic, ABC/XYZ classification |
| Production Agent | Capacity constraints, changeover scheduling, line sequencing |
| Procurement Agent | Lead time modeling, order point calculation, supplier delay analysis |
| Logistics Agent | OTIF tracking, shipping slot constraints, carrier analysis |
| Finance Agent | Margin impact, working capital, inventory valuation |

---

## Relationship to the S&OP Agent

The Supply Chain Control Agent and the S&OP Agent are distinct but related. They operate at different cadences and at different levels of abstraction.

| Agent | Time horizon | Focus |
| --- | --- | --- |
| **Supply Chain Control Agent** | Daily – weekly | Operational monitoring: exceptions, stockout risk, shipment delays, excess inventory, supply shortage, root causes, action priorities |
| **S&OP Agent** | Weekly – monthly | Planning and management decisions: demand forecast, supply capacity, inventory policy, production plan, purchase plan, revenue/profit impact, scenario comparison, final recommendation |

In the final state, the S&OP Agent sits above the Supply Chain Control Agent:

```text
S&OP Agent                        ← planning & management-level decisions
  └─ Supply Chain Control Agent   ← execution & monitoring layer
      ├─ Demand
      ├─ Inventory
      ├─ Production
      ├─ Procurement
      ├─ Logistics
      └─ Finance
```

The Supply Chain Control Agent is the execution and monitoring layer of the S&OP cycle. The S&OP Agent uses it as an input when building planning scenarios and comparing them against operational reality.

The MVP uses the name **Supply Chain Control Agent**. As planning capabilities are added, the S&OP Agent is introduced as the upper layer — the Control Agent does not need to be renamed.

---

## Target Architecture

```text
Level 0: S&OP Agent               ← planning, scenario comparison, management decisions
Level 1: Supply Chain Control Agent   ← cross-domain visibility, daily exceptions
Level 2: Specialist Domain Agents     ← deep analysis, added when depth is needed
Level 3: Tools (SQL / DataFrame / Forecast / Optimization)
```

---

## Division of Judgment vs. Division of Processing

The architectural prohibition is against dividing **judgment**, not against dividing **processing**.

| Division type | Acceptable | Reason |
| --- | --- | --- |
| Dividing judgment (each agent concludes independently, then merge) | No | Destroys cross-domain optimization |
| Dividing data retrieval (tools fetch domain data) | Yes | Keeps implementation clean |
| Dividing calculation (tools run domain-specific logic) | Yes | Enables reuse of specialized logic |
| Dividing final interpretation (each agent produces its own answer) | No | Results become incoherent |
| Control Agent holds judgment and integrates | Yes | Preserves cross-domain joining value |

The pattern to avoid:

```text
Demand Agent    → judges demand independently
Inventory Agent → judges inventory independently
Production Agent → judges production independently
→ merge results without shared context   ← this is the problem
```

The correct pattern:

```text
User
 ↓
Supply Chain Control Agent   ← judgment center, context owner, final interpreter
 ↓ calls as needed
 ├─ SQL / data tools
 ├─ Demand analysis tool
 ├─ Inventory analysis tool
 ├─ Shipment analysis tool
 ├─ Production analysis tool
 └─ Finance analysis tool
 ↓
Supply Chain Control Agent integrates and responds
```

Sub-agents in early phases should be treated more as **analysis modules** than as independent decision-makers. The Control Agent owns the judgment; sub-agents and tools provide input.

**Recommended MVP tool set** (no sub-agents needed at this stage):

```text
Supply Chain Control Agent
  + SQL Tool
  + DataFrame Analysis Tool
  + KPI Calculation Tool
  + Alert / Exception Detection Tool
```

---

## Rationale

The system's core value is **cross-domain joining** — reading inventory + orders + shipments + production schedule + purchase plan + forecast + actuals together and producing interpretations like:

- This SKU's risk is not low stock — it is an inbound delay.
- This customer's unshipped order is blocked by shipping slot shortage, not inventory.
- This apparent overstock will be consumed by a confirmed order next week.

Fragmenting *judgment* into specialists before this capability is mature loses the primary value proposition. The YAGNI principle applies: add specialist agents when the requirement for depth exists, not in anticipation of it.

---

## Consequences

- The Control Agent's tool allowlist is broader than any single domain agent would be.
- Sub-agents introduced later act as analysis assistants — they provide inputs to the Control Agent, which retains final interpretive authority.
- The SessionOrchestrator routes to the Control Agent by default for supply chain queries; specialist agents are added as routing targets only when they exist.
- Splitting judgment prematurely is the primary architectural risk to guard against.
