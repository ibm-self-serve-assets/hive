"""Unit tests for the Hive Orders & Capacity Calculator."""

import pytest
from pathlib import Path
from calculator import (
    CapacityCalculator,
    FactoryConfiguration,
    OptimalExpansionSimulator,
    OrderScheduleGenerator,
    StationSlot,
    UpgradeOptimizer,
    load_rules,
)


@pytest.fixture
def calc():
    return CapacityCalculator()


def test_load_rules_structure(calc):
    rules = calc.rules
    assert "simulation_time" in rules
    assert rules["simulation_time"]["max_sim_weeks"] in [1, 2]
    assert calc.max_sim_days == calc.max_sim_weeks * 7
    assert calc.max_sim_minutes == calc.max_sim_days * 24 * 60
    assert "resources" in rules
    assert "manufacturing" in rules
    assert "assembly" in rules
    assert "station_metadata" in rules
    assert "robot_metadata" in rules


def test_bom_calculations(calc):
    raw_bom = calc.get_raw_resources_per_robot("engineer")
    # Verify exact BOM quantities
    assert raw_bom["energy"] == 22
    assert raw_bom["resin"] == 3
    assert raw_bom["metals"] == 19
    assert raw_bom["silicon"] == 9
    assert raw_bom["copper"] == 18

    # Forager uses identical BOM
    forager_bom = calc.get_raw_resources_per_robot("forager")
    assert forager_bom == raw_bom


def test_initial_throughput_and_bottleneck(calc):
    init_config = calc.get_initial_configuration()
    analysis = calc.analyze_throughput(init_config)

    # Initial bottleneck must be metals (at L1, 10m interval -> 190m per robot)
    assert analysis["bottleneck_name"] == "Resource: metals"
    assert analysis["bottleneck_type"] == "resource"
    assert pytest.approx(analysis["max_robots_per_hour"], rel=1e-3) == 0.315789
    assert pytest.approx(analysis["max_robots_per_day"], rel=1e-3) == 7.5789


def test_upgrade_evaluation_and_roi(calc):
    init_config = calc.get_initial_configuration()
    optimizer = UpgradeOptimizer(calc)

    candidates = optimizer.get_candidate_actions(init_config, available_coins=500)
    assert len(candidates) > 0

    # Top action should target metals (the binding constraint)
    top_action = candidates[0]
    assert top_action.station_key == "metals"
    assert top_action.marginal_rate_increase_per_hour > 0


def test_expansion_simulation_1week(calc):
    sim = OptimalExpansionSimulator(calc)
    result = sim.simulate_expansion(total_sim_minutes=10080)

    assert result["total_sim_minutes"] == 10080
    assert result["total_robots_produced"] > 200
    assert result["upgrades_applied_count"] > 0
    assert len(result["production_curve"]) > 5
    assert result["final_robots_per_hour"] > 1.5


def test_expansion_simulation_2week(calc):
    sim = OptimalExpansionSimulator(calc)
    result = sim.simulate_expansion(total_sim_minutes=20160)

    assert result["total_sim_minutes"] == 20160
    assert result["total_robots_produced"] > 400
    assert result["final_robots_per_hour"] > 2.0


def test_order_schedule_generation(calc):
    order_gen = OrderScheduleGenerator(calc)
    orders = order_gen.generate_order_schedule(sim_duration_weeks=2, difficulty="standard")

    assert len(orders) >= 5
    # Milestone 1 & 2 checks
    assert orders[0].order_id == "ORD-001"
    assert orders[0].total_quantity == 1
    assert orders[0].deadline_sim_minute == 1440

    assert orders[1].order_id == "ORD-002"
    assert orders[1].total_quantity == 2
    assert orders[1].deadline_sim_minute == 2880

    # Total ordered robots across 2 weeks should be balanced within achievable capacity
    total_ordered = sum(o.total_quantity for o in orders)
    assert 200 <= total_ordered <= 800
