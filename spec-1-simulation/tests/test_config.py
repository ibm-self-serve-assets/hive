import os
import pytest
from server.config import ServerConfig, load_enrollment_config


def test_server_config_loading():
    os.environ["PORT"] = "9000"
    os.environ["FACTORY_TTL_SECONDS"] = "1800"

    try:
        cfg = ServerConfig.load_from_env()
        assert cfg.port == 9000
        assert cfg.factory_ttl_seconds == 1800
    finally:
        del os.environ["PORT"]
        del os.environ["FACTORY_TTL_SECONDS"]


def test_enrollment_config_loading():
    en_cfg = load_enrollment_config()
    assert len(en_cfg.enrollments) >= 1

def test_obsolete_config_rejection():
    os.environ["FACTORY_BACKLOG_LIMIT_EVENTS"] = "100"
    with pytest.raises(ValueError, match="FACTORY_BACKLOG_LIMIT_EVENTS is obsolete"):
        ServerConfig.load_from_env()
    del os.environ["FACTORY_BACKLOG_LIMIT_EVENTS"]

    os.environ["DATABASE_URL"] = "postgresql://..."
    with pytest.raises(ValueError, match="DATABASE_URL is obsolete"):
        ServerConfig.load_from_env()
    del os.environ["DATABASE_URL"]
