# REFACTORING_BRIEF.md

## Purpose

The goal of this refactoring is not to preserve the existing structure, but to move the codebase toward the final state defined in `DESIGN.md`.

The existing implementation may be used as reference, but must not be used as the basis for design decisions.
The basis for all decisions is `DESIGN.md`.

---

## Core Policy

This refactoring prioritizes the following:

1. Move toward the responsibility separation defined in `DESIGN.md`
2. Restructure around the Orchestrator as the center
3. Clarify the boundaries between Domain Agents and Analytical Agents
4. Separate the Tool Layer from Agents
5. Treat Memory and Guardrails as explicit layers
6. Prioritize structures that are easier to extend in the future over extending the life of existing code

---

## Key Decision Criteria

When existing code conflicts with the new design, the new design takes priority.

However, the following must not be carelessly broken:

- External API contracts
- User-visible major behaviors
- Persistence data compatibility
- Authentication and authorization
- Audit logs
- Configuration required for production operation

Internal structure, file layout, class names, module division, and responsibility placement may be changed.

---

## Refactoring Targets

The primary targets are:

- Orchestrator responsibility clarification
- Agent classification restructuring
- Tool call separation
- Memory management clarification
- Guardrail processing clarification
- Workflow organization
- Removal of duplicate logic
- Cleanup of naming and structure dependent on the old design

---

## Orchestrator Policy

The Orchestrator is the central component responsible for:

- Intent Analysis
- Planning
- Routing
- State Management
- Result Aggregation
- Conflict Detection
- Decision Scoring
- Response Generation

The Orchestrator does not absorb specialized analysis directly.
Specialized analysis is delegated to Domain Agents or Analytical Agents.

---

## Agent Policy

Agents are classified as:

- SessionOrchestrator
- Domain Agents
- Analytical Agents

Agents are treated first as responsibility boundaries, not as implementation units.
In early implementation, multiple capabilities may be consolidated into a smaller number of runtime agents.

However, the code must be structured so that future separation is possible.

---

## Tool Policy

Tools must not be embedded as internal processing within Agents.

Tools are treated as independent execution capabilities with the following responsibilities:

- Data retrieval
- Domain knowledge search
- KPI definition retrieval
- Calculation
- Analysis
- Simulation
- Notification
- Audit logging
- Permission control

Agents use Tools; agents do not hold Tool implementation details.

---

## Memory Policy

Memory must not be treated as simple conversation history.

The following uses are separated:

- Short-term Memory
- Working Memory
- Long-term Memory
- Decision Memory
- User Memory
- Domain Memory

Decision rationale, preconditions, intermediate results, and past decisions must be structured so they can be saved and reused as needed.

---

## Guardrail Policy

Guardrails are treated as an independent control layer, not as after-the-fact if-statements.

The following must be made explicit:

- Operations that can be executed
- Operations that can only be proposed
- Operations that require approval
- Prohibited operations
- Operations that require permission verification
- Operations that require audit logging

When an Agent affects external systems, it must always pass through Guardrail.

---

## What May Be Deleted or Consolidated

The following may be deleted or consolidated:

- Structures premised on old phases
- Branches dependent on completed tasks
- Duplicate Agent definitions
- Overlapping responsibilities between Orchestrator and Agents
- Tight coupling between Tools and Agents
- Remnants of temporary MVP implementations
- Naming that conflicts with the current DESIGN.md
- Shortcut implementations that impede future extension

---

## What Must Be Preserved

The following must be handled carefully:

- Working external interfaces
- Authentication and authorization
- Data persistence
- Logging and auditing
- Tests
- Configuration management
- User-visible behavior
- Existing valid business logic

Even when preserved, placement and responsibility must be reorganized to match the new design.

---

## Implementation Prohibitions

The following are prohibited:

- Applying only superficial fixes while keeping the existing structure as the premise
- Stuffing all business logic into the Orchestrator
- Embedding Tool implementations directly inside Agents
- Treating Memory as simple logging
- Scattering Guardrail logic as after-the-fact conditional branches
- Mixing phase or task history into design structure
- Preserving old concepts not present in DESIGN.md

---

## Completion Criteria

This refactoring is complete when all of the following are satisfied:

- Code structure has moved toward the layered structure of `DESIGN.md`
- Orchestrator responsibilities are clearly defined
- Responsibility boundaries between Domain Agents and Analytical Agents are clear
- Tool Layer is separated from Agents
- Memory usage is clearly defined
- Guardrail responsibilities are clearly defined
- Duplicate structures and unnecessary remnants from the old design are reduced
- Major external behavior is not broken
- Tests, lint, and typecheck pass

---

## Instructions for Coding Agents

In this work, do not make minimum-change fixes premised on the existing structure.

First read `DESIGN.md` and analyze the gap with the current code structure.
Then establish a refactoring policy to approach the new design.
After that, make changes incrementally in units that do not break responsibility boundaries.

When in doubt, prioritize the final state of `DESIGN.md` over the convenience of existing code.

The goal of this refactoring is not to "clean up the existing implementation."
The goal is to "migrate to a structure closer to the new design."
