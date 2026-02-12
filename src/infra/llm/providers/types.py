"""Shared LLM provider types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMCallParams:
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1200
    top_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop: Optional[List[str]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_openai_kwargs(self, default_model: str) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": self.model or default_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.presence_penalty is not None:
            kwargs["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            kwargs["frequency_penalty"] = self.frequency_penalty
        if self.stop:
            kwargs["stop"] = self.stop
        if self.extra:
            kwargs.update(self.extra)
        return kwargs


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMToolCallResponse:
    message: Dict[str, Any]
    tool_calls: List[LLMToolCall]


@dataclass
class LLMStructuredOutput:
    data: Any
    raw_text: str

