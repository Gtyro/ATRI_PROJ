"""Environment helpers for detached work that must outlive the bot payload."""

import os
from collections.abc import Mapping


PROCESS_OWNERSHIP_ENV = (
    "ATRI_PAYLOAD_OWNER",
    "ATRI_SCREEN_OWNER",
    "ATRI_SCREEN_ROOT",
)


def detached_process_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy an environment without markers that tie a child to its parent payload."""
    environment = dict(os.environ if source is None else source)
    for key in PROCESS_OWNERSHIP_ENV:
        environment.pop(key, None)
    return environment
