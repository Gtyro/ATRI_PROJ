"""LLM provider errors."""

from __future__ import annotations

from typing import Optional


class LLMProviderError(RuntimeError):
    """Standardized LLM provider error."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        operation: str,
        request_id: Optional[str] = None,
        retryable: bool = False,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.request_id = request_id
        self.retryable = retryable
        self.cause = cause


class LLMOutputParseError(LLMProviderError):
    """Raised when structured output parsing fails."""

