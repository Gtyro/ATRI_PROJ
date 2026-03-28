import asyncio
import json

from src.infra.llm.providers.ai_processor import AIProcessor
from src.infra.llm.providers.types import (
    LLMStructuredOutput,
    LLMToolCall,
    LLMToolCallResponse,
)


class _FakeLLMClient:
    def __init__(self):
        self.final_messages = None
        self.system_prompts = []

    async def chat_with_tools(
        self,
        messages,
        tools,
        params,
        *,
        tool_choice="auto",
        system_prompt=None,
        operation="tool_call",
        request_id=None,
        usage_context=None,
    ):
        assert operation == "memory_tool_call"
        self.system_prompts.append((operation, system_prompt))
        tool_call = LLMToolCall(
            id="tool-1",
            name="retrieve_memories",
            arguments=json.dumps({"query": "张三"}),
        )
        return LLMToolCallResponse(
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                    }
                ],
            },
            tool_calls=[tool_call],
        )

    async def structured_output(
        self,
        messages,
        params,
        *,
        system_prompt=None,
        schema=None,
        operation="structured_output",
        request_id=None,
        strict=True,
        usage_context=None,
    ):
        assert operation == "memory_candidate_selection"
        return LLMStructuredOutput(
            data={"selected_ids": ["mem-2"]},
            raw_text='{"selected_ids":["mem-2"]}',
        )

    async def chat(
        self,
        messages,
        params,
        *,
        system_prompt=None,
        operation="chat",
        request_id=None,
        usage_context=None,
    ):
        if operation == "final_response":
            self.system_prompts.append((operation, system_prompt))
            self.final_messages = list(messages)
            return "收到"
        self.system_prompts.append((operation, system_prompt))
        return "fallback"


def test_generate_response_selects_memory_candidates_and_uses_selected_context():
    processor = object.__new__(AIProcessor)
    processor.group_character = {}
    processor.memory_retrieval_callback = None
    processor.raise_on_error = True
    processor._llm_client = _FakeLLMClient()

    callback_calls = []

    async def payload_callback(
        query,
        user_id=None,
        conv_id=None,
        selected_ids=None,
        reinforce_selected=False,
    ):
        callback_calls.append({
            "query": query,
            "user_id": user_id,
            "conv_id": conv_id,
            "selected_ids": list(selected_ids or []),
            "reinforce_selected": reinforce_selected,
        })
        if selected_ids:
            return {
                "memory_context": "我记得这些内容:\n1. [topic]【项目A状态】项目A延期到下周 (2026-03-17 10:00)\n",
                "candidates": [],
                "selected_ids": list(selected_ids),
            }
        return {
            "memory_context": "我记得这些内容:\n1. [topic]【张三近况】张三最近在做项目A (2026-03-17 10:00)\n",
            "candidates": [
                {
                    "id": "mem-1",
                    "title": "张三近况",
                    "summary": "张三最近在做项目A",
                    "source": "topic",
                    "weight": 1.2,
                    "created_at": 1742205600.0,
                },
                {
                    "id": "mem-2",
                    "title": "项目A状态",
                    "summary": "项目A延期到下周",
                    "source": "topic",
                    "weight": 1.0,
                    "created_at": 1742205601.0,
                },
            ],
            "selected_ids": [],
        }

    processor.memory_retrieval_callback = payload_callback

    response = asyncio.run(
        processor.generate_response(
            conv_id="private_1",
            messages=[{"role": "user", "content": "你还记得张三吗？"}],
            tool_choice="required",
        )
    )

    assert response == "收到"
    assert callback_calls == [
        {
            "query": "张三",
            "user_id": None,
            "conv_id": "private_1",
            "selected_ids": [],
            "reinforce_selected": False,
        },
        {
            "query": "张三",
            "user_id": None,
            "conv_id": "private_1",
            "selected_ids": ["mem-2"],
            "reinforce_selected": True,
        },
    ]
    assert any(
        message.get("role") == "tool" and "【项目A状态】项目A延期到下周" in message.get("content", "")
        for message in processor._llm_client.final_messages
    )
    assert any(
        "不要重复、轻微改写、补说或续写你最近一条回复" in (system_prompt or "")
        for _, system_prompt in processor._llm_client.system_prompts
    )


class _PromptOnlyLLMClient:
    def __init__(self):
        self.system_prompts = []

    async def chat(
        self,
        messages,
        params,
        *,
        system_prompt=None,
        operation="chat",
        request_id=None,
        usage_context=None,
    ):
        self.system_prompts.append((operation, system_prompt))
        return "收到"


def test_generate_response_adds_anti_repeat_instruction_to_prompt():
    processor = object.__new__(AIProcessor)
    processor.group_character = {}
    processor.memory_retrieval_callback = None
    processor.raise_on_error = True
    processor._llm_client = _PromptOnlyLLMClient()

    response = asyncio.run(
        processor.generate_response(
            conv_id="private_1",
            messages=[{"role": "user", "content": "么么哒"}],
            tool_choice="none",
        )
    )

    assert response == "收到"
    assert processor._llm_client.system_prompts == [
        (
            "no_tool_response",
            processor._llm_client.system_prompts[0][1],
        )
    ]
    assert "不要重复、轻微改写、补说或续写你最近一条回复" in processor._llm_client.system_prompts[0][1]
