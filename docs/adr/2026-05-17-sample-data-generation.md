# ADR: Sample Data Generation Strategy

**Date:** 2026-05-17
**Status:** Accepted
**Scope:** `scripts/generate_sample_data.py`, `data/sample/`

## Context

The Business Decision OS requires realistic operational data to exercise all agent tools
(SQL, Forecast, Simulation, Optimization) before real inventory data is available.
The generator must produce data that reflects real supply-chain statistical properties
without embedding actual customer data.

## Decisions

### 1. Negative Binomial Distribution for Demand Noise

**Decision:** Use `numpy.random.default_rng.negative_binomial(n, p)` for daily demand.

**Rationale:** Real retail/industrial demand is overdispersed — variance exceeds the mean.
A Normal distribution forces variance = mean (Poisson) or allows variance < mean, neither
of which matches observed demand patterns. The Negative Binomial naturally models
overdispersion with a single dispersion parameter. Dispersion is set to 0.3 (std/mean),
giving variance = (0.3 * mean)^2, which implies n = mean^2 / (variance - mean). This
produces demand that clusters around the mean with heavier tails than a Poisson process,
matching real SKU-level demand distributions.

**Alternatives considered:**
- Normal distribution: discarded because it allows negative values and underestimates tail risk.
- Poisson distribution: discarded because it constrains variance = mean, ruling out overdispersion.
- Empirical bootstrapping: discarded because it requires real historical data.

### 2. Random Seed Policy

**Decision:** Default seed = 42. Override with `--seed N` CLI flag.

**Rationale:** A fixed default seed ensures every developer and CI run produces byte-identical
output. The `--seed` override allows generating alternative datasets for sensitivity analysis
without modifying the default corpus. The seed is passed explicitly to
`numpy.random.default_rng(seed)` rather than a global state mutation, making the dependency
on seed traceable in code.

### 3. Deterministic Missing Data Pattern

**Decision:** Missing data injection is deterministic under the seed, not random in an
uncontrolled sense.

**Rationale:** Tests must be able to assert exact NULL rates and positions. Using a
seeded RNG for NULL selection (same seed as demand generation) guarantees that:
- Unit tests can assert a ~2% NULL rate ±0.5% without flakiness.
- Integration tests can assert the 7-day contiguous gap covers days 60–66 of year 1.
- CI runs never produce different null masks across machines.

The 7-day gap models a real ERP outage scenario; deterministic placement makes the gap
useful as a regression fixture.

### 4. Seasonal Model

**Decision:** Additive sine wave: `multiplier = 1 + amplitude * sin(2π * day_of_year / period)`.

**Rationale:** An additive multiplier preserves the base demand level and makes the
seasonal effect interpretable: amplitude = 0.6 means demand oscillates ±60% around the
base. Multiplicative models (exponential) produce unbounded growth under compounding,
which is inappropriate for a fixed 24-month window. The sine wave is the simplest
continuous periodic model; it is sufficient to exercise the Forecast stub's NULL-aware
moving average and to demonstrate seasonal KPI variation in the UI.

**SKUs with seasonal amplitude > 0:** SKU-013, SKU-014, SKU-023, SKU-026.

### 5. Supply Order Count and Lead Time

**Decision:** 3–5 supply orders per SKU. Lead time sampled from
`LogNormal(μ = ln(mean_lt), σ = std/mean)`.

**Rationale:** LogNormal is the standard industrial model for lead time, as it is
always positive and right-skewed (occasional long delays). Using `std/mean` as the
log-space sigma preserves the coefficient of variation from ground-truth parameters.

## Consequences

- `data/sample/ground_truth/` is never read by any non-generator code. Enforced by
  `AGENTS.md` convention and the SQL Tool allowlist.
- The generator is idempotent: re-running overwrites outputs with identical content
  (same seed).
- Changing the seed invalidates all cassettes and fixtures; record in the DECISIONS.md
  when doing so intentionally.
- The 2% NULL rate and 7-day gap are baked into `tests/unit/test_generate_sample_data.py`
  assertions; changes to the injection logic require updating those tests.
