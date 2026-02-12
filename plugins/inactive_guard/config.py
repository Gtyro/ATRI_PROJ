from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class InactiveGuardConfig:
    auto_enabled: bool
    schedule_time: str
    window_hours: int
    active_message_threshold: int
    dry_run: bool

    @classmethod
    def load(cls, path: str = "data/inactive_guard.yaml") -> "InactiveGuardConfig":
        data: Dict[str, Any] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logging.error("Failed to load inactive guard config: %s", exc)
        else:
            logging.warning("inactive guard config not found at %s", path)

        return cls(
            auto_enabled=bool(data.get("auto_enabled", False)),
            schedule_time=str(data.get("schedule_time", "10:00")).strip() or "10:00",
            window_hours=int(data.get("window_hours", 24)),
            active_message_threshold=int(data.get("active_message_threshold", 20)),
            dry_run=bool(data.get("dry_run", False)),
        )
