import pytest
import uuid
from server.simulation import SimulationRun
from server.rules import get_simulation_rules


def test_simulation_first_cycle():
    seq = 0
    def gen_seq():
        nonlocal seq
        seq += 1
        return seq

    sim = SimulationRun(
        factory_id=str(uuid.uuid4()),
        server_epoch=str(uuid.uuid4()),
        run_generation=1,
        lifecycle_status="running",
    )

    # Start scheduling at time 0: every resource begins its first delivery cycle,
    # but inventory is empty so no station can start yet.
    events = sim.initial_scheduling(event_seq_generator=gen_seq)
    assert [ev.event_type for _, ev in events] == ["gathering.started"] * 5
    assert all(qty == 0 for qty in sim.resources.values())
    assert len(sim.active_jobs) == 0

    # At 600000 ms (10 sim minutes) every resource's first cycle completes (+1 of each resource).
    sim.advance_to(600000, event_seq_generator=gen_seq)
    for qty in sim.resources.values():
        assert qty >= 0

    # Advance clock across further delivery cycles until stations satisfy recipes
    sim.advance_to(2000000, event_seq_generator=gen_seq)
    assert len(sim.active_jobs) > 0
    snap = sim.build_snapshot_payload()
    assert snap.resources["resin"] >= 0
    assert snap.resources["metals"] >= 0
    assert snap.resources["copper"] >= 0
    assert snap.resources["energy"] >= 0


def test_conservation_of_materials():
    seq = 0
    def gen_seq():
        nonlocal seq
        seq += 1
        return seq

    sim = SimulationRun(
        factory_id=str(uuid.uuid4()),
        server_epoch=str(uuid.uuid4()),
        run_generation=1,
        lifecycle_status="running",
    )

    events = sim.initial_scheduling(event_seq_generator=gen_seq)
    events += sim.advance_to(60000, event_seq_generator=gen_seq)  # 60 simulated seconds

    rules = get_simulation_rules()

    # Total resin delivered: sum of completed resin delivery cycles.
    total_delivered_resin = sum(
        ev.payload["quantity"]
        for _, ev in events
        if ev.event_type == "gathering.completed" and ev.payload["resource_id"] == "resin"
    )

    # Resin is consumed only by structural molding (rules.manufacturing recipe),
    # which turns it into chassis. Chassis end up in inventory, in an active
    # assembly job, or in completed robots.
    resin_per_chassis = rules.get_manufacturing("structural_molding").inputs["resin"]
    chassis_per_robot = rules.worker_assembly.inputs["chassis"]
    active_chassis_job = 1 if "structural_molding" in sim.active_jobs else 0
    active_robot_job = 1 if "worker_assembly" in sim.active_jobs else 0
    total_chassis = (
        sim.parts["chassis"]
        + active_robot_job * chassis_per_robot
        + sim.completed_robots_count * chassis_per_robot
    )

    staged_resin = sum(cart.get("resin", 0) for cart in sim.carts.values())
    total_resin_accounted = (
        sim.resources["resin"] + staged_resin + (active_chassis_job + total_chassis) * resin_per_chassis
    )
    assert total_resin_accounted == total_delivered_resin


def _new_sim():
    return SimulationRun(
        factory_id=str(uuid.uuid4()), server_epoch=str(uuid.uuid4()),
        lifecycle_status="running",
    )


def test_cart_accumulates_partial_inputs_across_passes():
    sim = _new_sim()
    seq = iter(range(1, 10**6))
    gen = lambda: next(seq)

    # Only 1 metals in stock: actuator fabrication (needs 2) must hold it, not lose it
    sim.completed_parts_count["actuator_fabrication"] = 0
    for st in ("structural_molding", "electronics_assembly", "battery_assembly"):
        sim.completed_parts_count[st] = 5  # lowest count => actuator stage first
    sim.resources.update({"energy": 1, "metals": 1, "copper": 1})
    sim._run_scheduling_pass(0, "t", gen)
    assert "actuator_fabrication" not in sim.active_jobs
    assert sim.carts["actuator_fabrication"] == {"energy": 1, "metals": 1, "copper": 1}
    assert sim.resources["metals"] == 0

    # A second metals delivery completes the cart and the job starts
    sim.resources["metals"] += 1
    sim._run_scheduling_pass(1, "t", gen)
    assert "actuator_fabrication" in sim.active_jobs
    assert sim.carts["actuator_fabrication"] == {}


def test_single_metal_stations_cannot_starve_actuator_fabrication():
    sim = _new_sim()
    seq = iter(range(1, 10**6))
    gen = lambda: next(seq)

    # Actuator fabrication has the fewest parts, so it is served first and keeps its metals
    for st in ("structural_molding", "electronics_assembly", "battery_assembly"):
        sim.completed_parts_count[st] = 5
    sim.resources.update({"energy": 10, "resin": 10, "copper": 10, "metals": 1})
    sim._run_scheduling_pass(0, "t", gen)
    assert sim.carts["actuator_fabrication"]["metals"] == 1
    assert "structural_molding" not in sim.active_jobs
    assert "battery_assembly" not in sim.active_jobs

    sim.resources["metals"] += 1  # next delivery
    sim._run_scheduling_pass(1, "t", gen)
    assert "actuator_fabrication" in sim.active_jobs


def test_assembly_cart_accumulates_parts_incrementally():
    sim = _new_sim()
    seq = iter(range(1, 10**6))
    gen = lambda: next(seq)

    sim.parts.update({"chassis": 1, "electronics": 3, "battery": 2, "actuator": 5})
    sim._run_scheduling_pass(0, "t", gen)
    assert "worker_assembly" not in sim.active_jobs
    assert sim.carts["worker_assembly"]["actuator"] == 5
    assert sim.parts["actuator"] == 0

    sim.parts["actuator"] += 3
    sim._run_scheduling_pass(1, "t", gen)
    assert "worker_assembly" in sim.active_jobs
    assert sim.carts["worker_assembly"] == {}
    assert all(v == 0 for v in sim.parts.values())


def test_forager_placeholder_is_declared_but_not_scheduled():
    rules = get_simulation_rules()

    # Declared with the same recipe/duration as the engineer station
    assert rules.forager_assembly is not None
    assert rules.forager_assembly.station_id == "forager_assembly"
    assert rules.forager_assembly.inputs == rules.worker_assembly.inputs == {
        "chassis": 1, "electronics": 3, "battery": 2, "actuator": 8,
    }
    assert rules.forager_assembly.robots[0].name == "forager"
    assert rules.forager_assembly.robots[0].duration_ms == 600000

    # ...but not scheduled: five stations, no forager events
    assert rules.station_order == [
        "structural_molding", "electronics_assembly", "actuator_fabrication",
        "battery_assembly", "worker_assembly",
    ]
    sim = SimulationRun(
        factory_id=str(uuid.uuid4()), server_epoch=str(uuid.uuid4()),
        lifecycle_status="running",
    )
    seq = iter(range(1, 10**6))
    events = sim.initial_scheduling(event_seq_generator=lambda: next(seq))
    events += sim.advance_to(600000, event_seq_generator=lambda: next(seq))
    assert all(ev.payload.get("output_id") != "forager" for _, ev in events)
    assert len(sim.build_snapshot_payload().stations) == 5
