import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    simulation_server_url: str = "http://localhost:8080"
    workshop_access_token: Optional[str] = None
    connection_profile_id: Optional[str] = None
    confluent_bootstrap_servers: Optional[str] = None
    confluent_consumer_api_key: Optional[str] = None
    confluent_consumer_api_secret: Optional[str] = None

    local_backend_host: str = "127.0.0.1"
    local_backend_port: int = 8000
    local_frontend_port: int = 5173

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> "BackendConfig":
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

        env_dict = {**env_file_values, **dict(os.environ)}

        if "PROJECTION_DATABASE_PATH" in env_dict:
            raise ValueError("PROJECTION_DATABASE_PATH is obsolete. SQLite is not used.")

        sim_url = env_dict.get("SIMULATION_SERVER_URL", "http://localhost:8080").rstrip("/")
        token = env_dict.get("WORKSHOP_ACCESS_TOKEN")
        profile = env_dict.get("CONNECTION_PROFILE_ID")
        bootstrap = env_dict.get("CONFLUENT_BOOTSTRAP_SERVERS")
        key = env_dict.get("CONFLUENT_CONSUMER_API_KEY")
        secret = env_dict.get("CONFLUENT_CONSUMER_API_SECRET")

        host = env_dict.get("LOCAL_BACKEND_HOST", "127.0.0.1")
        port = int(env_dict.get("LOCAL_BACKEND_PORT", 8000))
        fe_port = int(env_dict.get("LOCAL_FRONTEND_PORT", 5173))

        return cls(
            simulation_server_url=sim_url,
            workshop_access_token=token if token != "CHANGE_ME" else None,
            connection_profile_id=profile if profile != "CHANGE_ME" else None,
            confluent_bootstrap_servers=bootstrap if bootstrap != "CHANGE_ME" else None,
            confluent_consumer_api_key=key if key != "CHANGE_ME" else None,
            confluent_consumer_api_secret=secret if secret != "CHANGE_ME" else None,
            local_backend_host=host,
            local_backend_port=port,
            local_frontend_port=fe_port,
        )
