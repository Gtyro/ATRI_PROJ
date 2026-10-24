"""Optional local manager settings and request accounting for ATRI LLM calls."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from llm_request_kit.manager_client import load_project_config, load_project_routes, record_usage
from src.core.domain.runtime_settings import get_runtime_setting

PROJECT = "ATRI_PROJ"


def enabled() -> bool:
    return get_runtime_setting("LLM_REQUEST_KIT_MANAGER") == "1"


def _socket_path() -> Path | None:
    configured = os.getenv("LLM_REQUEST_KIT_SOCKET", "").strip()
    if not configured:
        return None
    path = Path(configured)
    if not path.is_absolute():
        raise ValueError("LLM_REQUEST_KIT_SOCKET 必须是绝对路径")
    return path


def _providers() -> dict[str, Any]:
    socket_path = _socket_path()
    providers = (load_project_config(PROJECT, socket_path=socket_path) if socket_path else
                 load_project_config(PROJECT))
    if not isinstance(providers, dict):
        raise RuntimeError("LLM 管理服务返回的 Provider 配置无效")
    return providers


def _routes() -> dict[str, list[str]]:
    socket_path = _socket_path()
    try:
        routes = (load_project_routes(PROJECT, socket_path=socket_path) if socket_path else
                  load_project_routes(PROJECT))
    except RuntimeError as exc:
        if "Unknown operation" not in str(exc):
            raise
        return {}
    if not isinstance(routes, dict):
        raise RuntimeError("LLM 管理服务返回的用途绑定无效")
    return routes


def provider_settings(name: str, providers: dict[str, Any] | None = None, *,
                      role: str = "text", routes: dict[str, list[str]] | None = None) -> dict[str, Any]:
    providers = providers if providers is not None else _providers()
    routes = routes if routes is not None else _routes()
    if role in routes:
        names = routes[role]
        if not isinstance(names, list) or (role != "vision" and len(names) != 1):
            raise RuntimeError(f"LLM 管理服务的 {role} 用途尚未绑定 Provider")
        if role == "vision" and name not in names:
            raise RuntimeError(f"Provider {name} 未绑定到图片理解用途")
        if role != "vision":
            name = names[0]
    settings = providers.get(name)
    if not isinstance(settings, dict) or not all(
        isinstance(settings.get(key), str) and settings[key].strip()
        for key in ("api_key", "base_url", "model")
    ):
        raise RuntimeError(f"LLM 管理服务缺少 {name} 的密钥、端点或模型")
    if role != "image_generation" and settings.get("api") not in (None, "responses"):
        raise RuntimeError(f"{name} 的协议必须是 Responses")
    return {**settings, "_manager_provider_id": name}


def image_provider_specs() -> list[dict[str, str]]:
    providers = _providers()
    routes = _routes()
    names = (routes["vision"] if "vision" in routes else
             sorted(name for name in providers if name == "image_understander" or name.startswith("image_understander_")))
    specs = []
    for name in names:
        settings = provider_settings(name, providers, role="vision", routes=routes)
        specs.append({"name": name, **{key: settings[key] for key in ("api_key", "base_url", "model")}})
    return specs


def image_generation_settings() -> dict[str, Any] | None:
    routes = _routes()
    if "image_generation" not in routes:
        return None
    return provider_settings("", _providers(), role="image_generation", routes=routes)


async def record_request(provider: str, model: str, *, result: Any = None,
                         error: BaseException | None = None, elapsed_ms: int = 0,
                         attempts: int | None = None) -> None:
    if not enabled():
        return
    attempts = attempts if attempts is not None else getattr(error if error is not None else result, "attempts", 1)
    event: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "success": error is None,
        "attempts": max(1, attempts if isinstance(attempts, int) else 1),
        "elapsed_ms": max(0, elapsed_ms),
    }
    if error is not None:
        event["error_code"] = str(getattr(error, "code", None) or "request_failed")
    elif result is not None:
        event["input_tokens"] = result.usage.input_tokens
        event["output_tokens"] = result.usage.output_tokens
    try:
        socket_path = _socket_path()
        if socket_path:
            await asyncio.to_thread(record_usage, PROJECT, event, socket_path=socket_path)
        else:
            await asyncio.to_thread(record_usage, PROJECT, event)
    except (OSError, RuntimeError, ValueError) as exc:
        logging.warning("LLM 管理服务用量记录失败：%s", exc)
