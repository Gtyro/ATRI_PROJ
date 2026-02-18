"""模块指标查询仓储实现。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

SUPPORTED_INTERVALS = {"day", "hour"}

EVENT_FIELDS = (
    "id",
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
    "extra",
    "created_at",
)


@dataclass(frozen=True)
class ModuleMetricsFilter:
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    plugin_name: Optional[str] = None
    module_name: Optional[str] = None
    operation: Optional[str] = None
    conv_id: Optional[str] = None


class TortoiseModuleMetricsRepository:
    """基于 Tortoise ORM 的模块指标读查询仓储。"""

    def __init__(self, model: Any = None) -> None:
        self.model = model or self._load_default_model()

    @staticmethod
    def _load_default_model() -> Any:
        try:
            from tortoise import Tortoise

            model = Tortoise.apps.get("models", {}).get("PluginModuleMetricEvent")
            if model is not None:
                return model
        except Exception:
            pass

        try:
            from src.infra.db.tortoise.plugin_models import PluginModuleMetricEvent

            return PluginModuleMetricEvent
        except Exception as exc:
            raise RuntimeError(
                "无法加载 PluginModuleMetricEvent，请在初始化后显式传入 model 参数"
            ) from exc

    def _build_query(self, filters: Optional[ModuleMetricsFilter]):
        query = self.model.all()
        if filters is None:
            return query
        if filters.from_time is not None:
            query = query.filter(created_at__gte=filters.from_time)
        if filters.to_time is not None:
            query = query.filter(created_at__lte=filters.to_time)
        if filters.plugin_name:
            query = query.filter(plugin_name=filters.plugin_name)
        if filters.module_name:
            query = query.filter(module_name=filters.module_name)
        if filters.operation:
            query = query.filter(operation=filters.operation)
        if filters.conv_id:
            query = query.filter(conv_id=filters.conv_id)
        return query

    @staticmethod
    def _normalize_options(values: List[Optional[str]]) -> List[str]:
        normalized = set()
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                normalized.add(text)
        return sorted(normalized)

    @staticmethod
    def _bucket_start(value: datetime, interval: str) -> datetime:
        if interval == "hour":
            return value.replace(minute=0, second=0, microsecond=0)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _to_int(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    async def list_options(self, filters: Optional[ModuleMetricsFilter] = None) -> Dict[str, List[str]]:
        plugin_names_raw = await self._build_query(filters).values_list("plugin_name", flat=True)
        module_names_raw = await self._build_query(filters).values_list("module_name", flat=True)
        operations_raw = await self._build_query(filters).values_list("operation", flat=True)
        conv_ids_raw = await self._build_query(filters).values_list("conv_id", flat=True)
        return {
            "plugin_names": self._normalize_options(plugin_names_raw),
            "module_names": self._normalize_options(module_names_raw),
            "operations": self._normalize_options(operations_raw),
            "conv_ids": self._normalize_options(conv_ids_raw),
        }

    async def get_summary(
        self,
        filters: Optional[ModuleMetricsFilter] = None,
        *,
        interval: str = "day",
    ) -> Dict[str, Any]:
        normalized_interval = str(interval or "day").strip().lower()
        if normalized_interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"unsupported interval: {interval}")

        rows = await self._build_query(filters).values("created_at", "success", "total_tokens")

        total_calls = 0
        failed_calls = 0
        total_tokens = 0
        trend_map: Dict[datetime, Dict[str, int]] = {}

        for row in rows:
            total_calls += 1
            success = bool(row.get("success"))
            if not success:
                failed_calls += 1
            tokens = self._to_int(row.get("total_tokens"))
            total_tokens += tokens

            created_at = row.get("created_at")
            if not isinstance(created_at, datetime):
                continue
            bucket = self._bucket_start(created_at, normalized_interval)
            bucket_metrics = trend_map.setdefault(
                bucket,
                {
                    "total_calls": 0,
                    "failed_calls": 0,
                    "total_tokens": 0,
                },
            )
            bucket_metrics["total_calls"] += 1
            if not success:
                bucket_metrics["failed_calls"] += 1
            bucket_metrics["total_tokens"] += tokens

        success_calls = total_calls - failed_calls
        success_rate = (success_calls / total_calls) if total_calls else 0.0
        avg_tokens_per_call = (total_tokens / total_calls) if total_calls else 0.0

        trends: List[Dict[str, Any]] = []
        for bucket in sorted(trend_map.keys()):
            item = trend_map[bucket]
            trends.append(
                {
                    "time": bucket.isoformat(),
                    "total_calls": item["total_calls"],
                    "failed_calls": item["failed_calls"],
                    "total_tokens": item["total_tokens"],
                }
            )

        return {
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "success_rate": success_rate,
            "total_tokens": total_tokens,
            "avg_tokens_per_call": avg_tokens_per_call,
            "trends": trends,
        }

    async def list_events(
        self,
        filters: Optional[ModuleMetricsFilter] = None,
        *,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        normalized_page = max(1, int(page))
        normalized_size = max(1, int(size))
        query = self._build_query(filters)
        total = await query.count()
        offset = (normalized_page - 1) * normalized_size
        items = await (
            query.order_by("-created_at", "-id")
            .offset(offset)
            .limit(normalized_size)
            .values(*EVENT_FIELDS)
        )
        return {
            "items": items,
            "total": total,
            "page": normalized_page,
            "size": normalized_size,
        }
