"""模块指标服务层。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

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

    def __init__(self, repository: Optional[TortoiseModuleMetricsRepository] = None) -> None:
        self.repository = repository or TortoiseModuleMetricsRepository()

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
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> ModuleMetricsFilter:
        return ModuleMetricsFilter(
            from_time=from_time,
            to_time=to_time,
            plugin_name=self._normalize_optional_text(plugin_name),
            module_name=self._normalize_optional_text(module_name),
            operation=self._normalize_optional_text(operation),
            conv_id=self._normalize_optional_text(conv_id),
        )

    async def get_options(
        self,
        *,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        filters = self._build_filters(
            from_time=from_time,
            to_time=to_time,
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
        plugin_name: Optional[str] = None,
        module_name: Optional[str] = None,
        operation: Optional[str] = None,
        conv_id: Optional[str] = None,
        interval: str = "day",
    ) -> Dict[str, Any]:
        filters = self._build_filters(
            from_time=from_time,
            to_time=to_time,
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
