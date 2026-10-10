import json
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ConnectionProfile(BaseModel):
    bootstrap_servers: str
    security_protocol: str = "SASL_SSL"
    sasl_mechanism: str = "PLAIN"


class EnrollmentRecord(BaseModel):
    attendee_id: str
    token_hash: str
    connection_profile_id: str
    topic_prefix: str
    consumer_group_prefix: str
    expires_at: str


class EnrollmentConfig(BaseModel):
    workshop_id: str
    connection_profiles: Dict[str, ConnectionProfile]
    enrollments: List[EnrollmentRecord]

    def find_by_token(self, token: str) -> Optional[EnrollmentRecord]:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        for rec in self.enrollments:
            if rec.token_hash == token_hash:
                return rec
        return None

    def find_by_attendee_id(self, attendee_id: str) -> Optional[EnrollmentRecord]:
        for rec in self.enrollments:
            if rec.attendee_id == attendee_id:
                return rec
        return None


class ServerConfig(BaseModel):
    port: int = 8080
    enrollment_config_path: str
    max_factories: int = 25
    factory_ttl_seconds: int = 21600
    factory_buffer_limit_events: int = 10000
    factory_buffer_limit_bytes: int = 16777216
    sim_tick_milliseconds: int = 100
    snapshot_interval_milliseconds: int = 200

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> "ServerConfig":
        # Check for obsolete or forbidden variables in os.environ and env file
        # Check candidate .env paths if env_path not explicitly supplied
        candidate_paths = []
        if env_path:
            candidate_paths.append(env_path)
        else:
            candidate_paths.extend([
                os.path.join(os.getcwd(), ".env"),
                os.path.join(Path(__file__).resolve().parent.parent, ".env"),
            ])

        env_file_values = {}
        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            env_file_values[k] = v
                break

        # Explicit os.environ values take precedence over .env file values
        env_dict = {**env_file_values, **dict(os.environ)}

        if "FACTORY_BACKLOG_LIMIT_EVENTS" in env_dict:
            raise ValueError(
                "FACTORY_BACKLOG_LIMIT_EVENTS is obsolete. Use FACTORY_BUFFER_LIMIT_EVENTS instead."
            )
        if "DATABASE_URL" in env_dict:
            raise ValueError(
                "DATABASE_URL is obsolete/unsupported. Memory-only simulation requires no database."
            )
        if "CREDENTIAL_ENCRYPTION_KEY" in env_dict:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY is obsolete/unsupported. In-memory secrets are not encrypted."
            )

        enrollment_path = env_dict.get("ENROLLMENT_CONFIG_PATH", "")
        if not enrollment_path or enrollment_path == "CHANGE_ME":
            raise ValueError("ENROLLMENT_CONFIG_PATH must be supplied and not CHANGE_ME")

        port = int(env_dict.get("PORT", 8080))
        max_factories = int(env_dict.get("MAX_FACTORIES", 25))
        factory_ttl = int(env_dict.get("FACTORY_TTL_SECONDS", 21600))
        buffer_events = int(env_dict.get("FACTORY_BUFFER_LIMIT_EVENTS", 10000))
        buffer_bytes = int(env_dict.get("FACTORY_BUFFER_LIMIT_BYTES", 16777216))
        tick_ms = int(env_dict.get("SIM_TICK_MILLISECONDS", 100))
        snapshot_ms = int(env_dict.get("SNAPSHOT_INTERVAL_MILLISECONDS", 200))

        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid PORT: {port}")
        if max_factories <= 0:
            raise ValueError("MAX_FACTORIES must be positive")
        if factory_ttl <= 0:
            raise ValueError("FACTORY_TTL_SECONDS must be positive")
        if buffer_events <= 0:
            raise ValueError("FACTORY_BUFFER_LIMIT_EVENTS must be positive")
        if buffer_bytes <= 0:
            raise ValueError("FACTORY_BUFFER_LIMIT_BYTES must be positive")
        if tick_ms <= 0:
            raise ValueError("SIM_TICK_MILLISECONDS must be positive")
        if snapshot_ms <= 0:
            raise ValueError("SNAPSHOT_INTERVAL_MILLISECONDS must be positive")

        return cls(
            port=port,
            enrollment_config_path=enrollment_path,
            max_factories=max_factories,
            factory_ttl_seconds=factory_ttl,
            factory_buffer_limit_events=buffer_events,
            factory_buffer_limit_bytes=buffer_bytes,
            sim_tick_milliseconds=tick_ms,
            snapshot_interval_milliseconds=snapshot_ms,
        )


def load_enrollment_config(path: str) -> EnrollmentConfig:
    resolved_path = path
    if not os.path.exists(resolved_path):
        # Try resolving relative to package root
        pkg_root = Path(__file__).resolve().parent.parent
        alt_path = pkg_root / path
        if alt_path.exists():
            resolved_path = str(alt_path)
        else:
            raise FileNotFoundError(f"Enrollment config file not found: {path}")
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    config = EnrollmentConfig(**data)
    
    # Validate uniqueness
    attendees = set()
    topic_prefixes = set()
    for rec in config.enrollments:
        if rec.attendee_id in attendees:
            raise ValueError(f"Duplicate attendee_id in enrollment config: {rec.attendee_id}")
        attendees.add(rec.attendee_id)
        if rec.topic_prefix in topic_prefixes:
            raise ValueError(f"Duplicate topic_prefix in enrollment config: {rec.topic_prefix}")
        topic_prefixes.add(rec.topic_prefix)
        if rec.connection_profile_id not in config.connection_profiles:
            raise ValueError(
                f"Unknown connection_profile_id '{rec.connection_profile_id}' for attendee '{rec.attendee_id}'"
            )

    return config
