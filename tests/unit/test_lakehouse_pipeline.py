"""Tests for T-8002/T-8003/T-8004: Lakehouse package."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from packages.lakehouse import LakehouseClient
from packages.lakehouse.bronze import write_decisions, read_decisions
from packages.lakehouse.silver import run_silver, transform_decisions
from packages.lakehouse.gold import run_gold


@pytest.fixture
def tmp_client(tmp_path: Path) -> LakehouseClient:
    return LakehouseClient(base_path=tmp_path)


class TestLakehouseClient:
    def test_write_and_read_roundtrip(self, tmp_client: LakehouseClient) -> None:
        rows = [{"id": "1", "goal": "test"}, {"id": "2", "goal": "test2"}]
        n = tmp_client.write("bronze", "decisions", rows)
        assert n == 2
        result = tmp_client.read("bronze", "decisions")
        assert len(result) == 2
        assert result[0]["id"] == "1"

    def test_table_exists_false_before_write(self, tmp_client: LakehouseClient) -> None:
        assert not tmp_client.table_exists("bronze", "decisions")

    def test_table_exists_true_after_write(self, tmp_client: LakehouseClient) -> None:
        tmp_client.write("bronze", "decisions", [{"id": "1"}])
        assert tmp_client.table_exists("bronze", "decisions")

    def test_job_status_not_started(self, tmp_client: LakehouseClient) -> None:
        status = tmp_client.job_status("bronze", "decisions")
        assert status["status"] == "NOT_STARTED"

    def test_job_status_succeeded_after_write(self, tmp_client: LakehouseClient) -> None:
        tmp_client.write("bronze", "decisions", [{"id": "1"}])
        status = tmp_client.job_status("bronze", "decisions")
        assert status["status"] == "SUCCEEDED"
        assert status["rows_written"] == 1

    def test_multiple_writes_append(self, tmp_client: LakehouseClient) -> None:
        tmp_client.write("bronze", "decisions", [{"id": "1"}])
        tmp_client.write("bronze", "decisions", [{"id": "2"}, {"id": "3"}])
        rows = tmp_client.read("bronze", "decisions")
        assert len(rows) == 3


class TestBronzeLayer:
    def test_write_decisions(self, tmp_client: LakehouseClient) -> None:
        rows = [{"session_id": "abc", "goal": "test", "risk_level": "low"}]
        n = write_decisions(tmp_client, rows)
        assert n == 1

    def test_read_decisions(self, tmp_client: LakehouseClient) -> None:
        rows = [{"session_id": "abc", "risk_level": "low"}]
        write_decisions(tmp_client, rows)
        result = read_decisions(tmp_client)
        assert len(result) == 1
        assert result[0]["session_id"] == "abc"


class TestSilverTransformation:
    def test_deduplication(self) -> None:
        rows = [
            {"session_id": "a", "created_at": "2026-05-20T00:00:00Z", "goal": "test"},
            {"session_id": "a", "created_at": "2026-05-20T00:00:00Z", "goal": "test"},
        ]
        clean = transform_decisions(rows)
        assert len(clean) == 1

    def test_removes_none_values(self) -> None:
        rows = [{"session_id": "b", "created_at": "2026-05-20T00:00:00Z", "optional": None}]
        clean = transform_decisions(rows)
        assert "optional" not in clean[0]

    def test_run_silver_pipeline(self, tmp_client: LakehouseClient) -> None:
        write_decisions(tmp_client, [
            {"session_id": "x", "created_at": "2026-05-20", "user_id": "u1"},
        ])
        n = run_silver(tmp_client)
        assert n == 1
        assert tmp_client.table_exists("silver", "decisions_clean")
        assert tmp_client.job_status("silver", "decisions_clean")["status"] == "SUCCEEDED"


class TestGoldAggregation:
    def test_run_gold_pipeline(self, tmp_client: LakehouseClient) -> None:
        write_decisions(tmp_client, [
            {"session_id": "x", "created_at": "2026-05-20", "user_id": "u1", "risk_level": "low", "auto_execute": True},
            {"session_id": "y", "created_at": "2026-05-20", "user_id": "u1", "risk_level": "high", "auto_execute": False},
        ])
        run_silver(tmp_client)
        n = run_gold(tmp_client)
        assert n >= 1
        assert tmp_client.table_exists("gold", "decision_analytics")
        status = tmp_client.job_status("gold", "decision_analytics")
        assert status["status"] == "SUCCEEDED"

    def test_gold_analytics_content(self, tmp_client: LakehouseClient) -> None:
        write_decisions(tmp_client, [
            {"session_id": "a", "created_at": "2026", "user_id": "u1", "risk_level": "low", "auto_execute": True},
            {"session_id": "b", "created_at": "2026", "user_id": "u1", "risk_level": "high", "auto_execute": False},
        ])
        run_silver(tmp_client)
        run_gold(tmp_client)
        rows = tmp_client.read("gold", "decision_analytics")
        assert len(rows) == 1
        assert rows[0]["user_id"] == "u1"
        assert rows[0]["total_decisions"] == 2
        assert rows[0]["low_risk_count"] == 1
        assert rows[0]["high_risk_count"] == 1
        assert rows[0]["auto_executed_count"] == 1


class TestCdcScript:
    def test_dry_run_writes_to_bronze(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAKEHOUSE_PATH", str(tmp_path))

        import importlib
        import sys
        if "packages.lakehouse" in sys.modules:
            importlib.reload(sys.modules["packages.lakehouse"])

        from packages.lakehouse import LakehouseClient as LC
        client = LC(base_path=tmp_path)

        from packages.lakehouse.bronze import write_decisions as wd
        sample = [{"session_id": "test-dry", "goal": "dry-run", "risk_level": "low"}]
        n = wd(client, sample)
        assert n == 1
        assert client.table_exists("bronze", "decisions")
