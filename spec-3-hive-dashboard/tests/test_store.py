import os
import json
import pytest
from backend.config import BackendConfig
from backend.store import InMemProjectionStore
from backend.models import EventEnvelope


def test_backend_config_defaults(tmp_path):
    env_file = tmp_path / ".env"
    with open(env_file, "w") as f:
        f.write("LOCAL_BACKEND_PORT=8001\nLOCAL_FRONTEND_PORT=5174\nSIMULATION_SERVER_URL=http://localhost:8080\n")

    cfg = BackendConfig.load_from_env(str(env_file))
    assert cfg.local_backend_port == 8001
    assert cfg.local_frontend_port == 5174
    assert cfg.simulation_server_url == "http://localhost:8080"


def test_in_memory_projection_store():
    store = InMemProjectionStore(max_activity_events=10)
    store.reset_view(factory_id="factory-1", server_epoch="epoch-1")

    # Ingest activity event
    act_env = EventEnvelope(
        event_id="e-1",
        event_type="gathering.completed",
        schema_version=1,
        factory_id="factory-1",
        server_epoch="epoch-1",
        run_id="run-1",
        run_generation=1,
        event_sequence=1,
        state_revision=1,
        occurred_at="2026-01-01T00:00:00Z",
        sim_time_minutes=0,
        causation_id=None,
        payload={
            "job_id": "j-1",
            "resource_id": "resin",
            "quantity": 4,
        },
    )
    assert store.ingest_envelope(act_env) is True
    assert len(store.activity_events) == 1

    # Ingest duplicate should be ignored
    assert store.ingest_envelope(act_env) is False
    assert len(store.activity_events) == 1

    # Ingest snapshot
    snap_env = EventEnvelope(
        event_id="e-2",
        event_type="factory.state",
        schema_version=1,
        factory_id="factory-1",
        server_epoch="epoch-1",
        run_id="run-1",
        run_generation=1,
        event_sequence=2,
        state_revision=1,
        occurred_at="2026-01-01T00:00:00Z",
        sim_time_minutes=0,
        causation_id=None,
        payload={
            "lifecycle_status": "running",
            "running": True,
            "operational_error": None,
            "next_delivery_sim_time_ms": 20000,
            "next_delivery_in_ms": 20000,
            "resources": {"resin": 3, "silicon": 5, "metals": 9, "copper": 17, "energy": 5},
            "parts": {"chassis": 0, "electronics": 0, "actuator": 0, "battery": 0},
            "stations": [],
            "completed_robots": {"count": 0, "last_robot_id": None},
            "last_applied_command_id": None,
        },
    )
    assert store.ingest_envelope(snap_env) is True
    assert store.latest_snapshot is not None
    assert store.latest_snapshot.resources["resin"] == 3
    assert store.get_stream_health() == "live"
