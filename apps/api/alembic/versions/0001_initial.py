"""Initial schema — all Phase 0-9 tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # -------------------------------------------------------------------------
    # System tables
    # -------------------------------------------------------------------------

    op.execute("""
        CREATE TABLE users (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email       TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst','approver','admin')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE decision_sessions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id),
            goal        TEXT NOT NULL,
            status      TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE agent_steps (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id       UUID NOT NULL REFERENCES decision_sessions(id),
            specialist_role  TEXT NOT NULL,
            step_type        TEXT NOT NULL,
            input_json       JSONB,
            output_json      JSONB,
            started_at       TIMESTAMPTZ,
            ended_at         TIMESTAMPTZ
        );
    """)

    op.execute("""
        CREATE TABLE tool_calls (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_step_id    UUID NOT NULL REFERENCES agent_steps(id),
            tool_name        TEXT NOT NULL,
            input_json       JSONB,
            output_json      JSONB,
            status           TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed')),
            requires_approval BOOLEAN NOT NULL DEFAULT false,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE llm_usage (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_step_id       UUID NOT NULL REFERENCES agent_steps(id),
            model               TEXT NOT NULL,
            input_tokens        INT NOT NULL,
            output_tokens       INT NOT NULL,
            cache_read_tokens   INT NOT NULL DEFAULT 0,
            cache_write_tokens  INT NOT NULL DEFAULT 0,
            total_cost_usd      NUMERIC(10,6) NOT NULL,
            request_id          TEXT,
            latency_ms          INT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE llm_pricing (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model                    TEXT NOT NULL UNIQUE,
            input_cost_per_1k        NUMERIC(10,6) NOT NULL,
            output_cost_per_1k       NUMERIC(10,6) NOT NULL,
            cache_read_cost_per_1k   NUMERIC(10,6) NOT NULL DEFAULT 0,
            cache_write_cost_per_1k  NUMERIC(10,6) NOT NULL DEFAULT 0,
            effective_from           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE memories (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scope       TEXT NOT NULL,
            type        TEXT NOT NULL CHECK (type IN ('decision','forecast_error','user_policy','failure_case')),
            content     TEXT NOT NULL,
            embedding   vector(1536),
            metadata    JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE audit_log (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id      UUID,
            agent_step_id   UUID,
            tool_call_id    UUID,
            event_type      TEXT NOT NULL,
            payload         JSONB NOT NULL,
            audit_hash      TEXT NOT NULL,
            prev_audit_hash TEXT,
            actor           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE approvals (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id          UUID NOT NULL REFERENCES decision_sessions(id),
            recommendation_id   UUID,
            parent_approval_id  UUID REFERENCES approvals(id),
            status              TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','needs_revision','expired')),
            weight_override_json JSONB,
            reason              TEXT,
            actor               TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE recommendations (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id            UUID NOT NULL REFERENCES decision_sessions(id),
            primary_candidate_json JSONB NOT NULL,
            alternatives_json     JSONB NOT NULL,
            tradeoff_json         JSONB NOT NULL,
            rationale             TEXT NOT NULL,
            risk_level            TEXT NOT NULL CHECK (risk_level IN ('low','medium','high')),
            requires_approval     BOOLEAN NOT NULL DEFAULT false,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE candidates (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recommendation_id     UUID NOT NULL REFERENCES recommendations(id),
            action_json           JSONB NOT NULL,
            kpi_scores_json       JSONB NOT NULL,
            constraints_satisfied JSONB NOT NULL,
            constraints_violated  JSONB NOT NULL
        );
    """)

    op.execute("""
        CREATE TABLE kpi_scores (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES candidates(id),
            kpi_name     TEXT NOT NULL,
            value        NUMERIC NOT NULL,
            unit         TEXT NOT NULL,
            direction    TEXT NOT NULL CHECK (direction IN ('higher_better','lower_better'))
        );
    """)

    op.execute("""
        CREATE TABLE evaluations (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id    UUID NOT NULL REFERENCES decision_sessions(id),
            criteria_json JSONB NOT NULL,
            result_json   JSONB NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE forecast_runs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id      UUID NOT NULL REFERENCES decision_sessions(id),
            sku_id          TEXT NOT NULL,
            model_version   TEXT NOT NULL,
            horizon_days    INT NOT NULL,
            output_json     JSONB NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE simulation_runs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id   UUID NOT NULL REFERENCES decision_sessions(id),
            sku_id       TEXT NOT NULL,
            order_qty    NUMERIC NOT NULL,
            horizon_days INT NOT NULL,
            output_json  JSONB NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE optimization_runs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id      UUID NOT NULL REFERENCES decision_sessions(id),
            sku_id          TEXT NOT NULL,
            horizon_days    INT NOT NULL,
            candidates_json JSONB NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # -------------------------------------------------------------------------
    # Operational domain tables
    # -------------------------------------------------------------------------

    op.execute("""
        CREATE TABLE sku_master (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id               TEXT NOT NULL UNIQUE,
            name                 TEXT NOT NULL,
            category             TEXT,
            sku_type             TEXT NOT NULL CHECK (sku_type IN ('critical','standard','slow_moving')),
            moq                  NUMERIC NOT NULL,
            lead_time_days_mean  NUMERIC NOT NULL,
            lead_time_days_std   NUMERIC NOT NULL,
            holding_cost_pct     NUMERIC NOT NULL,
            unit_cost            NUMERIC NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE inventory (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id        TEXT NOT NULL REFERENCES sku_master(sku_id),
            warehouse_id  TEXT NOT NULL,
            on_hand       NUMERIC NOT NULL,
            on_order      NUMERIC NOT NULL,
            snapshot_date DATE NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE demand_history (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id     TEXT NOT NULL REFERENCES sku_master(sku_id),
            date       DATE NOT NULL,
            quantity   NUMERIC,
            is_missing BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE supply (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id           TEXT NOT NULL REFERENCES sku_master(sku_id),
            supplier_id      TEXT NOT NULL,
            order_date       DATE NOT NULL,
            expected_arrival DATE NOT NULL,
            quantity         NUMERIC NOT NULL,
            status           TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE cost (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id         TEXT NOT NULL REFERENCES sku_master(sku_id),
            period_start   DATE NOT NULL,
            period_end     DATE NOT NULL,
            cogs           NUMERIC NOT NULL,
            holding_cost   NUMERIC NOT NULL,
            ordering_cost  NUMERIC NOT NULL,
            stockout_cost  NUMERIC NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE customers (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id       TEXT NOT NULL UNIQUE,
            segment           TEXT NOT NULL CHECK (segment IN ('large','small','spot')),
            sku_affinity_json JSONB NOT NULL DEFAULT '{}',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # -------------------------------------------------------------------------
    # Indexes
    # -------------------------------------------------------------------------

    op.execute("""
        CREATE INDEX ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    """)

    op.execute("""
        CREATE INDEX ON audit_log (session_id, created_at);
    """)

    op.execute("""
        CREATE INDEX ON demand_history (sku_id, date);
    """)

    op.execute("""
        CREATE INDEX ON approvals (status, created_at);
    """)

    op.execute("""
        CREATE TABLE notifications (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id),
            approval_id UUID REFERENCES approvals(id),
            type        TEXT NOT NULL DEFAULT 'approval_pending',
            read        BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE policies (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            budget_soft_limit_usd NUMERIC(10,4) NOT NULL DEFAULT 10.0,
            budget_hard_limit_usd NUMERIC(10,4) NOT NULL DEFAULT 50.0,
            budget_period         TEXT NOT NULL DEFAULT 'session' CHECK (budget_period IN ('session','day','month')),
            updated_by            TEXT,
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX ON notifications (user_id, read, created_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.execute("DROP TABLE IF EXISTS cost CASCADE;")
    op.execute("DROP TABLE IF EXISTS supply CASCADE;")
    op.execute("DROP TABLE IF EXISTS demand_history CASCADE;")
    op.execute("DROP TABLE IF EXISTS inventory CASCADE;")
    op.execute("DROP TABLE IF EXISTS sku_master CASCADE;")
    op.execute("DROP TABLE IF EXISTS optimization_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS simulation_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS forecast_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS evaluations CASCADE;")
    op.execute("DROP TABLE IF EXISTS kpi_scores CASCADE;")
    op.execute("DROP TABLE IF EXISTS candidates CASCADE;")
    op.execute("DROP TABLE IF EXISTS recommendations CASCADE;")
    op.execute("DROP TABLE IF EXISTS approvals CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS memories CASCADE;")
    op.execute("DROP TABLE IF EXISTS llm_pricing CASCADE;")
    op.execute("DROP TABLE IF EXISTS llm_usage CASCADE;")
    op.execute("DROP TABLE IF EXISTS tool_calls CASCADE;")
    op.execute("DROP TABLE IF EXISTS agent_steps CASCADE;")
    op.execute("DROP TABLE IF EXISTS decision_sessions CASCADE;")
    op.execute("DROP TABLE IF EXISTS policies CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS vector;")
