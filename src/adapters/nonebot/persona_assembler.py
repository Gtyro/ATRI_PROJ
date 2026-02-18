"""Persona 引擎装配器（NoneBot 适配）。"""

import logging
import os
from typing import Any, Callable, Optional

from src.adapters.persona import LLMProviderAdapter, LongTermMemoryAdapter, ShortTermMemoryAdapter
from src.core.domain import PersonaConfig
from src.core.engine import PersonaEngineCore
from src.core.services.image_context_service import ImageContextService
from src.core.services.message_processor import MessageProcessor
from src.core.services.plugin_policy_service import PluginPolicyService
from src.adapters.nonebot.image_resolver import NapcatImageResolver
from src.infra.db.neo4j_gateway import initialize_neo4j
from src.infra.db.tortoise.message_repository import MessageRepository
from src.infra.llm.providers import get_llm_provider_registry
from src.infra.llm.providers.image_understander import ImageUnderstander
from src.infra.memory import DecayManager, LongTermMemory, LongTermRetriever, ShortTermMemory


logger = logging.getLogger(__name__)
_PLUGIN_MODULE_METRIC_EVENT_MODEL: Any = None
_PLUGIN_MODULE_METRIC_EVENT_MODEL_READY = False


def _get_plugin_module_metric_event_model() -> Any:
    global _PLUGIN_MODULE_METRIC_EVENT_MODEL, _PLUGIN_MODULE_METRIC_EVENT_MODEL_READY
    if _PLUGIN_MODULE_METRIC_EVENT_MODEL_READY:
        return _PLUGIN_MODULE_METRIC_EVENT_MODEL

    _PLUGIN_MODULE_METRIC_EVENT_MODEL_READY = True
    try:
        from src.infra.db.tortoise.plugin_models import PluginModuleMetricEvent

        _PLUGIN_MODULE_METRIC_EVENT_MODEL = PluginModuleMetricEvent
    except Exception as exc:
        logger.warning("加载模块指标模型失败，已跳过图片理解指标落库: error=%s", exc)
        _PLUGIN_MODULE_METRIC_EVENT_MODEL = None
    return _PLUGIN_MODULE_METRIC_EVENT_MODEL


def _to_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _persist_image_metric_event(event: dict) -> None:
    """将图片理解 usage 事件持久化到模块指标表。"""
    if not isinstance(event, dict):
        return
    metric_model = _get_plugin_module_metric_event_model()
    if metric_model is None:
        return

    known_fields = {
        "plugin_name",
        "module_name",
        "operation",
        "conv_id",
        "message_id",
        "provider_name",
        "model",
        "request_id",
        "success",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "error_type",
    }
    extra = {key: value for key, value in event.items() if key not in known_fields}

    try:
        await metric_model.create(
            plugin_name=_to_optional_str(event.get("plugin_name")) or "persona",
            module_name=_to_optional_str(event.get("module_name")) or "image_understanding",
            operation=_to_optional_str(event.get("operation")) or "image_understanding",
            conv_id=_to_optional_str(event.get("conv_id")),
            message_id=_to_optional_str(event.get("message_id")),
            provider_name=_to_optional_str(event.get("provider_name")),
            model=_to_optional_str(event.get("model")),
            request_id=_to_optional_str(event.get("request_id")),
            success=bool(event.get("success")),
            prompt_tokens=_to_optional_int(event.get("prompt_tokens")),
            completion_tokens=_to_optional_int(event.get("completion_tokens")),
            total_tokens=_to_optional_int(event.get("total_tokens")),
            error_type=_to_optional_str(event.get("error_type")),
            extra=extra,
        )
    except Exception as exc:
        logger.warning("图片理解指标写入失败: error=%s", exc)


