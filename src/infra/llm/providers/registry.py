"""LLM Provider 注册与创建。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

ProviderFactory = Callable[..., Any]


class LLMProviderRegistry:
    """LLM Provider 注册表。"""

    def __init__(self) -> None:
        self._factories: Dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs: Any) -> Any:
        if name not in self._factories:
            raise ValueError(f"未注册的 LLM Provider: {name}")
        return self._factories[name](**kwargs)

    def available(self) -> List[str]:
        return list(self._factories.keys())

    def create_with_fallback(
        self,
        provider_specs: Sequence[Union[str, Dict[str, Any]]],
        *,
        default_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """根据配置创建带回退策略的Provider实例。"""
        from .fallback import FallbackLLMProvider

        providers = []
        base_kwargs = default_kwargs or {}

        for spec in provider_specs:
            if isinstance(spec, str):
                name = spec
                params: Dict[str, Any] = {}
                enabled = True
            elif isinstance(spec, dict):
                name = spec.get("name") or spec.get("provider")
                params = spec.get("params") or {}
                enabled = spec.get("enabled", True)
            else:
                raise ValueError(f"无效的provider配置: {spec}")

            if not enabled:
                continue
            if not name:
                raise ValueError("provider配置缺少name")

            provider_kwargs = {**base_kwargs, **params}
            provider_kwargs.setdefault("provider_name", name)
            providers.append(self.create(name, **provider_kwargs))

        if not providers:
            raise ValueError("没有可用的provider用于回退链")

        return FallbackLLMProvider(providers)


def register_default_providers(registry: LLMProviderRegistry) -> None:
    from .ai_processor import AIProcessor

    registry.register("ai_processor", AIProcessor)
    registry.register("openai_compatible", AIProcessor)


_default_registry: Optional[LLMProviderRegistry] = None


def get_llm_provider_registry() -> LLMProviderRegistry:
    """获取默认 Provider 注册表实例。"""

    global _default_registry
    if _default_registry is None:
        _default_registry = LLMProviderRegistry()
        register_default_providers(_default_registry)
    return _default_registry
