import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class BackendConfig(BaseModel):
    simulation_server_url: str = "http://localhost:8080"
    workshop_access_token: Optional[str] = None
    confluent_bootstrap_server: Optional[str] = None
    confluent_api_key: Optional[str] = None
    confluent_api_secret: Optional[str] = None

    local_backend_host: str = "127.0.0.1"
    local_backend_port: int = 8000
    local_frontend_port: int = 5173

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> "BackendConfig":
        # Load .env into os.environ. When an explicit path is given (e.g. in
        # tests) we override so that file wins. In normal startup we don't
        # overwrite values already set in the shell environment.
        if env_path:
            load_dotenv(env_path, override=True)
        else:
            loaded = load_dotenv(override=False)
            if not loaded:
                load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

        env_dict = dict(os.environ)

        if "PROJECTION_DATABASE_PATH" in env_dict:
            raise ValueError("PROJECTION_DATABASE_PATH is obsolete. SQLite is not used.")

        sim_url = env_dict.get("SIMULATION_SERVER_URL", "http://localhost:8080").rstrip("/")
        token = env_dict.get("WORKSHOP_ACCESS_TOKEN")
        bootstrap = env_dict.get("CONFLUENT_BOOTSTRAP_SERVER")
        key = env_dict.get("CONFLUENT_API_KEY")
        secret = env_dict.get("CONFLUENT_API_SECRET")

        host = env_dict.get("LOCAL_BACKEND_HOST", "127.0.0.1")
        port = int(env_dict.get("LOCAL_BACKEND_PORT", 8000))
        fe_port = int(env_dict.get("LOCAL_FRONTEND_PORT", 5173))

        return cls(
            simulation_server_url=sim_url,
            workshop_access_token=token if token != "CHANGE_ME" else None,
            confluent_bootstrap_server=bootstrap if bootstrap != "CHANGE_ME" else None,
            confluent_api_key=key if key != "CHANGE_ME" else None,
            confluent_api_secret=secret if secret != "CHANGE_ME" else None,
            local_backend_host=host,
            local_backend_port=port,
            local_frontend_port=fe_port,
        )
