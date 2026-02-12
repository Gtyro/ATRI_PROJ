import asyncio

import pytest

from src.core.domain import PersonaConfig
from src.infra.llm.providers.ai_processor import AIProcessor

pytestmark = pytest.mark.integration


def _mask_key(api_key: str) -> str:
    if not api_key:
        return "<empty>"
    if len(api_key) <= 6:
        return "*" * len(api_key)
    return f"{api_key[:3]}...{api_key[-3:]}"


def test_llm_api_key_and_model_availability():
    config = PersonaConfig.load()

    assert config.api_key, "api_key is empty in config"
    assert config.model, "model is empty in config"
    assert config.base_url, "base_url is empty in config"

    processor = AIProcessor(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
    )
    response = asyncio.run(
        processor._call_api(
            "You are a ping bot.",
            [{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=1,
        )
    )

    assert isinstance(response, str)
    assert response.strip(), "LLM returned empty response"

    print(f"LLM OK | base_url={config.base_url} | model={config.model} | api_key={_mask_key(config.api_key)}")
