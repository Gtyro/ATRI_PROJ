import asyncio
import os
from pathlib import Path

import pytest
import yaml

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
    if os.environ.get("RUN_LLM_INTEGRATION") != "1":
        pytest.skip("set RUN_LLM_INTEGRATION=1 to explicitly enable live LLM checks")
    api_key = os.environ.get("TEST_OPENAI_API_KEY")
    if not api_key:
        pytest.skip("set TEST_OPENAI_API_KEY to explicitly provide a test API key")

    raw_config = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "data/persona/persona.yaml").read_text(
            encoding="utf-8"
        )
    )
    config = PersonaConfig.from_dict(raw_config)
    base_url = os.environ.get("TEST_OPENAI_BASE_URL", config.base_url)
    model = os.environ.get("TEST_OPENAI_MODEL", config.model)

    assert model, "model is empty in test configuration"
    assert base_url, "base_url is empty in test configuration"

    processor = AIProcessor(
        api_key=api_key,
        model=model,
        base_url=base_url,
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

    print(f"LLM OK | base_url={base_url} | model={model} | api_key={_mask_key(api_key)}")
