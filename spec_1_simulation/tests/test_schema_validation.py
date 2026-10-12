import os
import json
import pytest
from pathlib import Path
from jsonschema import validate, Draft202012Validator
from server.simulation import SimulationRun
from server.rules import get_simulation_rules


@pytest.fixture
def schemas():
    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    with open(schemas_dir / "event_envelope.json", "r") as f:
        envelope_schema = json.load(f)
    with open(schemas_dir / "event_payloads.json", "r") as f:
        payloads_schema = json.load(f)
    return envelope_schema, payloads_schema


def test_schema_conformance(schemas):
    envelope_schema, payloads_schema = schemas
    validator = Draft202012Validator(envelope_schema)

    seq = 0
    def gen_seq():
        nonlocal seq
        seq += 1
        return seq

    sim = SimulationRun(
        factory_id="11111111-1111-1111-1111-111111111111",
        server_epoch="22222222-2222-2222-2222-222222222222",
        run_id="33333333-3333-3333-3333-333333333333",
        run_generation=1,
        speed=1,
        lifecycle_status="running",
    )

    # 1. Initial snapshot
    _, snap_event = sim.create_snapshot_event(event_seq_generator=gen_seq)
    validator.validate(snap_event.model_dump())

    # Validate state payload
    Draft202012Validator(payloads_schema["definitions"]["factory_state"]).validate(snap_event.payload)

    # 2. Scheduling events
    events = sim.initial_scheduling(event_seq_generator=gen_seq)
    for topic_suffix, ev in events:
        validator.validate(ev.model_dump())
        if ev.event_type == "resource.delivered":
            Draft202012Validator(payloads_schema["definitions"]["resource_delivered"]).validate(ev.payload)
        elif ev.event_type == "manufacturing.started":
            Draft202012Validator(payloads_schema["definitions"]["job_started"]).validate(ev.payload)

    # 3. Advance to completion
    events_adv = sim.advance_to(10000, event_seq_generator=gen_seq)
    for topic_suffix, ev in events_adv:
        validator.validate(ev.model_dump())
        if ev.event_type == "manufacturing.completed":
            Draft202012Validator(payloads_schema["definitions"]["part_produced"]).validate(ev.payload)
        elif ev.event_type == "assembly.completed":  # unchanged
            Draft202012Validator(payloads_schema["definitions"]["robot_assembled"]).validate(ev.payload)
