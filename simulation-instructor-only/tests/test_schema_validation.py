import json
import pytest
from pathlib import Path
from jsonschema import Draft202012Validator
from server.simulation import SimulationRun


@pytest.fixture
def schemas():
    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    shared_schemas_dir = Path(__file__).resolve().parent.parent.parent / "spec-shared" / "schemas"
    with open(schemas_dir / "event_envelope.json", "r") as f:
        envelope_schema = json.load(f)
    with open(shared_schemas_dir / "event_payloads.json", "r") as f:
        payloads_schema = json.load(f)
    return envelope_schema, payloads_schema


def test_schema_conformance(schemas):
    envelope_schema, payloads_schema = schemas
    envelope_validator = Draft202012Validator(envelope_schema)
    # Schema definitions are keyed by the exact event_type string emitted on the wire.
    # factory.state and connection.test are infrastructure events validated separately.
    payload_validators = {
        event_type: Draft202012Validator(defn)
        for event_type, defn in payloads_schema["topics"].items()
        if event_type != "factory.state"
    }

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
        lifecycle_status="running",
    )

    # 1. Initial snapshot — validate envelope and factory.state payload
    _, snap_event = sim.create_snapshot_event(event_seq_generator=gen_seq)
    envelope_validator.validate(snap_event.model_dump())
    Draft202012Validator(payloads_schema["topics"]["factory.state"]).validate(snap_event.payload)

    # 2. Scheduling events
    events = sim.initial_scheduling(event_seq_generator=gen_seq)
    for _, ev in events:
        envelope_validator.validate(ev.model_dump())
        if ev.event_type in payload_validators:
            payload_validators[ev.event_type].validate(ev.payload)

    # 3. Advance and seed parts to test assembly event schema validation
    events_adv = sim.advance_to(2000000, event_seq_generator=gen_seq)
    sim.parts["chassis"] = 1
    sim.parts["electronics"] = 3
    sim.parts["battery"] = 2
    sim.parts["actuator"] = 8
    events_adv += sim.advance_to(3000000, event_seq_generator=gen_seq)

    seen_types = set()
    for _, ev in events_adv:
        envelope_validator.validate(ev.model_dump())
        seen_types.add(ev.event_type)
        if ev.event_type in payload_validators:
            payload_validators[ev.event_type].validate(ev.payload)
        elif ev.event_type != "factory.state":
            # Any non-snapshot event type must have a schema definition
            pytest.fail(f"No payload schema definition for event_type '{ev.event_type}'")

    # Every activity event type the sim can emit must appear in the schema
    expected_activity_types = {
        "gathering.started", "gathering.completed", "gathering.blocked",
        "manufacturing.started", "manufacturing.completed", "manufacturing.blocked",
        "assembly.started", "assembly.completed", "assembly.blocked",
    }
    missing_from_schema = expected_activity_types - set(payload_validators.keys())
    assert not missing_from_schema, f"event_types missing from event_payloads.json: {missing_from_schema}"

    # Confirm the sim actually produced assembly events in this run
    assert {"assembly.started", "assembly.completed"} <= seen_types

    # assembly.completed payload spot-check
    assembly_completions = [ev for _, ev in events_adv if ev.event_type == "assembly.completed"]
    assert all(ev.payload["output_type"] == "engineer" for ev in assembly_completions)

    # 4. Final snapshot conforms
    _, final_snap = sim.create_snapshot_event(event_seq_generator=gen_seq)
    Draft202012Validator(payloads_schema["topics"]["factory.state"]).validate(final_snap.payload)
    assert final_snap.payload["completed_robots"]["last_robot_id"] == "engineer"
