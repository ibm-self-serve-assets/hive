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
        speed=1,
        lifecycle_status="running",
    )

    # Start scheduling at time 0
    events = sim.initial_scheduling(event_seq_generator=gen_seq)
    
    # At time 0: delivery arrives (resin 4, silicon 6, metals 12, copper 20, energy 6)
    # Then 4 parts stations start:
    # structural_molding: consumes 1 resin, 1 metals -> completes at 6000ms
    # electronics_assembly: consumes 1 silicon, 1 copper -> completes at 4000ms
    # actuator_fabrication: consumes 1 metals, 1 copper -> completes at 2000ms
    # battery_assembly: consumes 1 energy, 1 copper, 1 metals -> completes at 5000ms
    assert sim.resources["resin"] == 3
    assert sim.resources["silicon"] == 5
    assert sim.resources["metals"] == 9
    assert sim.resources["copper"] == 17
    assert sim.resources["energy"] == 5
    assert len(sim.active_jobs) == 4

    # Advance clock to 2000 ms: Actuator completes (took 2s)
    events_2s = sim.advance_to(2000, event_seq_generator=gen_seq)
    assert sim.parts["actuator"] >= 1
    # Actuator fabrication may start next actuator job if resources available!
    # Metals (9->8), Copper (17->16) -> starts another actuator job!
    assert "actuator_fabrication" in sim.active_jobs

    # Advance clock to 25000 ms: Across 20s delivery and part completions
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
        speed=1,
        lifecycle_status="running",
    )

    sim.initial_scheduling(event_seq_generator=gen_seq)
    sim.advance_to(60000, event_seq_generator=gen_seq)  # 60 simulated seconds (3 deliveries)

    rules = get_simulation_rules()
    
    # Total delivered resources
    total_deliveries = sim.delivery_sequence
    total_delivered_resin = total_deliveries * rules.delivery.resources["resin"]
    
    # Calculate currently available + consumed in active jobs + converted to parts
    # For resin: only structural molding uses 1 resin -> makes 1 chassis
    # Chassis in inventory + active chassis job + chassis in worker assembly + chassis in completed workers
    active_chassis_job = 1 if "structural_molding" in sim.active_jobs else 0
    active_worker_job = 1 if "worker_assembly" in sim.active_jobs else 0
    total_chassis = sim.parts["chassis"] + active_worker_job * 1 + sim.completed_workers_count * 1
    
    total_resin_accounted = sim.resources["resin"] + active_chassis_job * 1 + total_chassis * 1
    assert total_resin_accounted == total_delivered_resin
