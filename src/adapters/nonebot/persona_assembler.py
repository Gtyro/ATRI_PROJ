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
from src.infra.db.tortoise.module_metrics_event_writer import ModuleMetricEventWriter
from src.infra.llm.providers import get_llm_provider_registry
from src.infra.llm.providers.image_understander import ImageUnderstander
from src.infra.memory import DecayManager, LongTermMemory, LongTermRetriever, ShortTermMemory


logger = logging.getLogger(__name__)
_MODULE_METRIC_EVENT_WRITER: Optional[ModuleMetricEventWriter] = None
_MODULE_METRIC_EVENT_WRITER_READY = False


def _get_module_metric_event_writer() -> Optional[ModuleMetricEventWriter]:
    global _MODULE_METRIC_EVENT_WRITER, _MODULE_METRIC_EVENT_WRITER_READY
    if _MODULE_METRIC_EVENT_WRITER_READY:
        return _MODULE_METRIC_EVENT_WRITER

    _MODULE_METRIC_EVENT_WRITER_READY = True
    try:
        _MODULE_METRIC_EVENT_WRITER = ModuleMetricEventWriter()
    except Exception as exc:
        logger.warning("加载模块指标事件写入器失败，已跳过 usage 事件落库: error=%s", exc)
        _MODULE_METRIC_EVENT_WRITER = None
    return _MODULE_METRIC_EVENT_WRITER


async def _persist_module_metric_event(event: dict) -> None:
    """将 usage 事件持久化到模块指标表。"""
    writer = _get_module_metric_event_writer()
    if writer is None:
        return
    await writer.write_event(event)


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
    image_understander.set_usage_event_callback(_persist_module_metric_event)
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
