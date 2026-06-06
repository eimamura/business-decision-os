# SPEC.md

## Purpose

Product requirements for the supply chain optimization agent system.
This document defines what the system must be able to do — not how it is built.
Architecture and implementation decisions are in DESIGN.md, DECISIONS.md, and docs/adr/.

---

## Top 10 Questions in Supply Chain Operations

These are the highest-value recurring questions that the system is designed to answer.
They represent daily operational decisions where agent-assisted analysis creates immediate value.

| Priority | Question                                                          | Value                                                 |
| -------: | ----------------------------------------------------------------- | ----------------------------------------------------- |
|        1 | Which products are at risk of stockout?                           | Prevents lost sales                                   |
|        2 | Which products have excess inventory?                             | Prevents cash flow pressure                           |
|        3 | What exceptions require human judgment today?                     | Provides high daily operational value                 |
|        4 | What is causing shipment delays or unshipped orders?              | Prevents customer complaints and delayed revenue      |
|        5 | Why is there a gap between demand forecast and actual demand?     | Core input for improving S&OP                         |
|        6 | Which products may face supply shortages next week or next month? | Enables proactive production and purchasing decisions |
|        7 | Which products require production plan adjustments?               | Prevents overproduction and underproduction           |
|        8 | Which materials or items should be purchased earlier or later?    | Prevents raw material and component shortages         |
|        9 | Are there demand changes by customer or region?                   | Enables early detection of demand shifts              |
|       10 | Which constraint is having the biggest negative impact on sales or profit? | Supports overall optimization                 |

**MVP starting point: questions 1, 3, and 4** — Stockout risk → Today's exceptions → Shipment delay root causes.
These are checked daily and deliver value immediately.

---

## Agent Capabilities and Limitations

The agent system can answer all 10 questions above — not by resolving them fully, but by **assembling the materials needed for a decision: root cause candidates and recommended actions**.

| Domain | Agent capability | Human judgment retained |
| --- | --- | --- |
| Stockout risk | Extract at-risk SKUs from inventory, demand, and supply signals | Customer priority, emergency response |
| Excess inventory | Detect via days-on-hand, sell-through rate, and forward demand | Markdown, production stop, write-off |
| Today's exceptions | Prioritize significant anomalies | What to act on first |
| Shipment delays | Cross-reference open orders, inventory, and shipping status | Customer communication, deadline negotiation |
| Forecast deviation | Decompose gaps by SKU, region, customer, and week | Confirm the real business cause |
| Supply shortage | Project shortfalls from demand, stock, and inbound schedule | Adjust purchasing and production |
| Production plan changes | Detect overproduction and underproduction | Line constraints, staffing, changeover |
| Purchasing adjustment | Surface candidates for pull-forward or push-out | Supplier negotiation |
| Demand shift detection | Detect changes by customer and region | Confirm the sales-side context |
| Constraint analysis | Identify the bottleneck with the largest impact on revenue or profit | Management decision |

The agent's structural advantage is **cross-domain joining**: inventory + orders + shipments + production schedule + purchase plan + forecast + actuals, read together. This enables interpretations like:

- This SKU's risk is not low stock — it is an inbound delay.
- This customer's open order is not blocked by inventory — it is a shipping slot shortage.
- This overstock is not real excess — it will be consumed by a confirmed order next week.

**Known limitations**

- Dirty data or inaccurate master data degrades all outputs.
- Implicit business rules not captured in the database are invisible to the agent.
- Field context that never reaches the system (e.g., verbal supplier commitments) cannot be used.
- Final decisions that carry accountability must remain with a human.
- Supplier and customer negotiations require human relationships.

**Realistic framing**

The agent acts as a Supply Chain Analyst / Planner assistant — not a fully autonomous decision-maker. The practical role is:

> Scan operational data daily, surface anomalies, narrow root causes, and produce decision options for the human planner.

---

## Agent Catalog (Target State)

Full agent specifications for the final target state. In MVP, most Specialist Domain Agents and Cross-Domain Agents are not yet instantiated — the Supply Chain Control Agent covers their responsibilities. See `DESIGN.md § Agent Design` for the maturity model governing when each agent is introduced.

