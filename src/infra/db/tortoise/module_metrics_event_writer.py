"""模块指标事件写入器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional


logger = logging.getLogger(__name__)


class ModuleMetricEventWriter:
    """统一的模块指标事件入库组件。"""

    REQUIRED_FIELDS = ("plugin_name", "module_name", "operation")
    KNOWN_FIELDS = {
        "module_id",
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

    def __init__(self, *, event_model: Any = None, module_model: Any = None) -> None:
        self.event_model = event_model or self._load_default_event_model()
        self.module_model = module_model or self._load_default_module_model()

    @staticmethod
    def _load_default_event_model() -> Any:
        try:
            from tortoise import Tortoise

            models = Tortoise.apps.get("models", {})
            model = models.get("ModuleMetricEvent") or models.get("PluginModuleMetricEvent")
            if model is not None:
                return model
        except Exception:
            pass

        try:
            from src.infra.db.tortoise.plugin_models import ModuleMetricEvent

            return ModuleMetricEvent
        except Exception as exc:
            raise RuntimeError(
                "无法加载 ModuleMetricEvent，请在初始化后显式传入 event_model 参数"
            ) from exc

    @staticmethod
    def _load_default_module_model() -> Any:
        try:
            from tortoise import Tortoise

            model = Tortoise.apps.get("models", {}).get("ModuleMetricModule")
            if model is not None:
                return model
        except Exception:
            pass

        try:
            from src.infra.db.tortoise.plugin_models import ModuleMetricModule

            return ModuleMetricModule
        except Exception:
            return None

    @staticmethod
    def _to_optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _to_optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_bool(value: Any, *, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return bool(value)

    @classmethod
    def _build_module_id(
        cls,
        *,
        module_id: Optional[str],
        plugin_name: str,
        module_name: str,
    ) -> str:
        normalized = cls._to_optional_str(module_id)
        if normalized:
            return normalized
        return f"{plugin_name}.{module_name}"

    @classmethod
    def _build_extra_payload(cls, event: Mapping[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in event.items() if key not in cls.KNOWN_FIELDS}

    @classmethod
    def _resolve_required_fields(cls, event: Mapping[str, Any]) -> Optional[Dict[str, str]]:
        plugin_name = cls._to_optional_str(event.get("plugin_name"))
        module_name = cls._to_optional_str(event.get("module_name"))
        operation = cls._to_optional_str(event.get("operation"))
        if not plugin_name or not module_name or not operation:
            logger.warning(
                "模块指标事件缺失必填字段，已拒绝写入: plugin_name=%s module_name=%s operation=%s request_id=%s",
                plugin_name,
                module_name,
                operation,
                cls._to_optional_str(event.get("request_id")),
            )
            return None
        return {
            "plugin_name": plugin_name,
            "module_name": module_name,
            "operation": operation,
        }

    async def _sync_module_definition(self, *, module_id: str, plugin_name: str, module_name: str) -> None:
        if self.module_model is None:
            return
        try:
            await self.module_model.get_or_create(
                module_id=module_id,
                defaults={
                    "plugin_name": plugin_name,
                    "module_name": module_name,
                    "display_name": module_name,
                    "is_active": True,
                    "extra": {},
                },
            )
        except Exception as exc:
            logger.warning(
                "模块定义同步失败，不影响事件落库: module_id=%s error=%s",
                module_id,
                exc,
            )

    async def write_event(self, event: Any) -> bool:
        if not isinstance(event, Mapping):
            logger.warning("模块指标事件格式错误，已拒绝写入: event_type=%s", type(event).__name__)
            return False

        required = self._resolve_required_fields(event)
        if required is None:
            return False

        plugin_name = required["plugin_name"]
        module_name = required["module_name"]
        operation = required["operation"]
        module_id = self._build_module_id(
            module_id=self._to_optional_str(event.get("module_id")),
            plugin_name=plugin_name,
            module_name=module_name,
        )
        extra = self._build_extra_payload(event)
        try:
            await self.event_model.create(
                module_id=module_id,
                plugin_name=plugin_name,
                module_name=module_name,
                operation=operation,
                conv_id=self._to_optional_str(event.get("conv_id")),
                message_id=self._to_optional_str(event.get("message_id")),
                provider_name=self._to_optional_str(event.get("provider_name")),
                model=self._to_optional_str(event.get("model")),
                request_id=self._to_optional_str(event.get("request_id")),
                success=self._to_bool(event.get("success"), default=True),
                prompt_tokens=self._to_optional_int(event.get("prompt_tokens")),
                completion_tokens=self._to_optional_int(event.get("completion_tokens")),
                total_tokens=self._to_optional_int(event.get("total_tokens")),
                error_type=self._to_optional_str(event.get("error_type")),
                extra=extra,
            )
        except Exception as exc:
            logger.warning(
                "模块指标写入失败: module_id=%s request_id=%s error=%s",
                module_id,
                self._to_optional_str(event.get("request_id")),
                exc,
            )
            return False

        await self._sync_module_definition(
            module_id=module_id,
            plugin_name=plugin_name,
            module_name=module_name,
        )
        return True
