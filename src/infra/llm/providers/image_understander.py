"""图片理解 Provider。"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .client import LLMClient
from .errors import LLMProviderError
from .types import LLMCallParams


logger = logging.getLogger(__name__)

DEFAULT_OBSERVATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "visible_facts": {"type": "array", "items": {"type": "string"}},
        "key_values": {"type": "array", "items": {"type": "string"}},
        "ocr_text": {"type": "array", "items": {"type": "string"}},
        "ui_elements": {"type": "array", "items": {"type": "string"}},
        "charts": {"type": "array", "items": {"type": "string"}},
        "tables": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "visible_facts",
        "key_values",
        "ocr_text",
        "ui_elements",
        "charts",
        "tables",
        "warnings",
        "uncertainties",
    ],
    "additionalProperties": False,
}


@dataclass
class ImageObservationResult:
    display_text: str = ""
    observation: Dict[str, Any] = field(default_factory=dict)
    detail: str = "auto"
    provider_name: str = ""
    model: str = ""


@dataclass
class _ImageProviderRuntime:
    provider_name: str
    api_key: str
    base_url: str
    model: str
    client: LLMClient


class ImageUnderstander:
    """使用独立 LLMClient 进行结构化图片观察。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_tokens: int = 2000,
        detail: str = "auto",
        providers: Optional[List[Dict[str, Any]]] = None,
        provider_name: str = "image_understander",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        normalized_detail = str(detail or "auto").strip().lower() or "auto"
        self.detail = normalized_detail if normalized_detail in {"auto", "high", "low"} else "auto"
        self.provider_name = provider_name
        self._provider_runtimes = self._build_provider_runtimes(
            providers=providers,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        primary = self._provider_runtimes[0] if self._provider_runtimes else None
        self.api_key = primary.api_key if primary else str(api_key or "").strip()
        self.base_url = primary.base_url if primary else str(base_url or "").strip()
        self.model = primary.model if primary else str(model or "").strip()
        if not self._provider_runtimes:
            logger.warning("图片理解 Provider 初始化跳过：没有可用 provider")

    def set_usage_event_callback(self, callback: Optional[Callable[[Dict[str, Any]], Any]]) -> None:
        """设置图片理解 usage 事件回调。"""
        for runtime in self._provider_runtimes:
            runtime.client.set_usage_event_callback(callback)

    async def inspect_images(
        self,
        images: List[Dict[str, Any]],
        *,
        usage_contexts: Optional[List[Optional[Dict[str, Any]]]] = None,
    ) -> List[ImageObservationResult]:
        """输入多图，输出等长结构化观察结果。失败项返回空结果。"""
        if not images:
            return []
        if not self._provider_runtimes:
            return [ImageObservationResult(detail=self.detail, model=self.model) for _ in images]

        results: List[ImageObservationResult] = []
        for index, image in enumerate(images):
            usage_context: Optional[Dict[str, Any]] = None
            if usage_contexts and index < len(usage_contexts):
                candidate = usage_contexts[index]
                if isinstance(candidate, dict):
                    usage_context = dict(candidate)
            if usage_context is None:
                usage_context = {}
            usage_context.setdefault("detail", self.detail)
            usage_context.setdefault("response_api", "responses")
            result = await self._inspect_single_image(image, usage_context=usage_context)
            results.append(result)
        return results

    async def _inspect_single_image(
        self,
        image: Dict[str, Any],
        *,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> ImageObservationResult:
        if not self._provider_runtimes:
            return ImageObservationResult(detail=self.detail, model=self.model)
        image_url = self._build_image_url(image)
        if not image_url:
            return ImageObservationResult(detail=self.detail, model=self.model)

        prompt = (
            "你是一个图片观察器。请只根据图片提取客观可见事实，不要结合聊天上下文，不要脑补。"
            "输出必须是简体中文 JSON。"
            "summary 用一句简短中文概括图片主体。"
            "visible_facts 记录稳定可见事实。"
            "key_values 记录重要键值对，格式使用“键: 值”。"
            "ocr_text 记录图片中能可靠读出的文字片段。"
            "ui_elements/charts/tables 用于截图、仪表盘、网页、表格等场景。"
            "看不清或不确定的内容写入 uncertainties，不要猜测。"
        )
        input_items = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": self.detail,
                    },
                ],
            }
        ]
        params = LLMCallParams(temperature=0.2, max_tokens=self.max_tokens)
        for provider_index, runtime in enumerate(self._provider_runtimes):
            provider_usage_context = dict(usage_context or {})
            provider_usage_context.setdefault("detail", self.detail)
            provider_usage_context.setdefault("response_api", "responses")
            provider_usage_context.setdefault("fallback_index", provider_index)
            try:
                result = await self._inspect_with_runtime(
                    runtime=runtime,
                    input_items=input_items,
                    params=params,
                    usage_context=provider_usage_context,
                )
                if result.display_text:
                    return result
            except Exception as exc:
                logger.warning(
                    "图片理解 provider 全部重试失败: provider=%s model=%s error=%s",
                    runtime.provider_name,
                    runtime.model,
                    exc,
                )
            if provider_index < len(self._provider_runtimes) - 1:
                logger.warning(
                    "图片理解切换到下一个 provider: from=%s model=%s next=%s",
                    runtime.provider_name,
                    runtime.model,
                    self._provider_runtimes[provider_index + 1].provider_name,
                )
        return ImageObservationResult(detail=self.detail, model=self.model)

    async def _inspect_with_runtime(
        self,
        *,
        runtime: _ImageProviderRuntime,
        input_items: List[Dict[str, Any]],
        params: LLMCallParams,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> ImageObservationResult:
        for attempt in range(2):
            try:
                output = await runtime.client.response_json(
                    input_items=input_items,
                    schema=DEFAULT_OBSERVATION_SCHEMA,
                    params=params,
                    schema_name="image_observation",
                    operation="image_understanding",
                    usage_context=usage_context,
                )
                normalized = self._normalize_observation(output.data)
                display_text = self._build_display_text(normalized)
                if display_text:
                    return ImageObservationResult(
                        display_text=display_text,
                        observation=normalized,
                        detail=self.detail,
                        provider_name=runtime.provider_name,
                        model=runtime.model,
                    )
                logger.warning(
                    "图片理解返回空观察结果，准备重试: provider=%s attempt=%s",
                    runtime.provider_name,
                    attempt + 1,
                )
            except LLMProviderError as exc:
                logger.warning(
                    "图片理解调用失败: provider=%s attempt=%s error=%s",
                    runtime.provider_name,
                    attempt + 1,
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "图片理解异常: provider=%s attempt=%s error=%s",
                    runtime.provider_name,
                    attempt + 1,
                    exc,
                )
        return ImageObservationResult(
            detail=self.detail,
            provider_name=runtime.provider_name,
            model=runtime.model,
        )

    def _build_provider_runtimes(
        self,
        *,
        providers: Optional[List[Dict[str, Any]]],
        api_key: str,
        base_url: str,
        model: str,
    ) -> List[_ImageProviderRuntime]:
        provider_specs = self._normalize_provider_specs(providers, api_key=api_key, base_url=base_url, model=model)
        runtimes: List[_ImageProviderRuntime] = []
        for index, spec in enumerate(provider_specs):
            if not (spec["api_key"] and spec["base_url"] and spec["model"]):
                logger.warning("图片理解 Provider 初始化跳过：缺少 api_key/base_url/model index=%s", index)
                continue
            runtime_name = str(spec.get("name") or f"{self.provider_name}_{index + 1}").strip()
            try:
                runtimes.append(
                    _ImageProviderRuntime(
                        provider_name=runtime_name,
                        api_key=str(spec["api_key"]),
                        base_url=str(spec["base_url"]),
                        model=str(spec["model"]),
                        client=LLMClient(
                            api_key=str(spec["api_key"]),
                            base_url=str(spec["base_url"]),
                            model=str(spec["model"]),
                            provider_name=runtime_name,
                            timeout=self.timeout_seconds,
                        ),
                    )
                )
            except Exception as exc:
                logger.warning("图片理解 Provider 初始化失败，跳过 provider=%s error=%s", runtime_name, exc)
        return runtimes

    @staticmethod
    def _normalize_provider_specs(
        providers: Optional[List[Dict[str, Any]]],
        *,
        api_key: str,
        base_url: str,
        model: str,
    ) -> List[Dict[str, str]]:
        if isinstance(providers, list) and providers:
            normalized: List[Dict[str, str]] = []
            for index, item in enumerate(providers):
                if not isinstance(item, dict):
                    continue
                normalized.append(
                    {
                        "name": str(item.get("name") or f"provider_{index + 1}").strip(),
                        "api_key": str(item.get("api_key") or "").strip(),
                        "base_url": str(item.get("base_url") or "").strip(),
                        "model": str(item.get("model") or "").strip(),
                    }
                )
            return normalized
        return [
            {
                "name": "primary",
                "api_key": str(api_key or "").strip(),
                "base_url": str(base_url or "").strip(),
                "model": str(model or "").strip(),
            }
        ]

    @staticmethod
    def _normalize_string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        normalized: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @classmethod
    def _normalize_observation(cls, payload: Any) -> Dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        return {
            "summary": str(data.get("summary") or "").strip(),
            "visible_facts": cls._normalize_string_list(data.get("visible_facts")),
            "key_values": cls._normalize_string_list(data.get("key_values")),
            "ocr_text": cls._normalize_string_list(data.get("ocr_text")),
            "ui_elements": cls._normalize_string_list(data.get("ui_elements")),
            "charts": cls._normalize_string_list(data.get("charts")),
            "tables": cls._normalize_string_list(data.get("tables")),
            "warnings": cls._normalize_string_list(data.get("warnings")),
            "uncertainties": cls._normalize_string_list(data.get("uncertainties")),
        }

    @staticmethod
    def _build_display_text(observation: Dict[str, Any]) -> str:
        summary = str(observation.get("summary") or "").strip()
        if summary:
            return summary
        for key in ("visible_facts", "key_values", "ocr_text", "ui_elements"):
            values = observation.get(key)
            if isinstance(values, list) and values:
                return str(values[0]).strip()
        return ""

    @staticmethod
    def _build_image_url(image: Dict[str, Any]) -> str:
        image_bytes = image.get("image_bytes")
        if isinstance(image_bytes, bytes) and image_bytes:
            mime = str(image.get("mime") or "image/jpeg").strip() or "image/jpeg"
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            return f"data:{mime};base64,{encoded}"

        raw_url = image.get("url")
        if raw_url:
            return str(raw_url)
        return ""
