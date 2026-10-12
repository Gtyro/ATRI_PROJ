from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple

import yaml

from src.core.domain.runtime_settings import get_runtime_setting


DEFAULT_API_URL = "https://api.isthereanydeal.com/giveaways/v1"


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _as_recipient_ids(value: object) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(
        recipient
        for recipient in (str(item).strip() for item in value)
        if recipient and recipient.isdigit()
    )


@dataclass(frozen=True)
class ItadGiveawaysConfig:
    api_key: str
    api_url: str
    auto_enabled: bool
    schedule_time: str
    timeout_seconds: float
    timezone: str
    recipient_ids: Tuple[str, ...]

    @classmethod
    def load(cls, path: str = "data/itad_giveaways.yaml") -> "ItadGiveawaysConfig":
        config_path = Path(path)
        data: Mapping[str, Any] = {}
        if config_path.exists():
            try:
                loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
                else:
                    logging.warning("ITAD giveaways config must be a mapping: %s", config_path)
            except (OSError, yaml.YAMLError) as exc:
                logging.error("Failed to load ITAD giveaways config %s: %s", config_path, exc)
        else:
            logging.warning("ITAD giveaways config not found at %s", config_path)

        timeout_value = data.get("timeout_seconds", 15)
        try:
            timeout_seconds = max(1.0, float(timeout_value))
        except (TypeError, ValueError):
            timeout_seconds = 15.0

        configured_key = str(get_runtime_setting("ITAD_API_KEY", "") or "").strip()
        return cls(
            api_key=configured_key,
            api_url=str(data.get("api_url", DEFAULT_API_URL)).strip() or DEFAULT_API_URL,
            auto_enabled=_as_bool(data.get("auto_enabled", True), True),
            schedule_time=str(data.get("schedule_time", "09:00")).strip() or "09:00",
            timeout_seconds=timeout_seconds,
            timezone=str(data.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai",
            recipient_ids=_as_recipient_ids(data.get("recipient_ids")),
        )