async def assemble_persona_engine(
    config: PersonaConfig,
    group_config: Any,
    plugin_name: str = "persona",
    reply_callback: Optional[Callable] = None,
    plugin_policy_service: Optional[PluginPolicyService] = None,
) -> PersonaEngineCore:
    """装配 Persona 核心引擎依赖。"""
    os.makedirs(os.path.dirname(config.db_path), exist_ok=True)

    message_repo = MessageRepository(config)
    await message_repo.initialize()
    try:
        await message_repo.cleanup_stale_messages(
            keep_count=config.queue_history_size,
            max_age_days=1,
        )
    except Exception as e:
        logging.warning(f"启动时清理短期记忆失败: {e}")

    memory_repo = await initialize_neo4j(config)

    short_term_impl = ShortTermMemory(message_repo, config)
    short_term = ShortTermMemoryAdapter(short_term_impl)

    group_ids = await group_config.get_distinct_group_ids(plugin_name)
    group_character = {}
    for group_id in group_ids:
        try:
            gpconfig = await group_config.get_config(group_id, plugin_name)
            prompt_file = gpconfig.plugin_config.get("prompt_file", None)
            if prompt_file and os.path.exists(prompt_file):
                group_character[group_id] = prompt_file
        except Exception as e:
            logging.error(f"读取群组配置失败[{group_id}]: {e}")

    model = config.model
    base_url = config.base_url
    provider_params = config.extras.get("llm_provider_params", {})
    provider_kwargs = {
        "api_key": config.api_key,
        "model": model,
        "base_url": base_url,
        "group_character": group_character,
        "queue_history_size": config.queue_history_size,
        **provider_params,
    }
    provider_chain = config.extras.get("llm_providers") or config.extras.get("llm_provider_chain")

    registry = get_llm_provider_registry()
    if provider_chain:
        fallback_kwargs = {**provider_kwargs, "raise_on_error": True}
        try:
            llm_impl = registry.create_with_fallback(provider_chain, default_kwargs=fallback_kwargs)
        except Exception as e:
            logging.error(f"创建 LLM Provider 回退链失败: {e}, 回退到单一 provider", exc_info=True)
            provider_name = config.extras.get("llm_provider", "ai_processor")
            provider_kwargs_single = {**provider_kwargs, "provider_name": provider_name}
            try:
                llm_impl = registry.create(provider_name, **provider_kwargs_single)
            except Exception as err:
                logging.error(f"创建 LLM Provider 失败: {err}, 回退到 ai_processor", exc_info=True)
                llm_impl = registry.create("ai_processor", **{**provider_kwargs, "provider_name": "ai_processor"})
    else:
        provider_name = config.extras.get("llm_provider", "ai_processor")
        provider_kwargs_single = {**provider_kwargs, "provider_name": provider_name}
        try:
            llm_impl = registry.create(provider_name, **provider_kwargs_single)
        except Exception as e:
            logging.error(f"创建 LLM Provider 失败: {e}, 回退到 ai_processor", exc_info=True)
            llm_impl = registry.create("ai_processor", **{**provider_kwargs, "provider_name": "ai_processor"})
    llm_provider = LLMProviderAdapter(llm_impl)

    msgprocessor = MessageProcessor(
        config=config,
        llm_provider=llm_provider,
        group_character=group_character,
        queue_history_size=config.queue_history_size,
        group_config=group_config,
        plugin_name=plugin_name,
    )

    image_cfg = config.image_understanding
    image_resolver = NapcatImageResolver(timeout_seconds=image_cfg.http_timeout_seconds)
    image_understander = ImageUnderstander(
        api_key=image_cfg.api_key,
        base_url=image_cfg.base_url,
        model=image_cfg.model,
        timeout_seconds=image_cfg.timeout_seconds,
        max_tokens=image_cfg.max_tokens,
    )
    image_understander.set_usage_event_callback(_persist_image_metric_event)
    image_context_service = ImageContextService(
        config=config,
        image_resolver=image_resolver,
        image_understander=image_understander,
        message_repo=message_repo,
    )

    long_term_impl = LongTermMemory(memory_repo, config)
    long_term = LongTermMemoryAdapter(long_term_impl)
    retriever = LongTermRetriever(memory_repo)
    decay_manager = DecayManager(
        memory_repo,
        config.node_decay_rate,
        group_config=group_config,
        plugin_name=plugin_name,
        config=config,
    )
    await decay_manager.initialize()

    engine = PersonaEngineCore(
        config=config,
        plugin_name=plugin_name,
        group_config=group_config,
        message_repo=message_repo,
        memory_repo=memory_repo,
        short_term=short_term,
        long_term=long_term,
        msgprocessor=msgprocessor,
        retriever=retriever,
        decay_manager=decay_manager,
        reply_callback=reply_callback,
        aiprocessor=llm_impl,
        plugin_policy_service=plugin_policy_service,
        image_context_service=image_context_service,
    )
    if hasattr(llm_impl, "set_memory_retrieval_callback"):
        llm_impl.set_memory_retrieval_callback(engine.format_memories)

    return engine
