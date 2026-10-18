import os
import json
import pytest
from fastapi.testclient import TestClient
import backend.app as app_module
from backend.app import app
from backend.store import InMemProjectionStore


def test_api_status_and_csrf():
    client = TestClient(app)
    
    # Get CSRF
    r = client.get("/api/csrf")
    assert r.status_code == 200
    csrf = r.json()["csrf_token"]
    assert csrf is not None

    # Get Status
    r = client.get("/api/status")
    assert r.status_code == 200
    res = r.json()
    assert "stream_health" in res
    assert "observed_state" in res


def test_csrf_protection_on_controls():
    client = TestClient(app)
    # Without CSRF header -> 403
    r = client.post("/api/controls", json={"command": "start"})
    assert r.status_code == 403

    # With CSRF header but not connected -> 400
    r_csrf = client.get("/api/csrf")
    token = r_csrf.json()["csrf_token"]
    r = client.post("/api/controls", json={"command": "start"}, headers={"X-CSRF-Token": token})
    assert r.status_code == 400
    assert r.json()["detail"]["error_code"] == "not_connected"
