"""Read runtime settings from the selected dotenv file and process env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_runtime_setting(
    name: str,
    default: Optional[str] = None,
    *,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """Return a setting, preferring process env over the selected dotenv file."""
    process_value = os.environ.get(name)
    if process_value is not None:
        return process_value

    environment = os.environ.get("ENVIRONMENT", "prod").strip().lower()
    if environment not in {"dev", "prod"}:
        raise ValueError("ENVIRONMENT must be 'dev' or 'prod' to read runtime settings")

    env_path = (project_root or PROJECT_ROOT) / f".env.{environment}"
    if env_path.is_file():
        dotenv_value = dotenv_values(env_path).get(name)
        if dotenv_value is not None:
            return dotenv_value
    return default
