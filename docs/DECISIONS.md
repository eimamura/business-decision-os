# DECISIONS.md

Lightweight daily log of key design decisions.

Historical decisions (2026-06-02 – 2026-06-03, P0–P23) archived at `docs/archive/v3/DECISIONS.md`.

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-04 | Add Ollama as dev LLM provider (`LLM_PROVIDER=ollama`) | Eliminate Anthropic API costs during local development; qwen2.5-coder:7b runs comfortably on 8 GB RAM in WSL2. `LLMClient` protocol unchanged. ADR: `docs/adr/2026-06-04-ollama-local-llm-provider.md` |
| 2026-06-04 | Store prompt/response in `llm_usage` via optional `LLMUsage` fields | Enable post-hoc LLM call inspection without external services (no MLflow/Langfuse required). Additive nullable columns; `UsageWriter` signature unchanged. Covered by `ClaudeClient` and `OllamaClient`. |
| 2026-06-04 | Extend Demand Agent with 8 analysis tools (Data Analysis Layer) | Demand planning = data analysis, not just forecasting. Agent must answer "why", "is it temporary", "which customer", "is the forecast trustworthy" — not only "what is the forecast". 4 must-have: `profile_demand_data`, `analyze_demand_trend`, `evaluate_forecast_accuracy`, `detect_demand_anomalies`. 4 next-tier: `analyze_seasonality`, `analyze_demand_drivers`, `segment_demand`, `compare_demand_periods`. `Tool` protocol and SQL guardrail `ALLOWED_READ_TABLES` are unchanged; tools use direct parameterized `execute_read_query` calls. |
