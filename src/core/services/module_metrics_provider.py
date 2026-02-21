"""模块指标 Provider 抽象与注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class ModuleMetricsQuery:
    """Provider 查询上下文。"""

    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    plugin_name: Optional[str] = None
    module_name: Optional[str] = None
    operation: Optional[str] = None
    conv_id: Optional[str] = None


class ModuleMetricsProvider(Protocol):
    """模块指标 Provider 统一接口。"""

    module_id: str

    def get_module_definition(self) -> Dict[str, Any]:
        """返回模块定义（模块元信息）。"""

    async def get_overview(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        """返回模块主图与主 KPI。"""

    async def get_detail(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        """返回模块详情图表集合。"""

    async def get_filter_options(self, query: ModuleMetricsQuery) -> Dict[str, Any]:
        """返回模块私有筛选项。"""


class ModuleMetricsProviderRegistry:
    """Provider 注册表。"""

    def __init__(self, providers: Optional[Iterable[ModuleMetricsProvider]] = None) -> None:
        self._providers: Dict[str, ModuleMetricsProvider] = {}
        if providers:
            for provider in providers:
                self.register(provider)

    @staticmethod
    def _normalize_module_id(module_id: str) -> str:
        text = str(module_id or "").strip()
        if not text:
            raise ValueError("module_id 不能为空")
        return text

    def register(self, provider: ModuleMetricsProvider) -> None:
        module_id = self._normalize_module_id(getattr(provider, "module_id", ""))
        if module_id in self._providers:
            raise ValueError(f"module provider 已存在: {module_id}")
        self._providers[module_id] = provider

    def get(self, module_id: str) -> ModuleMetricsProvider:
        normalized = self._normalize_module_id(module_id)
        provider = self._providers.get(normalized)
        if provider is None:
            raise KeyError(normalized)
        return provider

    def has(self, module_id: str) -> bool:
        try:
            normalized = self._normalize_module_id(module_id)
        except ValueError:
            return False
        return normalized in self._providers

    def list(self) -> List[ModuleMetricsProvider]:
        return [self._providers[module_id] for module_id in sorted(self._providers.keys())]

    def list_module_definitions(self) -> List[Dict[str, Any]]:
        definitions: List[Dict[str, Any]] = []
        for provider in self.list():
            definition = provider.get_module_definition()
            if not isinstance(definition, dict):
                continue
            item = dict(definition)
            item.setdefault("module_id", provider.module_id)
            definitions.append(item)
        return definitions
