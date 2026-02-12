"""LLM provider fallback chain."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional


class FallbackLLMProvider:
    """按顺序尝试多个LLM Provider的回退实现。"""

    def __init__(self, providers: List[Any], *, name: str = "fallback") -> None:
        if not providers:
            raise ValueError("providers不能为空")
        self.providers = providers
        self.name = name
        self.memory_retrieval_callback: Optional[Callable[..., Any]] = None

    @staticmethod
    def _provider_label(provider: Any) -> str:
        return (
            getattr(provider, "provider_name", None)
            or getattr(provider, "name", None)
            or provider.__class__.__name__
        )

    async def _call_with_fallback(
        self,
        method_name: str,
        fallback_value: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        last_error: Optional[Exception] = None
        for index, provider in enumerate(self.providers):
            label = self._provider_label(provider)
            try:
                method: Callable[..., Awaitable[Any]] = getattr(provider, method_name)
                return await method(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                logging.warning(
                    f"LLM provider 调用失败，准备回退: provider={label} "
                    f"index={index} error={type(exc).__name__} {exc}"
                )
        if last_error:
            logging.error(f"所有LLM provider均失败: last_error={last_error}")
        return fallback_value

    async def extract_topics(self, conv_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return await self._call_with_fallback("extract_topics", [], conv_id, messages)

    async def extract_reply_keywords_from_history(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[str]:
        return await self._call_with_fallback("extract_reply_keywords_from_history", [], conv_id, messages)

    async def generate_response(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        long_memory_prompt: str = "",
        tool_choice: str = "required",
    ) -> str:
        return await self._call_with_fallback(
            "generate_response",
            "",
            conv_id,
            messages,
            temperature=temperature,
            long_memory_prompt=long_memory_prompt,
            tool_choice=tool_choice,
        )

    def set_memory_retrieval_callback(self, callback: Callable[..., Any]) -> None:
        """向回退链中的可用 provider 下发记忆检索回调。"""
        self.memory_retrieval_callback = callback
        for provider in self.providers:
            setter = getattr(provider, "set_memory_retrieval_callback", None)
            if callable(setter):
                setter(callback)
                continue
            logging.warning(
                "provider 未实现 set_memory_retrieval_callback，跳过回调注入: provider=%s",
                self._provider_label(provider),
            )
