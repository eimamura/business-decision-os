# Skill File Format

This document specifies the required format for all Skill files in `packages/knowledge/skills/`.
Skill files define standard analysis procedures that the ControlAgent injects into its LLM context
before answering user queries. This makes analysis reproducible and auditable.

> This file is a format specification document — it is **not** a real Skill file and is never loaded
> by `SkillLoader`.

---

## File Naming

- Use kebab-case: `stockout_risk_analysis.md`, `exception_detection.md`
- The filename (without `.md`) is the canonical identifier referenced in `SkillLoader`'s intent map
- One Skill per file

---

## Required Frontmatter

Every Skill file must begin with a YAML frontmatter block enclosed by `---` delimiters:

```yaml
---
skill_name: <kebab-case name matching the filename>
description: <one sentence describing what this Skill does>
required_tables: [<comma-separated table names from the SQL allowlist>]
required_kpis: [<comma-separated KPI names, or empty list []>]
---
```

### Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `skill_name` | string (kebab-case) | Yes | Canonical name; must match the filename stem |
| `description` | string | Yes | One sentence describing the Skill's purpose |
| `required_tables` | list of strings | Yes | DB tables this Skill's procedure reads (subset of SQL allowlist: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`) |
| `required_kpis` | list of strings | Yes | Named KPI formulas used (from `packages/knowledge/kpi.py`); empty list `[]` if none |

---

## Required Sections

After the frontmatter, every Skill file must contain the following two sections in order.

### `# Procedure`

A numbered list of steps the agent must follow to answer the user's question. Steps should be
concrete and tool-actionable — refer to specific tool names (e.g., `calculate_stockout_risk`,
`sql_query`) where appropriate.

```markdown
# Procedure

1. Step one — what to fetch / compute first
2. Step two — what to derive from step-one output
3. ...
```

### `# Output Schema`

A bulleted list describing the fields the agent must include in its final response. Each entry
uses the format: `- field_name: description (type)`.

```markdown
# Output Schema

- field_name: description (type)
- another_field: description (type)
```

---

## Complete Example

```markdown
---
skill_name: example-skill
description: Demonstrates the required Skill file structure with a minimal example.
required_tables: [inventory, demand_history]
required_kpis: [days_on_hand]
---

# Procedure

1. Query current on-hand inventory for the target SKU(s) from `inventory`.
2. Compute average daily demand from `demand_history` over the last 30 days.
3. Apply the `days_on_hand` KPI formula: `on_hand / avg_daily_demand`.
4. Flag SKUs where days_on_hand is below the configured reorder threshold.

# Output Schema

- sku_id: product identifier (string)
- on_hand_qty: current units in stock (float)
- avg_daily_demand: mean daily demand units (float)
- days_on_hand: computed days of supply remaining (float)
- reorder_signal: true if days_on_hand is below threshold (bool)
```

---

## Authoring Rules

- All content must be in English
- Do not include secrets, credentials, or hardcoded column names beyond what `get_schema_context()` provides
- Steps in `# Procedure` must be achievable with tools from the ControlAgent tool allowlist
  (see `packages/tools/base.py` for the `"control"` role allowlist)
- `required_tables` must be a subset of the SQL Tool allowlist: `sku_master`, `inventory`,
  `demand_history`, `supply`, `cost`, `customers`
- Keep each Skill focused on a single analytical question — do not combine unrelated procedures
  into one file
