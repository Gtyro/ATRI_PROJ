"""模块指标内置 Provider。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from src.core.services.module_metrics_provider import ModuleMetricsQuery
from src.infra.db.tortoise.module_metrics_repository import (
    ModuleMetricsFilter,
    TortoiseModuleMetricsRepository,
)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_extra(extra: Any) -> Dict[str, Any]:
    if isinstance(extra, Mapping):
        return dict(extra)
    if isinstance(extra, str):
        text = extra.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
            if isinstance(payload, Mapping):
                return dict(payload)
            return {}
        except Exception:
            return {}
    return {}


def _build_chart(
    *,
    chart_id: str,
    title: str,
    chart_type: str,
    dataset: Any,
    x_axis: Optional[Dict[str, Any]] = None,
    series: Optional[List[Dict[str, Any]]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "chart_id": chart_id,
        "title": title,
        "type": chart_type,
        "dataset": dataset if dataset is not None else [],
        "x_axis": x_axis or {},
        "series": series or [],
        "meta": meta or {},
    }


def _build_common_kpis(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    total_calls = _to_int(summary.get("total_calls"))
    failed_calls = _to_int(summary.get("failed_calls"))
    total_tokens = _to_int(summary.get("total_tokens"))
    success_rate = float(summary.get("success_rate") or 0)
    avg_tokens = float(summary.get("avg_tokens_per_call") or 0)
    return [
        {
            "key": "total_calls",
            "label": "调用次数",
            "value": total_calls,
            "format": "integer",
        },
        {
            "key": "failed_calls",
            "label": "失败次数",
            "value": failed_calls,
            "format": "integer",
        },
        {
            "key": "success_rate",
            "label": "成功率",
            "value": success_rate,
            "format": "percent",
        },
        {
            "key": "total_tokens",
            "label": "总 Tokens",
            "value": total_tokens,
            "format": "integer",
        },
        {
            "key": "avg_tokens_per_call",
            "label": "平均 Tokens/次",
            "value": avg_tokens,
            "format": "decimal",
        },
    ]


class _BaseModuleMetricsProvider:
    """基于仓储查询的 Provider 基类。"""

    module_id: str = ""
    plugin_name: str = ""
    module_name: str = ""
    title: str = ""
    description: str = ""

    def __init__(self, repository: Optional[TortoiseModuleMetricsRepository] = None) -> None:
        self.repository = repository or TortoiseModuleMetricsRepository()

    def get_module_definition(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "plugin_name": self.plugin_name,
            "module_name": self.module_name,
            "title": self.title,
            "description": self.description,
        }

    def _build_filters(self, query: ModuleMetricsQuery) -> ModuleMetricsFilter:
        return ModuleMetricsFilter(
            from_time=query.from_time,
            to_time=query.to_time,
            module_id=self.module_id,
            plugin_name=query.plugin_name,
            module_name=query.module_name,
            operation=query.operation,
            conv_id=query.conv_id,
        )

    async def get_filter_options(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        return await self.repository.list_options(self._build_filters(query))


class PersonaImageUnderstandingMetricsProvider(_BaseModuleMetricsProvider):
    module_id = "persona.image_understanding"
    plugin_name = "persona"
    module_name = "image_understanding"
    title = "图片理解"
    description = "统计图片理解调用与 Tokens 使用情况。"

    async def get_overview(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        filters = self._build_filters(query)
        summary = await self.repository.get_summary(filters, interval="day")
        trends = list(summary.get("trends") or [])
        kpis = _build_common_kpis(summary)
        return {
            "module_id": self.module_id,
            "title": self.title,
            "kpis": kpis,
            "main_chart": _build_chart(
                chart_id=f"{self.module_id}.overview.main",
                title="调用与 Tokens 趋势",
                chart_type="line",
                dataset=trends,
                x_axis={"field": "time", "type": "time"},
                series=[
                    {"field": "total_calls", "name": "调用次数", "type": "line"},
                    {"field": "failed_calls", "name": "失败次数", "type": "line"},
                    {"field": "total_tokens", "name": "总 Tokens", "type": "line", "y_axis": "right"},
                ],
                meta={"interval": "day"},
            ),
            "meta": {"module_id": self.module_id},
        }

    async def get_detail(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        filters = self._build_filters(query)
        day_summary = await self.repository.get_summary(filters, interval="day")
        hour_summary = await self.repository.get_summary(filters, interval="hour")
        events = await self.repository.list_events(filters, page=1, size=20)

        kpis = _build_common_kpis(day_summary)
        total_calls = _to_int(day_summary.get("total_calls"))
        failed_calls = _to_int(day_summary.get("failed_calls"))
        success_calls = max(0, total_calls - failed_calls)

        event_rows: List[Dict[str, Any]] = []
        for row in list(events.get("items") or []):
            normalized = dict(row)
            normalized["created_at"] = _normalize_datetime(normalized.get("created_at"))
            event_rows.append(normalized)

        charts = [
            _build_chart(
                chart_id=f"{self.module_id}.detail.kpi",
                title="关键指标",
                chart_type="kpi",
                dataset=kpis,
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.trend.day",
                title="按天趋势",
                chart_type="line",
                dataset=list(day_summary.get("trends") or []),
                x_axis={"field": "time", "type": "time"},
                series=[
                    {"field": "total_calls", "name": "调用次数", "type": "line"},
                    {"field": "failed_calls", "name": "失败次数", "type": "line"},
                    {"field": "total_tokens", "name": "总 Tokens", "type": "line", "y_axis": "right"},
                ],
                meta={"interval": "day"},
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.trend.hour",
                title="按小时趋势",
                chart_type="line",
                dataset=list(hour_summary.get("trends") or []),
                x_axis={"field": "time", "type": "time"},
                series=[
                    {"field": "total_calls", "name": "调用次数", "type": "line"},
                    {"field": "failed_calls", "name": "失败次数", "type": "line"},
                    {"field": "total_tokens", "name": "总 Tokens", "type": "line", "y_axis": "right"},
                ],
                meta={"interval": "hour"},
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.success",
                title="成功/失败分布",
                chart_type="pie",
                dataset=[
                    {"name": "成功", "value": success_calls},
                    {"name": "失败", "value": failed_calls},
                ],
                series=[{"field": "value", "name": "调用次数", "type": "pie"}],
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.events",
                title="最近事件",
                chart_type="table",
                dataset=event_rows,
                meta={
                    "page": events.get("page", 1),
                    "size": events.get("size", 20),
                    "total": events.get("total", len(event_rows)),
                },
            ),
        ]
        return {
            "module_id": self.module_id,
            "title": self.title,
            "kpis": kpis,
            "charts": charts,
            "meta": {"module_id": self.module_id},
        }


class PersonaImageUrlFallbackMetricsProvider(_BaseModuleMetricsProvider):
    module_id = "persona.image_url_fallback"
    plugin_name = "persona"
    module_name = "image_url_fallback"
    title = "图片 URL 回退"
    description = "统计图片回退来源（fetch_source）分布。"

    @staticmethod
    def _extract_fetch_source(row: Mapping[str, Any]) -> str:
        extra = _parse_extra(row.get("extra"))
        source = _normalize_text(extra.get("fetch_source"))
        if source:
            return source
        operation = _normalize_text(row.get("operation"))
        if operation:
            return operation
        return "unknown"

    @classmethod
    def _build_source_distribution(cls, rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        counter: Dict[str, int] = {}
        for row in rows:
            source = cls._extract_fetch_source(row)
            counter[source] = counter.get(source, 0) + 1
        return [{"name": name, "value": counter[name]} for name in sorted(counter.keys())]

    @classmethod
    def _build_source_success_rows(cls, rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        matrix: Dict[str, Dict[str, int]] = {}
        for row in rows:
            source = cls._extract_fetch_source(row)
            item = matrix.setdefault(source, {"source": source, "total_calls": 0, "failed_calls": 0})
            item["total_calls"] += 1
            if not bool(row.get("success")):
                item["failed_calls"] += 1
        return [matrix[key] for key in sorted(matrix.keys())]

    async def get_overview(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        filters = self._build_filters(query)
        summary = await self.repository.get_summary(filters, interval="day")
        rows = await self.repository.list_rows(
            filters,
            fields=("operation", "extra", "success", "created_at"),
        )
        source_distribution = self._build_source_distribution(rows)
        kpis = _build_common_kpis(summary)
        return {
            "module_id": self.module_id,
            "title": self.title,
            "kpis": kpis,
            "main_chart": _build_chart(
                chart_id=f"{self.module_id}.overview.main",
                title="回退来源分布",
                chart_type="pie",
                dataset=source_distribution,
                series=[{"field": "value", "name": "调用次数", "type": "pie"}],
                meta={"dimension": "fetch_source"},
            ),
            "meta": {"module_id": self.module_id},
        }

    async def get_detail(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        filters = self._build_filters(query)
        day_summary = await self.repository.get_summary(filters, interval="day")
        rows = await self.repository.list_rows(
            filters,
            fields=("operation", "extra", "success", "created_at", "total_tokens"),
        )
        events = await self.repository.list_events(filters, page=1, size=20)
        source_distribution = self._build_source_distribution(rows)
        source_success_rows = self._build_source_success_rows(rows)

        kpis = _build_common_kpis(day_summary)
        event_rows: List[Dict[str, Any]] = []
        for row in list(events.get("items") or []):
            normalized = dict(row)
            normalized["created_at"] = _normalize_datetime(normalized.get("created_at"))
            normalized["fetch_source"] = self._extract_fetch_source(normalized)
            event_rows.append(normalized)

        charts = [
            _build_chart(
                chart_id=f"{self.module_id}.detail.kpi",
                title="关键指标",
                chart_type="kpi",
                dataset=kpis,
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.source",
                title="回退来源分布",
                chart_type="pie",
                dataset=source_distribution,
                series=[{"field": "value", "name": "调用次数", "type": "pie"}],
                meta={"dimension": "fetch_source"},
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.source.success",
                title="来源成功率",
                chart_type="bar",
                dataset=source_success_rows,
                x_axis={"field": "source", "type": "category"},
                series=[
                    {"field": "total_calls", "name": "调用次数", "type": "bar"},
                    {"field": "failed_calls", "name": "失败次数", "type": "bar"},
                ],
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.trend.day",
                title="按天趋势",
                chart_type="line",
                dataset=list(day_summary.get("trends") or []),
                x_axis={"field": "time", "type": "time"},
                series=[
                    {"field": "total_calls", "name": "调用次数", "type": "line"},
                    {"field": "failed_calls", "name": "失败次数", "type": "line"},
                ],
                meta={"interval": "day"},
            ),
            _build_chart(
                chart_id=f"{self.module_id}.detail.events",
                title="最近事件",
                chart_type="table",
                dataset=event_rows,
                meta={
                    "page": events.get("page", 1),
                    "size": events.get("size", 20),
                    "total": events.get("total", len(event_rows)),
                },
            ),
        ]

        return {
            "module_id": self.module_id,
            "title": self.title,
            "kpis": kpis,
            "charts": charts,
            "meta": {"module_id": self.module_id},
        }

    async def get_filter_options(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        filters = self._build_filters(query)
        options = await self.repository.list_options(filters)
        rows = await self.repository.list_rows(filters, fields=("operation", "extra"))
        sources = sorted({self._extract_fetch_source(row) for row in rows})
        payload = dict(options)
        payload["fetch_sources"] = sources
        return payload


def build_builtin_module_metrics_providers(
    repository: Optional[TortoiseModuleMetricsRepository] = None,
) -> List[_BaseModuleMetricsProvider]:
    repo = repository or TortoiseModuleMetricsRepository()
    return [
        PersonaImageUnderstandingMetricsProvider(repository=repo),
        PersonaImageUrlFallbackMetricsProvider(repository=repo),
    ]
