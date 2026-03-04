"""OpenAI-compatible LLM client wrapper."""

from __future__ import annotations

import json
import logging
import re
import inspect
import uuid
from typing import Any, Callable, Dict, List, Optional

from .errors import LLMOutputParseError, LLMProviderError
from .types import LLMCallParams, LLMStructuredOutput, LLMToolCall, LLMToolCallResponse


class LLMClient:
    """统一的 LLM 调用入口（OpenAI 兼容）。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        provider_name: str = "openai_compatible",
        supports_response_format: bool = False,
        timeout: Optional[float] = None,
        usage_event_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.provider_name = provider_name
        self.base_url = base_url
        self.model = model
        self.supports_response_format = supports_response_format
        self.timeout = timeout
        self._usage_event_callback = usage_event_callback
        self._client = None
        self._init_client(api_key, base_url)

    def set_usage_event_callback(self, callback: Optional[Callable[[Dict[str, Any]], Any]]) -> None:
        """设置 usage 事件回调。回调异常会被吞掉并记录 warning。"""
        self._usage_event_callback = callback

    def _init_client(self, api_key: str, base_url: str) -> None:
        try:
            from openai import AsyncOpenAI

            client_kwargs: Dict[str, Any] = {"api_key": api_key, "base_url": base_url}
            if self.timeout is not None:
                client_kwargs["timeout"] = self.timeout
            self._client = AsyncOpenAI(**client_kwargs)
            logging.debug("LLM客户端初始化成功")
        except ImportError:
            logging.error("未安装openai库，请使用pip install openai安装")
            raise
        except Exception as exc:
            logging.error(f"LLM客户端初始化失败: {exc}")
            raise ValueError(f"LLM客户端初始化失败: {exc}") from exc

    @staticmethod
    def _normalize_messages(messages: List[Dict[str, Any]], system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        full_messages: List[Dict[str, Any]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)
        return full_messages

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        content = text.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content).strip()
            if content.endswith("```"):
                content = content[:-3]
        return content.strip()

    @classmethod
    def _parse_json_payload(cls, text: str) -> Any:
        cleaned = cls._strip_code_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 兜底：尝试截取首尾 JSON
            if "{" in cleaned and "}" in cleaned:
                candidate = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
            elif "[" in cleaned and "]" in cleaned:
                candidate = cleaned[cleaned.find("[") : cleaned.rfind("]") + 1]
            else:
                candidate = cleaned
            return json.loads(candidate)

    def _log_event(
        self,
        level: int,
        event: str,
        *,
        request_id: str,
        operation: str,
        **fields: Any,
    ) -> None:
        context = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
        message = (
            f"LLM {event} provider={self.provider_name} model={self.model} "
            f"op={operation} request_id={request_id}"
        )
        if context:
            message = f"{message} {context}"
        logging.log(level, message)

    @staticmethod
    def _extract_usage(response: Any) -> Dict[str, Optional[int]]:
        usage = getattr(response, "usage", None)
        if not usage:
            return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    @staticmethod
    def _normalize_usage_context(usage_context: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not isinstance(usage_context, dict):
            return {}
        normalized: Dict[str, str] = {}
        for key in ("plugin_name", "module_name", "operation", "phase", "resolved_via", "conv_id", "message_id"):
            value = usage_context.get(key)
            if value is None:
                continue
            normalized[key] = str(value)
        return normalized

    @staticmethod
    def _resolve_error_type(exc: BaseException) -> str:
        cause = getattr(exc, "cause", None)
        if isinstance(cause, BaseException):
            return type(cause).__name__
        return type(exc).__name__

    async def _emit_usage_event(
        self,
        *,
        request_id: str,
        operation: str,
        success: bool,
        usage_context: Optional[Dict[str, Any]],
        usage: Optional[Dict[str, Optional[int]]] = None,
        error_type: Optional[str] = None,
    ) -> None:
        callback = getattr(self, "_usage_event_callback", None)
        if callback is None:
            return

        context = self._normalize_usage_context(usage_context)
        event: Dict[str, Any] = {
            "plugin_name": context.get("plugin_name"),
            "module_name": context.get("module_name"),
            "operation": context.get("operation") or operation,
            "phase": context.get("phase"),
            "resolved_via": context.get("resolved_via"),
            "conv_id": context.get("conv_id"),
            "message_id": context.get("message_id"),
            "provider_name": self.provider_name,
            "model": self.model,
            "request_id": request_id,
            "success": success,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "error_type": error_type,
        }
        if success and usage:
            event["prompt_tokens"] = usage.get("prompt_tokens")
            event["completion_tokens"] = usage.get("completion_tokens")
            event["total_tokens"] = usage.get("total_tokens")

        try:
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self._log_event(
                logging.WARNING,
                "usage_callback.error",
                request_id=request_id,
                operation=operation,
                callback_error_type=type(exc).__name__,
            )

    @staticmethod
    def _truncate_text(value: Any, limit: int = 240) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    @classmethod
    def _response_debug_fields(cls, response: Any) -> Dict[str, Any]:
        choices = getattr(response, "choices", None)
        fields: Dict[str, Any] = {
            "response_type": type(response).__name__,
            "response_object": getattr(response, "object", None),
            "response_id": getattr(response, "id", None),
        }
        if isinstance(choices, list):
            fields["choices_len"] = len(choices)
        else:
            fields["choices_type"] = type(choices).__name__ if choices is not None else "None"

        raw_error = getattr(response, "error", None)
        if raw_error is not None:
            fields["response_error"] = cls._truncate_text(raw_error)

        model_dump = getattr(response, "model_dump", None)
        if callable(model_dump):
            try:
                payload = model_dump(exclude_none=True)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                fields["response_keys"] = ",".join(sorted(payload.keys()))
                if raw_error is None and payload.get("error") is not None:
                    fields["response_error"] = cls._truncate_text(payload["error"])

        return fields

    def _raise_invalid_response(self, response: Any, *, operation: str, request_id: str, reason: str) -> None:
        self._log_event(
            logging.ERROR,
            "response.invalid",
            request_id=request_id,
            operation=operation,
            reason=reason,
            **self._response_debug_fields(response),
        )
        raise LLMProviderError(
            "LLM返回异常响应（缺少可用结果）",
            provider=self.provider_name,
            operation=operation,
            request_id=request_id,
            retryable=True,
        )

    def _extract_response_message(self, response: Any, *, operation: str, request_id: str) -> Any:
        choices = getattr(response, "choices", None)
        if not isinstance(choices, list) or not choices:
            self._raise_invalid_response(
                response,
                operation=operation,
                request_id=request_id,
                reason="missing_choices",
            )

        message = getattr(choices[0], "message", None)
        if message is None:
            self._raise_invalid_response(
                response,
                operation=operation,
                request_id=request_id,
                reason="missing_choice_message",
            )
        return message

    @staticmethod
    def _message_content_to_text(message: Any) -> str:
        content = getattr(message, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                else:
                    text = getattr(item, "text", None)
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            return "\n".join(text_parts)
        return str(content)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        params: LLMCallParams,
        *,
        system_prompt: Optional[str] = None,
        operation: str = "chat",
        request_id: Optional[str] = None,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._client is None:
            raise LLMProviderError(
                "LLM客户端未初始化",
                provider=self.provider_name,
                operation=operation,
                request_id=request_id,
            )
        request_id = request_id or uuid.uuid4().hex
        full_messages = self._normalize_messages(messages, system_prompt)
        self._log_event(
            logging.INFO,
            "request.start",
            request_id=request_id,
            operation=operation,
            messages=len(full_messages),
        )
        usage: Optional[Dict[str, Optional[int]]] = None
        try:
            try:
                kwargs = params.to_openai_kwargs(self.model)
                response = await self._client.chat.completions.create(
                    messages=full_messages,
                    **kwargs,
                )
            except Exception as exc:
                self._log_event(
                    logging.ERROR,
                    "request.error",
                    request_id=request_id,
                    operation=operation,
                    error_type=type(exc).__name__,
                )
                raise LLMProviderError(
                    "LLM请求失败",
                    provider=self.provider_name,
                    operation=operation,
                    request_id=request_id,
                    retryable=True,
                    cause=exc,
                ) from exc

            usage = self._extract_usage(response)
            self._log_event(
                logging.INFO,
                "request.success",
                request_id=request_id,
                operation=operation,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            )
            response_message = self._extract_response_message(
                response,
                operation=operation,
                request_id=request_id,
            )
            content = self._message_content_to_text(response_message)
        except Exception as exc:
            await self._emit_usage_event(
                request_id=request_id,
                operation=operation,
                success=False,
                usage_context=usage_context,
                error_type=self._resolve_error_type(exc),
            )
            raise

        await self._emit_usage_event(
            request_id=request_id,
            operation=operation,
            success=True,
            usage_context=usage_context,
            usage=usage,
        )
        return content

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        params: LLMCallParams,
        *,
        tool_choice: str = "auto",
        system_prompt: Optional[str] = None,
        operation: str = "tool_call",
        request_id: Optional[str] = None,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> LLMToolCallResponse:
        if self._client is None:
            raise LLMProviderError(
                "LLM客户端未初始化",
                provider=self.provider_name,
                operation=operation,
                request_id=request_id,
            )
        request_id = request_id or uuid.uuid4().hex
        full_messages = self._normalize_messages(messages, system_prompt)
        self._log_event(
            logging.INFO,
            "request.start",
            request_id=request_id,
            operation=operation,
            messages=len(full_messages),
        )
        usage: Optional[Dict[str, Optional[int]]] = None
        try:
            try:
                kwargs = params.to_openai_kwargs(self.model)
                response = await self._client.chat.completions.create(
                    messages=full_messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                )
            except Exception as exc:
                self._log_event(
                    logging.ERROR,
                    "request.error",
                    request_id=request_id,
                    operation=operation,
                    error_type=type(exc).__name__,
                )
                raise LLMProviderError(
                    "LLM工具调用请求失败",
                    provider=self.provider_name,
                    operation=operation,
                    request_id=request_id,
                    retryable=True,
                    cause=exc,
                ) from exc

            usage = self._extract_usage(response)
            self._log_event(
                logging.INFO,
                "request.success",
                request_id=request_id,
                operation=operation,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            )

            response_message = self._extract_response_message(
                response,
                operation=operation,
                request_id=request_id,
            )
            tool_calls: List[LLMToolCall] = []
            if getattr(response_message, "tool_calls", None):
                for tool_call in response_message.tool_calls:
                    tool_calls.append(
                        LLMToolCall(
                            id=tool_call.id,
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments,
                        )
                    )

            message: Dict[str, Any] = {
                "role": "assistant",
                "content": self._message_content_to_text(response_message),
            }
            if tool_calls:
                message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    }
                    for call in tool_calls
                ]
            result = LLMToolCallResponse(message=message, tool_calls=tool_calls)
        except Exception as exc:
            await self._emit_usage_event(
                request_id=request_id,
                operation=operation,
                success=False,
                usage_context=usage_context,
                error_type=self._resolve_error_type(exc),
            )
            raise

        await self._emit_usage_event(
            request_id=request_id,
            operation=operation,
            success=True,
            usage_context=usage_context,
            usage=usage,
        )
        return result

    async def structured_output(
        self,
        messages: List[Dict[str, Any]],
        params: LLMCallParams,
        *,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        operation: str = "structured_output",
        request_id: Optional[str] = None,
        strict: bool = True,
        usage_context: Optional[Dict[str, Any]] = None,
    ) -> LLMStructuredOutput:
        if self._client is None:
            raise LLMProviderError(
                "LLM客户端未初始化",
                provider=self.provider_name,
                operation=operation,
                request_id=request_id,
            )
        request_id = request_id or uuid.uuid4().hex
        full_messages = self._normalize_messages(messages, system_prompt)
        self._log_event(
            logging.INFO,
            "request.start",
            request_id=request_id,
            operation=operation,
            messages=len(full_messages),
        )
        usage: Optional[Dict[str, Optional[int]]] = None
        try:
            try:
                kwargs = params.to_openai_kwargs(self.model)
                if self.supports_response_format:
                    if schema:
                        kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {"name": "output", "schema": schema},
                        }
                    else:
                        kwargs["response_format"] = {"type": "json_object"}
                response = await self._client.chat.completions.create(
                    messages=full_messages,
                    **kwargs,
                )
            except Exception as exc:
                self._log_event(
                    logging.ERROR,
                    "request.error",
                    request_id=request_id,
                    operation=operation,
                    error_type=type(exc).__name__,
                )
                raise LLMProviderError(
                    "LLM结构化输出请求失败",
                    provider=self.provider_name,
                    operation=operation,
                    request_id=request_id,
                    retryable=True,
                    cause=exc,
                ) from exc

            usage = self._extract_usage(response)
            self._log_event(
                logging.INFO,
                "request.success",
                request_id=request_id,
                operation=operation,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            )

            response_message = self._extract_response_message(
                response,
                operation=operation,
                request_id=request_id,
            )
            content = self._message_content_to_text(response_message)
            try:
                data = self._parse_json_payload(content)
            except json.JSONDecodeError as exc:
                if strict:
                    raise LLMOutputParseError(
                        "结构化输出解析失败",
                        provider=self.provider_name,
                        operation=operation,
                        request_id=request_id,
                        retryable=True,
                        cause=exc,
                    ) from exc
                result = LLMStructuredOutput(data=None, raw_text=content)
            else:
                result = LLMStructuredOutput(data=data, raw_text=content)
        except Exception as exc:
            await self._emit_usage_event(
                request_id=request_id,
                operation=operation,
                success=False,
                usage_context=usage_context,
                error_type=self._resolve_error_type(exc),
            )
            raise

        await self._emit_usage_event(
            request_id=request_id,
            operation=operation,
            success=True,
            usage_context=usage_context,
            usage=usage,
        )
        return result
