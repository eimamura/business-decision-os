from __future__ import annotations

import pytest

from packages.domain.kpi import (
    days_on_hand,
    fill_rate,
    gross_margin_return_on_investment,
    inventory_turnover,
    reorder_point,
    safety_stock,
    service_level,
    total_supply_chain_cost,
)


def test_service_level_full():
    assert service_level(0, 90) == pytest.approx(1.0)


def test_service_level_partial():
    assert service_level(9, 90) == pytest.approx(0.9)


def test_inventory_turnover():
    assert inventory_turnover(1000.0, 250.0) == pytest.approx(4.0)


def test_days_on_hand():
    assert days_on_hand(100.0, 10.0) == pytest.approx(10.0)


def test_fill_rate():
    assert fill_rate(90.0, 100.0) == pytest.approx(0.9)


def test_total_supply_chain_cost():
    assert total_supply_chain_cost(100.0, 50.0, 25.0) == pytest.approx(175.0)


def test_reorder_point():
    assert reorder_point(10.0, 7.0, 20.0) == pytest.approx(90.0)


def test_safety_stock():
    assert safety_stock(1.65, 2.0, 5.0) == pytest.approx(16.5)


def test_gross_margin_roi():
    assert gross_margin_return_on_investment(500.0, 1000.0) == pytest.approx(0.5)
