import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.adapters.nonebot import command_registry
from src.infra.llm.providers.image_generator import ImageGenerationError


@pytest.fixture
def image_plugin(monkeypatch):
    matcher = SimpleNamespace(handle=lambda: (lambda handler: handler))
    monkeypatch.setattr(command_registry, "register_command", lambda *args, **kwargs: matcher)
    # Load the isolated command module without starting NoneBot or reading env files.
    path = Path(__file__).resolve().parents[2] / "plugins" / "image_generation.py"
    spec = importlib.util.spec_from_file_location("image_generation_error_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_image_command_reports_safe_upstream_reason_and_request_id(image_plugin, monkeypatch, caplog):
    error = ImageGenerationError(
        "图像生成服务返回 HTTP 404", code="not_found", status_code=404,
        request_id="req-command-failed", detail="No such model; token=private-key",
        endpoint="https://images.test/v1/images/generations", model="test-model",
    )
    generator = SimpleNamespace(generate=AsyncMock(side_effect=error))
    monkeypatch.setattr(image_plugin, "_get_generator", lambda: (generator, True))
    matcher = SimpleNamespace(finish=AsyncMock())

    asyncio.run(image_plugin._handle_generation(matcher, "a cat"))

    response = matcher.finish.await_args.args[0]
    assert "HTTP 404" in response
    assert "No such model" in response
    assert "req-command-failed" in response
    assert "status=404" in caplog.text
    assert "req-command-failed" in caplog.text
    assert "private-key" not in response + caplog.text
    assert "稍后重试" not in response


def test_unexpected_image_command_error_is_sanitized(image_plugin, monkeypatch, caplog):
    generator = SimpleNamespace(
        api_key="synthetic-private-key",
        generate=AsyncMock(side_effect=RuntimeError(
            "internal failure: synthetic-private-key; prompt=a cat",
        )),
    )
    monkeypatch.setattr(image_plugin, "_get_generator", lambda: (generator, True))
    matcher = SimpleNamespace(finish=AsyncMock())

    asyncio.run(image_plugin._handle_generation(matcher, "a cat"))

    response = matcher.finish.await_args.args[0]
    assert "检查错误日志" in response
    assert "internal failure" in caplog.text
    assert "synthetic-private-key" not in caplog.text
    assert "a cat" not in caplog.text
