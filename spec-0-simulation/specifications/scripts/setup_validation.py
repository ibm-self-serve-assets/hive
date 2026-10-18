#!/usr/bin/env python3
"""
Setup and environment validation script for Hive Simulation Server.
Checks tools, configuration, schemas, and selected integration prerequisites without printing secrets.
"""
import sys
import os
import json
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import ServerConfig, load_enrollment_config


def main():
    print("=== Hive Simulation Server Setup Validation ===")
    errors = []

    # 1. Python version check
    print(f"[*] Python version: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required.")

    # 2. Schema check
    schemas_dir = Path(__file__).resolve().parent.parent.parent.parent / "spec-shared" / "schemas"
    required_schemas = [
        "simulation_rules.json",
        "event_envelope.json",
        "event_payloads.json",
        "enrollment_config.json"
    ]
    for s in required_schemas:
        schema_path = schemas_dir / s
        if not schema_path.exists():
            errors.append(f"Missing schema file: {s}")
        else:
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    json.load(f)
                print(f"[+] Schema OK: {s}")
            except Exception as e:
                errors.append(f"Invalid JSON in schema {s}: {e}")

    # 3. Environment configuration check
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"

    try:
        config = ServerConfig.load_from_env(str(env_file) if env_file.exists() else None)
        print(f"[+] Server configuration loaded successfully:")
        print(f"    - PORT: {config.port}")
        print(f"    - MAX_FACTORIES: {config.max_factories}")
        print(f"    - FACTORY_TTL_SECONDS: {config.factory_ttl_seconds}")
        print(f"    - FACTORY_BUFFER_LIMIT_EVENTS: {config.factory_buffer_limit_events}")
        print(f"    - FACTORY_BUFFER_LIMIT_BYTES: {config.factory_buffer_limit_bytes}")
        print(f"    - SIM_TICK_MILLISECONDS: {config.sim_tick_milliseconds}")
        print(f"    - SNAPSHOT_INTERVAL_MILLISECONDS: {config.snapshot_interval_milliseconds}")

        # Test enrollment config loading
        enrollment_cfg = load_enrollment_config()
        print(f"[+] Attendee config validated: {len(enrollment_cfg.enrollments)} attendee(s).")
    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")

    if errors:
        print("\n[!] Setup validation FAILED with errors:")
        for err in errors:
            print(f"    - {err}")
        sys.exit(1)
    else:
        print("\n[+] All setup validations passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
