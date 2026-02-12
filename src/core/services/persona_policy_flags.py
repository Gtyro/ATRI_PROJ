"""Persona LLM 开关配置。"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.core.domain import PersonaConfig

LLM_TOPIC_EXTRACT_ENABLED_KEY = "llm_topic_extract_enabled"
LLM_KEYWORD_EXTRACT_ENABLED_KEY = "llm_keyword_extract_enabled"
LLM_PASSIVE_REPLY_ENABLED_KEY = "llm_passive_reply_enabled"
LLM_ACTIVE_REPLY_ENABLED_KEY = "llm_active_reply_enabled"

FALLBACK_PERSONA_POLICY_CONFIG: Dict[str, bool] = {
    LLM_TOPIC_EXTRACT_ENABLED_KEY: True,
    LLM_KEYWORD_EXTRACT_ENABLED_KEY: False,
    LLM_PASSIVE_REPLY_ENABLED_KEY: False,
    LLM_ACTIVE_REPLY_ENABLED_KEY: False,
}


def _load_policy_defaults() -> Dict[str, bool]:
    try:
        config = PersonaConfig.load()
        defaults = config.llm_flags_defaults
        if not isinstance(defaults, dict) or not defaults:
            raise ValueError("llm_flags_defaults 未配置")
        return {
            key: bool(defaults.get(key, fallback))
            for key, fallback in FALLBACK_PERSONA_POLICY_CONFIG.items()
        }
    except Exception as exc:
        logging.warning(f"加载 LLM 默认开关失败，使用内置回退值: {exc}")
        return dict(FALLBACK_PERSONA_POLICY_CONFIG)


DEFAULT_PERSONA_POLICY_CONFIG: Dict[str, bool] = _load_policy_defaults()


def normalize_persona_policy_config(config: Dict[str, Any]) -> Dict[str, bool]:
    """规范化 Persona LLM 配置，并按联动策略同步关键词提取开关。"""
    normalized = dict(config or {})
    passive_enabled = bool(normalized.get(LLM_PASSIVE_REPLY_ENABLED_KEY, False))
    active_enabled = bool(normalized.get(LLM_ACTIVE_REPLY_ENABLED_KEY, False))
    normalized[LLM_KEYWORD_EXTRACT_ENABLED_KEY] = passive_enabled or active_enabled
    return normalized


def resolve_llm_flags(config: Dict[str, Any]) -> Dict[str, bool]:
    """根据配置返回 LLM 开关状态，缺省值按默认配置。"""
    base_flags = {
        key: bool((config or {}).get(key, default))
        for key, default in DEFAULT_PERSONA_POLICY_CONFIG.items()
    }
    base_flags[LLM_KEYWORD_EXTRACT_ENABLED_KEY] = (
        base_flags.get(LLM_PASSIVE_REPLY_ENABLED_KEY, False)
        or base_flags.get(LLM_ACTIVE_REPLY_ENABLED_KEY, False)
    )
    return base_flags
