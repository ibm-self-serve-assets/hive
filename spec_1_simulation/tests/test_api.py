import pytest
import os
import json
import hashlib
from fastapi.testclient import TestClient
from server.app import app
import server.app as app_module
from server.config import ServerConfig, EnrollmentConfig, EnrollmentRecord, ConnectionProfile
from server.factory_manager import FactoryManager


@pytest.fixture
def test_setup():
    test_token = "secret-attendee-token-123"
    token_hash = hashlib.sha256(test_token.encode("utf-8")).hexdigest()

    enrollment_cfg = EnrollmentConfig(
        workshop_id="workshop-test",
        connection_profiles={
            "test-profile": ConnectionProfile(
                bootstrap_servers="localhost:9092",
                security_protocol="PLAINTEXT",
                sasl_mechanism="PLAIN",
            )
        },
        enrollments=[
            EnrollmentRecord(
                attendee_id="attendee-1",
                token_hash=token_hash,
                connection_profile_id="test-profile",
                topic_prefix="hive.test.attendee-1",
                consumer_group_prefix="cg-attendee-1",
                expires_at="2035-01-01T00:00:00Z",
            ),
            EnrollmentRecord(
                attendee_id="attendee-2",
                token_hash=hashlib.sha256(b"token2").hexdigest(),
                connection_profile_id="test-profile",
                topic_prefix="hive.test.attendee-2",
                consumer_group_prefix="cg-attendee-2",
                expires_at="2035-01-01T00:00:00Z",
            ),
        ],
    )

    srv_cfg = ServerConfig(
        port=8080,
        enrollment_config_path="/fake/path",
        max_factories=5,
        factory_ttl_seconds=3600,
        factory_buffer_limit_events=1000,
        factory_buffer_limit_bytes=1000000,
        sim_tick_milliseconds=50,
        snapshot_interval_milliseconds=100,
    )

    mgr = FactoryManager(srv_cfg, enrollment_cfg)
    app_module.server_config = srv_cfg
    app_module.enrollment_config = enrollment_cfg
    app_module.factory_manager = mgr

    client = TestClient(app)
    return client, mgr, test_token


def test_health_endpoints(test_setup):
    client, mgr, _ = test_setup
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_factory_lifecycle_and_isolation(test_setup):
    client, mgr, test_token = test_setup
    headers = {"Authorization": f"Bearer {test_token}"}

    # 1. Get server info
    r = client.get("/v1/server", headers=headers)
    assert r.status_code == 200
    epoch = r.json()["server_epoch"]
    assert epoch == mgr.get_server_epoch()

    # 2. Provision factory
    prov_req = {
        "connection_profile_id": "test-profile",
        "producer_credentials": {
            "api_key": "test_key",
            "api_secret": "test_secret",
        },
    }
    r = client.post(
        "/v1/factories",
        json=prov_req,
        headers={**headers, "Idempotency-Key": "idem-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 202
    res = r.json()
    factory_id = res["factory_id"]
    operation_id = res["operation_id"]

    # 3. Check operation status
    r = client.get(f"/v1/operations/{operation_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "succeeded")

    # 4. List factories
    r = client.get("/v1/factories", headers=headers)
    assert r.status_code == 200
    facts = r.json()["factories"]
    assert len(facts) == 1
    assert facts[0]["factory_id"] == factory_id

    # 5. Unauthorized attendee isolation check
    headers_att2 = {"Authorization": "Bearer token2"}
    r = client.get(f"/v1/factories/{factory_id}", headers=headers_att2)
    assert r.status_code == 404

    # 6. Start factory
    r = client.post(
        f"/v1/factories/{factory_id}/start",
        json={"expected_generation": 1},
        headers={**headers, "Idempotency-Key": "start-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle_status"] == "running"

    # 7. Speed change
    r = client.post(
        f"/v1/factories/{factory_id}/speed",
        json={"expected_generation": 1, "speed": 5},
        headers={**headers, "Idempotency-Key": "speed-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 200

    # 8. Pause
    r = client.post(
        f"/v1/factories/{factory_id}/pause",
        json={"expected_generation": 1},
        headers={**headers, "Idempotency-Key": "pause-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle_status"] == "paused"

    # 9. Stop
    r = client.post(
        f"/v1/factories/{factory_id}/stop",
        json={"expected_generation": 1},
        headers={**headers, "Idempotency-Key": "stop-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle_status"] == "stopped"

    # 10. Start on stopped returns 409
    r = client.post(
        f"/v1/factories/{factory_id}/start",
        json={"expected_generation": 1},
        headers={**headers, "Idempotency-Key": "start-2", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 409

    # 11. Restart at zero -> generation 2
    r = client.post(
        f"/v1/factories/{factory_id}/restart",
        json={"expected_generation": 1, "start": True},
        headers={**headers, "Idempotency-Key": "restart-1", "X-Server-Epoch": epoch},
    )
    assert r.status_code == 200
    assert r.json()["run_generation"] == 2
    assert r.json()["lifecycle_status"] == "running"

    # 12. Epoch mismatch returns 409
    r = client.post(
        f"/v1/factories/{factory_id}/pause",
        json={"expected_generation": 2},
        headers={**headers, "Idempotency-Key": "pause-2", "X-Server-Epoch": "wrong-epoch"},
    )
    assert r.status_code == 409