| Agent | Purpose | Role | Available Toolset | Primary Input | Output | Memory |
|---|---|---|---|---|---|---|
| SessionOrchestrator | Orchestrate user sessions across chat, QA, exploration, consultation, and explicit goal-directed tasks | Intent classification, chat/QA handling, goal resolution, planning, routing, execution control, state management, result aggregation, SessionResponse assembly | Data Access Tools, Knowledge Tools, Analysis Tools, Memory / Audit Tools, Guardrail Tools, Communication Tools | User utterance, session state, working state, past decisions, agent results | Direct answer, execution plan, delegation instructions, aggregated result, final response | Working Memory, Decision Memory, User Memory |
| Supply Chain Control Agent | Cross-domain judgment center and user-facing responder | Integrate results from Specialist and Cross-Domain Agents; own the final supply chain answer | All tool categories (via Tool Gateway) | Specialist outputs, Cross-Domain outputs, Memory context, Skills | Decision-ready answer: conclusion, root cause, options, priority, next checks | Decision Memory, Domain Memory, Working Memory |
| Demand Agent | Support demand-related judgment | Analyze demand trends, forecast deviations, demand fluctuations, and demand risk | Data Access Tools, Knowledge Tools, Analysis Tools | Demand actuals, forecasts, products, customers, period, KPI definitions | Demand insights, demand risk, forecast deviations | Domain Memory, Decision Memory |
| Inventory Agent | Support inventory-related judgment | Analyze inventory levels, stockout risk, excess inventory, and inventory health | Data Access Tools, Calculation Tools, Knowledge Tools | Inventory data, demand, supply, service level, inventory rules | Inventory risk, recommended review points, inventory decision inputs | Domain Memory, Working Memory |
| Replenishment Agent | Support replenishment judgment | Analyze when, where, and how much to replenish | Data Access Tools, Calculation Tools, Simulation Tools, Knowledge Tools | Inventory, demand, lead time, replenishment constraints, location information | Replenishment candidates, replenishment risk, replenishment rationale | Working Memory, Decision Memory |
| Procurement Agent | Support procurement judgment | Analyze orders, purchase quantities, timing, and constraints | Data Access Tools, Knowledge Tools, Calculation Tools | Purchase history, demand, inventory, supplier terms, pricing | Procurement decision inputs, order candidates, constraint notes | Domain Memory, Decision Memory |
| Production Agent | Support production planning judgment | Analyze production capacity, constraints, and plan change impacts | Data Access Tools, Analysis Tools, Simulation Tools, Knowledge Tools | Demand, inventory, production capacity, process constraints, plan information | Production risk, constraints, plan change impacts | Working Memory, Domain Memory |
| Logistics Agent | Support logistics judgment | Analyze shipping, inter-location transfers, logistics constraints, and delivery risk | Data Access Tools, Analysis Tools, Calculation Tools, Knowledge Tools | Shipment information, locations, delivery conditions, logistics cost, deadline constraints | Logistics risk, delivery decision inputs, transfer candidates | Domain Memory, Decision Memory |
| Finance Agent | Support finance-related judgment | Analyze revenue, profit impact, cost structure, and financial risk across supply chain scenarios | Data Access Tools, Calculation Tools, Analysis Tools, Knowledge Tools | Sales data, inventory cost, order data, pricing, stockout impact data | Profit impact analysis, financial risk, revenue analysis, cost decision inputs | Domain Memory, Decision Memory |
| Data Engineer Agent | Gather operational facts for the decision | Query operational data tables and retrieve factual context needed by other agents | Data Access Tools, Analysis Tools, Knowledge Tools | User goal, requested entities, operational tables, allowed tools | Data summary, retrieved facts, query results | Working Memory, Audit Memory |
| Simulation Optimizer Agent | Generate candidate plans | Run simulation and optimization tools and compare scenarios across supply chain domains | Simulation Tools, Optimization Tools, Calculation Tools, Communication Tools | Goal, data summaries, constraints, assumptions, comparison axes | Candidate plans, scenario comparison, optimization rationale | Working Memory, Decision Memory |
| Evaluator Agent | Evaluate candidate plans | Score each candidate plan against all KPIs independently | Analysis Tools, Calculation Tools, Knowledge Tools, Memory / Audit Tools | Candidate list, KPI definitions, weights, constraints, risk information | Per-KPI scores, evaluation rationale, audit notes | Working Memory, Decision Memory |
| Anomaly Detector Agent | Detect anomalies and items requiring attention | Detect missing data, outliers, sudden changes, rule violations, and abnormal patterns across domains; surface root cause candidates | Data Access Tools, Analysis Tools, Knowledge Tools, Memory / Audit Tools | Operational data, KPIs, thresholds, rules, historical trends | Anomaly list, severity, root cause candidates, review rationale | Working Memory, Audit Memory |
