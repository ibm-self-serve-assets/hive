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

    # At 10000 ms every resource's first cycle completes (energy 7, resin 3,
    # silicon 3, metals 2, copper 5). Stations then start from that inventory
    # at the same instant. Not every recipe can be satisfied at once, so some
    # stations start and others wait.
    sim.advance_to(10000, event_seq_generator=gen_seq)
    assert 0 < len(sim.active_jobs) < 4
    for qty in sim.resources.values():
        assert qty >= 0

    # Advance clock to 25000 ms: across further deliveries and part completions
    sim.advance_to(25000, event_seq_generator=gen_seq)
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

    total_resin_accounted = sim.resources["resin"] + (active_chassis_job + total_chassis) * resin_per_chassis
    assert total_resin_accounted == total_delivered_resin


def test_forager_placeholder_is_declared_but_not_scheduled():
    rules = get_simulation_rules()

    # Declared with the same recipe/duration as the engineer station
    assert rules.forager_assembly is not None
    assert rules.forager_assembly.station_id == "forager_assembly"
    assert rules.forager_assembly.inputs == rules.worker_assembly.inputs == {
        "chassis": 1, "electronics": 3, "battery": 2, "actuator": 8,
    }
    assert rules.forager_assembly.robots[0].name == "forager"
    assert rules.forager_assembly.robots[0].duration_ms == 10000

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
