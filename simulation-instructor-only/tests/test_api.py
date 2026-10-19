import pytest
import os
import json
from fastapi.testclient import TestClient
from server.app import app
import server.app as app_module
from server.config import ServerConfig, EnrollmentConfig, EnrollmentRecord
from server.factory_manager import FactoryManager


@pytest.fixture
def test_setup():
    test_token = "secret-queen-token-123"

    enrollment_cfg = EnrollmentConfig(
        enrollments=[
            EnrollmentRecord(
                attendee_id="queen-1",
                access_token=test_token,
            ),
            EnrollmentRecord(
                attendee_id="queen-2",
                access_token="token2",
            ),
        ],
    )

    srv_cfg = ServerConfig(
        port=8080,
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


def test_server_info(test_setup):
    """GET /v1/server returns epoch and matches manager state."""
    client, mgr, test_token = test_setup
    headers = {"Authorization": f"Bearer {test_token}"}

    r = client.get("/v1/server", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["server_epoch"] == mgr.get_server_epoch()
    assert data["contract_version"] == "1.0"
    assert data["active_factories"] == 0


def test_attendee_isolation(test_setup):
    """Bearer tokens are scoped to the enrolling attendee."""
    client, _, _ = test_setup

    # No token → 401
    r = client.get("/v1/server")
    assert r.status_code == 401

    # Wrong token → 401
    r = client.get("/v1/server", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401

    # Attendee 2 cannot reach a non-existent factory belonging to attendee 1
    r = client.get("/v1/factories/nonexistent-id", headers={"Authorization": "Bearer token2"})
    assert r.status_code == 404


def test_epoch_mismatch_rejected(test_setup):
    """Commands with a wrong X-Server-Epoch header get a 409."""
    client, mgr, test_token = test_setup
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Idempotency-Key": "idem-epoch-1",
        "X-Server-Epoch": "completely-wrong-epoch",
    }
    r = client.post("/v1/factories/fake-factory-id/start", json={}, headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "server_restarted"


def test_provision_factory_missing_idempotency_key(test_setup):
    """POST /v1/factories without Idempotency-Key returns 400."""
    client, mgr, test_token = test_setup
    headers = {"Authorization": f"Bearer {test_token}"}
    epoch = mgr.get_server_epoch()

    r = client.post(
        "/v1/factories",
        json={
            "bootstrap_server": "localhost:9092",
            "producer_credentials": {"api_key": "k", "api_secret": "s"},
        },
        headers={**headers, "X-Server-Epoch": epoch},
        # No Idempotency-Key header
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "missing_idempotency_key"
