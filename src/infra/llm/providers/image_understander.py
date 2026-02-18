"""图片理解 Provider。"""

from __future__ import annotations

import base64
import logging
from typing import Any, Callable, Dict, List, Optional

from .client import LLMClient
from .errors import LLMProviderError
from .types import LLMCallParams


logger = logging.getLogger(__name__)


class ImageUnderstander:
    """使用独立 LLMClient 进行图片摘要。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_tokens: int = 2000,
        provider_name: str = "image_understander",
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.provider_name = provider_name
        self._llm_client: Optional[LLMClient] = None

        if self.api_key and self.base_url and self.model:
            try:
                self._llm_client = LLMClient(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    model=self.model,
                    provider_name=self.provider_name,
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                logger.warning("图片理解 Provider 初始化失败，已降级为禁用状态: %s", exc)
                self._llm_client = None
        else:
            logger.warning("图片理解 Provider 初始化跳过：缺少 api_key/base_url/model")

    def set_usage_event_callback(self, callback: Optional[Callable[[Dict[str, Any]], Any]]) -> None:
        """设置图片理解 usage 事件回调。"""
        if self._llm_client is None:
            return
        self._llm_client.set_usage_event_callback(callback)

    async def summarize_images(
        self,
        images: List[Dict[str, Any]],
        *,
        usage_contexts: Optional[List[Optional[Dict[str, Any]]]] = None,
    ) -> List[str]:
        """输入多图，输出等长短摘要列表。失败项返回空字符串。"""
        if not images:
            return []
        if self._llm_client is None:
            return ["" for _ in images]

        summaries: List[str] = []
        for index, image in enumerate(images):
            usage_context: Optional[Dict[str, Any]] = None
            if usage_contexts and index < len(usage_contexts):
                candidate = usage_contexts[index]
                if isinstance(candidate, dict):
                    usage_context = candidate
            summary = await self._summarize_single_image(image, usage_context=usage_context)
            summaries.append(summary)
        return summaries

    async def _summarize_single_image(
        self,
        image: Dict[str, Any],
        *,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._llm_client is None:
            return ""
        image_url = self._build_image_url(image)
        if not image_url:
            return ""

        prompt = (
            "请用简体中文概括图片中和当前聊天最相关的信息。"
            "只输出1句简短描述，不要加前后缀。"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]
        params = LLMCallParams(temperature=0.2, max_tokens=self.max_tokens)
        for attempt in range(2):
            try:
                output = await self._llm_client.chat(
                    messages,
                    params=params,
                    operation="image_understanding",
                    usage_context=usage_context,
                )
                text = (output or "").strip()
                if text:
                    return text
                logger.warning("图片理解返回空摘要，准备重试: attempt=%s", attempt + 1)
            except LLMProviderError as exc:
                logger.warning("图片理解调用失败: attempt=%s error=%s", attempt + 1, exc)
            except Exception as exc:
                logger.warning("图片理解异常: attempt=%s error=%s", attempt + 1, exc)
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
