import asyncio

import pytest

from src.infra.llm.providers.ai_processor import AIProcessor


def test_generate_response_rejects_unknown_tool_choice_when_raise_on_error_enabled():
    processor = object.__new__(AIProcessor)
    processor.group_character = {}
    processor.memory_retrieval_callback = None
    processor.raise_on_error = True
    processor._llm_client = object()

    with pytest.raises(ValueError):
        asyncio.run(
            processor.generate_response(
                conv_id="private_1",
                messages=[],
                tool_choice="invalid",
            )
        )
