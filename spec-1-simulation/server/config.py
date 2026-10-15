import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class EnrollmentRecord(BaseModel):
    attendee_id: str
    access_token: str


class EnrollmentConfig(BaseModel):
    enrollments: List[EnrollmentRecord]

    def find_by_token(self, token: str) -> Optional[EnrollmentRecord]:
        for rec in self.enrollments:
            if rec.access_token == token:
                return rec
        return None

    def find_by_attendee_id(self, attendee_id: str) -> Optional[EnrollmentRecord]:
        for rec in self.enrollments:
            if rec.attendee_id == attendee_id:
                return rec
        return None


class ServerConfig(BaseModel):
    port: int = 8080
    factory_ttl_seconds: int = 3600
    factory_buffer_limit_events: int = 10000
    factory_buffer_limit_bytes: int = 16777216
    sim_tick_milliseconds: int = 100
    snapshot_interval_milliseconds: int = 200

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> "ServerConfig":
        # Load .env into os.environ. When an explicit path is given (e.g. in
        # tests) we override so that file wins. In normal startup we don't
        # overwrite values already set in the shell environment.
        if env_path:
            load_dotenv(env_path, override=True)
        else:
            # Try cwd first, then the package root (one level above server/).
            loaded = load_dotenv(override=False)
            if not loaded:
                load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

        env_dict = dict(os.environ)

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

        port = int(env_dict.get("PORT", 8080))
        factory_ttl = int(env_dict.get("FACTORY_TTL_SECONDS", 3600))
        buffer_events = int(env_dict.get("FACTORY_BUFFER_LIMIT_EVENTS", 10000))
        buffer_bytes = int(env_dict.get("FACTORY_BUFFER_LIMIT_BYTES", 16777216))
        tick_ms = int(env_dict.get("SIM_TICK_MILLISECONDS", 100))
        snapshot_ms = int(env_dict.get("SNAPSHOT_INTERVAL_MILLISECONDS", 200))

        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid PORT: {port}")
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
            factory_ttl_seconds=factory_ttl,
            factory_buffer_limit_events=buffer_events,
            factory_buffer_limit_bytes=buffer_bytes,
            sim_tick_milliseconds=tick_ms,
            snapshot_interval_milliseconds=snapshot_ms,
        )


def _resolve_env_refs(data: Any) -> Any:
    """
    Recursively walks a parsed JSON structure and replaces any string value
    matching the pattern ${ENV_VAR_NAME} with the corresponding os.environ value.
    Raises ValueError if the referenced variable is not set or is empty.
    """
    if isinstance(data, dict):
        return {k: _resolve_env_refs(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_refs(v) for v in data]
    if isinstance(data, str):
        match = re.fullmatch(r'\$\{([^}]+)\}', data.strip())
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name, "")
            if not value:
                raise ValueError(
                    f"Enrollment config references ${{{var_name}}} but that "
                    f"environment variable is not set."
                )
            return value
    return data


def load_enrollment_config() -> EnrollmentConfig:
    resolved_path = str(Path(__file__).resolve().parent.parent / "schemas" / "workshop_attendees.json")
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Attendee config not found: {resolved_path}")
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Substitute ${ENV_VAR_NAME} references before constructing the model
    data = _resolve_env_refs(data)

    config = EnrollmentConfig(**data)

    # Detect duplicate attendee ids
    attendees = set()
    for rec in config.enrollments:
        if rec.attendee_id in attendees:
            raise ValueError(f"Duplicate attendee_id in enrollment config: {rec.attendee_id}")
        attendees.add(rec.attendee_id)

    return config
