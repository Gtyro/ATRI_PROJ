from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class Daily60sConfig:
    alapi_key: str
    api_url: str
    image_format: str
    auto_enabled: bool
    schedule_time: str
    timeout_seconds: int

    @classmethod
    def load(cls, path: str = "data/daily60s.yaml") -> "Daily60sConfig":
        data: Dict[str, Any] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logging.error("Failed to load daily60s config: %s", exc)
        else:
            logging.warning("daily60s config not found at %s", path)

        return cls(
            alapi_key=str(data.get("alapi_key", "")).strip(),
            api_url=str(data.get("api_url", "https://v3.alapi.cn/api/zaobao")).strip(),
            image_format=str(data.get("format", "image")).strip() or "image",
            auto_enabled=bool(data.get("auto_enabled", True)),
            schedule_time=str(data.get("schedule_time", "10:00")).strip() or "10:00",
            timeout_seconds=int(data.get("timeout_seconds", 15)),
        )
