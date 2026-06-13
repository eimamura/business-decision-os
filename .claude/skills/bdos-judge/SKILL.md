---
name: bdos-judge
description: LLM-as-a-Judge for BDOS agent responses. Evaluate quality dimensions, identify root causes (prompt/tool/model/missing), propose concrete fixes, and optionally create a task via bdos-orchestrator. Usage: /bdos-judge "<question>" "<answer>" or paste a conversation log.
---

# BDOS Judge — SKILL

## Purpose

Evaluate a BDOS product agent response using LLM-as-a-Judge methodology.
Identify *why* the response is low quality, propose a concrete fix, and support task creation.

This skill handles **evaluation and diagnosis**. It does not implement fixes — delegate those to `bdos-app-builder`.

## Invocation

```
/bdos-judge "<question>" "<answer>"
```

Or paste the conversation log directly. The judge will extract the question and answer.

## Required Reading

Before scoring, always read:
- `packages/tools/base.py` → `_ROLE_TOOL_ALLOWLIST` — which tools each agent role can call
- `packages/agent/control/control_agent.py` — system prompt for the primary agent
- If the question involves a specific domain tool, read that tool file under `packages/tools/`

This context is essential: without knowing what tools *were available*, tool_selection cannot be scored accurately.

## Process

1. **Separate inputs** — identify the user question and the agent answer from the input.

2. **Read tool context** — grep `_ROLE_TOOL_ALLOWLIST` for the relevant agent role. List the tools available for this question category.

3. **Score 5 dimensions** (each 0.0–1.0):

   | Dimension | Question to answer |
   |---|---|
   | `tool_selection` | Were all tools needed to answer this question actually called? |
   | `groundedness` | Is every claim in the answer backed by data returned from a tool? |
   | `relevance` | Does the answer directly address what the user asked? |
   | `completeness` | Are all required data points present (numbers, reasons, recommendations)? |
   | `reasoning` | Is the reasoning chain logical and traceable from data to conclusion? |

4. **Compute aggregate** — unweighted average of the 5 scores.
   - Pass: aggregate ≥ 0.65 AND all dimensions ≥ 0.6
   - Fail: any dimension < 0.6 OR aggregate < 0.65

5. **Classify root cause** — pick exactly one primary class:

   | Class | When to use |
   |---|---|
   | `prompt_instruction` | System prompt lacks a required instruction; agent had no reason to call the missing tools |
   | `tool_definition` | Tool description is misleading or ambiguous; agent called the wrong tool or misread output |
   | `model_limitation` | Model cannot reliably plan multi-tool sequences regardless of prompt; changing prompts alone won't fix it |
   | `missing_tool` | The data needed to answer doesn't have a tool; agent cannot retrieve it |

6. **Propose fix** — give specific, actionable changes:
   - For `prompt_instruction`: quote the exact line to add/change in the system prompt file
   - For `tool_definition`: quote the exact description change in the tool file
   - For `model_limitation`: suggest model upgrade, a judge gate, or a mandatory tool call scaffold
   - For `missing_tool`: name the tool to build and its expected input/output

7. **Offer task creation** — ask the user (in their language) whether to create a task via `bdos-orchestrator intake`.
   If Y: spawn `Agent(subagent_type="bdos-orchestrator", prompt="intake <fix description>")`.

## Output Format

**Language:** match the user's language (AGENTS.md §Language Convention). When the user writes in Japanese, translate all section labels to Japanese. When the user writes in English, use the English template below.

```markdown
## Judge Report

**Question:** <question>
**Answer (summary):** <one-sentence summary of the answer>

### Scores
| Dimension      | Score | Issue |
|---|---|---|
| tool_selection | 0.X   | <specific issue or "none"> |
| groundedness   | 0.X   | <specific issue or "none"> |
| relevance      | 0.X   | <specific issue or "none"> |
| completeness   | 0.X   | <specific issue or "none"> |
| reasoning      | 0.X   | <specific issue or "none"> |

**Aggregate:** 0.XX → ✅ PASS / ❌ FAIL

### Root Cause
**Class:** `<class>`
**Explanation:** <2–3 sentences explaining the mechanism — not the symptom, the cause>

### Proposed Fix
<numbered list of specific changes with file paths and quoted text where applicable>

### Next Action
→ Create a task via bdos-orchestrator intake? [Y/N]
```

**Japanese label mapping** (use when responding in Japanese):

| English | Japanese |
|---|---|
| Question | 質問 |
| Answer (summary) | 回答（要約） |
| Scores | スコア |
| Dimension / Issue | 次元 / 問題点 |
| Root Cause / Class / Explanation | 根本原因 / クラス / 説明 |
| Proposed Fix | 修正案 |
| Next Action | 次のアクション |

## Root Cause Class → Fix Ownership

| Class | Fix approach | Delegate to |
|---|---|---|
| `prompt_instruction` | Edit system prompt | `bdos-app-builder` |
| `tool_definition` | Edit tool description | `bdos-app-builder` |
| `model_limitation` | Model swap or structural constraint | Human decision + `bdos-app-builder` |
| `missing_tool` | New tool implementation | `bdos-app-builder` + `bdos-infra` |

## Constraints

- Do not modify any code files — evaluation only
- Do not create tasks without explicit user confirmation
- Do not score a response without first reading the tool allowlist — blind scoring is invalid
- If the input is ambiguous (can't separate question from answer), ask before scoring
- One primary root cause class per report — if multiple issues exist, name the most impactful one and list others under "その他の問題"
