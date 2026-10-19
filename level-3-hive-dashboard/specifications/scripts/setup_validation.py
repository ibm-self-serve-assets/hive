#!/usr/bin/env python3
"""
Attendee setup and environment validation script for Hive Controls.
Checks local prerequisites, loopback ports, and config parameters.
"""
import sys
import os
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import BackendConfig


def main():
    print("=== Hive Controls Attendee Setup Validation ===")
    errors = []

    # 1. Python version check
    print(f"[*] Python version: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ is required.")

    # 2. Config loading check
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    try:
        config = BackendConfig.load_from_env(str(env_file) if env_file.exists() else None)
        print(f"[+] Local configuration loaded:")
        print(f"    - SIMULATION_SERVER_URL: {config.simulation_server_url}")
        print(f"    - LOCAL_BACKEND_PORT: {config.local_backend_port}")
        print(f"    - LOCAL_FRONTEND_PORT: {config.local_frontend_port}")
    except Exception as e:
        errors.append(f"Configuration error: {e}")

    # 3. Check frontend assets
    font_dir = Path(__file__).resolve().parent.parent.parent / "specifications" / "assets" / "fonts"
    if font_dir.exists():
        print(f"[+] IBM Plex Sans fonts available at {font_dir}")
    else:
        errors.append(f"Missing font assets directory: {font_dir}")

    if errors:
        print("\n[!] Setup validation FAILED with errors:")
        for err in errors:
            print(f"    - {err}")
        sys.exit(1)
    else:
        print("\n[+] All attendee setup validations passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
