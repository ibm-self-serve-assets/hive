import os
import json
import pytest
from pathlib import Path
from server.config import ServerConfig, load_enrollment_config


def test_server_config_loading(tmp_path):
    enrollment_file = tmp_path / "enrollment.json"
    enrollment_data = {
        "workshop_id": "test-ws",
        "connection_profiles": {
            "prof-1": {
                "bootstrap_servers": "localhost:9092",
                "security_protocol": "PLAINTEXT",
                "sasl_mechanism": "PLAIN"
            }
        },
        "enrollments": [
            {
                "attendee_id": "user1",
                "token_hash": "abc",
                "connection_profile_id": "prof-1",
                "topic_prefix": "hive.user1",
                "consumer_group_prefix": "cg.user1",
                "expires_at": "2030-01-01T00:00:00Z"
            }
        ]
    }
    with open(enrollment_file, "w") as f:
        json.dump(enrollment_data, f)

    os.environ["ENROLLMENT_CONFIG_PATH"] = str(enrollment_file)
    os.environ["PORT"] = "9000"
    os.environ["MAX_FACTORIES"] = "10"

    cfg = ServerConfig.load_from_env()
    assert cfg.port == 9000
    assert cfg.max_factories == 10
    assert cfg.factory_ttl_seconds == 21600

    en_cfg = load_enrollment_config(str(enrollment_file))
    assert en_cfg.workshop_id == "test-ws"
    assert len(en_cfg.enrollments) == 1
    assert en_cfg.find_by_attendee_id("user1") is not None


def test_obsolete_config_rejection(tmp_path):
    os.environ["FACTORY_BACKLOG_LIMIT_EVENTS"] = "100"
    with pytest.raises(ValueError, match="FACTORY_BACKLOG_LIMIT_EVENTS is obsolete"):
        ServerConfig.load_from_env()
    del os.environ["FACTORY_BACKLOG_LIMIT_EVENTS"]

    os.environ["DATABASE_URL"] = "postgresql://..."
    with pytest.raises(ValueError, match="DATABASE_URL is obsolete"):
        ServerConfig.load_from_env()
    del os.environ["DATABASE_URL"]
