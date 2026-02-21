"""模块指标服务层。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from src.core.services.module_metrics_provider import (
    ModuleMetricsProvider,
    ModuleMetricsProviderRegistry,
    ModuleMetricsQuery,
)
from src.infra.db.tortoise.module_metrics_repository import (
    ModuleMetricsFilter,
    TortoiseModuleMetricsRepository,
)


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200
SUPPORTED_INTERVALS = {"day", "hour"}


class ModuleMetricsService:
    """封装模块指标筛选、聚合和分页查询。"""

    def __init__(
        self,
        repository: Optional[TortoiseModuleMetricsRepository] = None,
        provider_registry: Optional[ModuleMetricsProviderRegistry] = None,
    ) -> None:
        self.repository = repository or TortoiseModuleMetricsRepository()
        self.provider_registry = provider_registry or ModuleMetricsProviderRegistry()

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_positive_int(
        value: Any,
        *,
        default: int,
        min_value: int = 1,
        max_value: Optional[int] = None,
    ) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = default
        if normalized < min_value:
            normalized = min_value
        if max_value is not None and normalized > max_value:
            normalized = max_value
        return normalized

    def _build_filters(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        module_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> ModuleMetricsFilter:
        return ModuleMetricsFilter(
            from_time=from_time,
            to_time=to_time,
            module_id=self._normalize_optional_text(module_id),
            plugin_name=self._normalize_optional_text(plugin_name),
            module_name=self._normalize_optional_text(module_name),
            operation=self._normalize_optional_text(operation),
            conv_id=self._normalize_optional_text(conv_id),
        )

    def _build_provider_query(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> ModuleMetricsQuery:
        return ModuleMetricsQuery(
            from_time=from_time,
            to_time=to_time,
            plugin_name=self._normalize_optional_text(plugin_name),
            module_name=self._normalize_optional_text(module_name),
            operation=self._normalize_optional_text(operation),
            conv_id=self._normalize_optional_text(conv_id),
        )

    def register_provider(self, provider: ModuleMetricsProvider) -> None:
        self.provider_registry.register(provider)

    def list_provider_modules(self) -> List[Dict[str, Any]]:
        return self.provider_registry.list_module_definitions()

    async def get_provider_overview(
        self,
        *,
        module_ids: Optional[Sequence[str]] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = self._build_provider_query(
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        providers: List[ModuleMetricsProvider] = []
        if module_ids:
            for raw_module_id in module_ids:
                normalized = self._normalize_optional_text(raw_module_id)
                if not normalized:
                    continue
                providers.append(self.provider_registry.get(normalized))
        else:
            providers = self.provider_registry.list()

        items = []
        for provider in providers:
            payload = await provider.get_overview(query)
            if isinstance(payload, dict):
                item = dict(payload)
                item.setdefault("module_id", provider.module_id)
                items.append(item)
        return {"items": items}

    async def get_provider_detail(
        self,
        module_id: str,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider = self.provider_registry.get(module_id)
        query = self._build_provider_query(
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        payload = await provider.get_detail(query)
        if not isinstance(payload, dict):
            return {"module_id": provider.module_id}
        result = dict(payload)
        result.setdefault("module_id", provider.module_id)
        return result

    async def get_provider_filter_options(
        self,
        module_id: str,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider = self.provider_registry.get(module_id)
        query = self._build_provider_query(
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        payload = await provider.get_filter_options(query)
        if not isinstance(payload, dict):
            return {}
        return payload

    async def get_options(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        module_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        filters = self._build_filters(
            from_time=from_time,
            to_time=to_time,
            module_id=module_id,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        return await self.repository.list_options(filters)

    async def get_summary(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        module_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
        interval: str = "day",
    ) -> Dict[str, Any]:
        filters = self._build_filters(
            from_time=from_time,
            to_time=to_time,
            module_id=module_id,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        normalized_interval = str(interval or "day").strip().lower()
        if normalized_interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"unsupported interval: {interval}")
        return await self.repository.get_summary(filters, interval=normalized_interval)

    async def get_events(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        module_id: Optional[str] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
        page: int = DEFAULT_PAGE,
        size: int = DEFAULT_PAGE_SIZE,
    ) -> Dict[str, Any]:
        filters = self._build_filters(
            from_time=from_time,
            to_time=to_time,
            module_id=module_id,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        normalized_page = self._normalize_positive_int(
            page,
            default=DEFAULT_PAGE,
            min_value=1,
        )
        normalized_size = self._normalize_positive_int(
            size,
            default=DEFAULT_PAGE_SIZE,
            min_value=1,
            max_value=MAX_PAGE_SIZE,
        )
        return await self.repository.list_events(
            filters,
            page=normalized_page,
            size=normalized_size,
        )


def build_default_module_metrics_service(
    repository: Optional[TortoiseModuleMetricsRepository] = None,
) -> ModuleMetricsService:
    """构建带内置 provider 的模块指标服务。"""

    from src.core.services.module_metrics_builtin_providers import (
        build_builtin_module_metrics_providers,
    )

    service = ModuleMetricsService(repository=repository)
    for provider in build_builtin_module_metrics_providers(repository=service.repository):
        service.register_provider(provider)
    return service
