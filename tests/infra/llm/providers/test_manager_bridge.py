import asyncio
from pathlib import Path

import pytest
from llm_request_kit import LLMError, Result, Usage

from src.infra.llm.providers import manager_bridge
from src.infra.llm.providers.client import LLMClient, _mark_tracked_request
from src.infra.llm.providers.image_understander import ImageUnderstander
from src.core.domain import runtime_settings


def test_manager_mode_uses_persistent_runtime_setting(tmp_path, monkeypatch):
    (tmp_path / ".env.prod").write_text("LLM_REQUEST_KIT_MANAGER=1\n", encoding="utf-8")
    monkeypatch.setattr(runtime_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("LLM_REQUEST_KIT_MANAGER", raising=False)
    assert manager_bridge.enabled() is True

    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "0")
    assert manager_bridge.enabled() is False


def test_managed_clients_use_provider_settings_and_record_each_request(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    providers = {
        "ai_processor": {
            "api_key": "managed-key", "base_url": "https://managed.test/v1",
            "model": "managed-model", "api": "responses", "timeout": 12,
            "max_attempts": 2,
        },
        "image_understander": {
            "api_key": "image-key", "base_url": "https://images.test/v1",
            "model": "image-model", "api": "responses",
        },
    }
    monkeypatch.setattr(manager_bridge, "load_project_config", lambda project: providers)
    monkeypatch.setattr(manager_bridge, "load_project_routes", lambda project: {})
    events = []
    monkeypatch.setattr(manager_bridge, "record_usage", lambda project, event: events.append((project, event)))

    client = LLMClient(api_key="legacy", base_url="https://legacy.test/v1",
                       model="legacy-model", provider_name="ai_processor")
    assert (client._api_key, client.base_url, client.model, client.timeout, client._max_attempts) == (
        "managed-key", "https://managed.test/v1", "managed-model", 12, 2)

    class Shared:
        model = "managed-model"

        async def arequest(self, *_args, **_kwargs):
            await _mark_tracked_request(None)
            return Result(text="ok", usage=Usage(input_tokens=5, output_tokens=3), attempts=2)

    assert asyncio.run(client._request_shared(Shared(), "hello")).text == "ok"
    assert events[0][0] == "ATRI_PROJ"
    assert events[0][1]["success"] is True
    assert events[0][1]["attempts"] == 2
    assert events[0][1]["input_tokens"] == 5

    image = ImageUnderstander(api_key="", base_url="", model="")
    assert image._provider_runtimes[0].provider_name == "image_understander"
    assert image._provider_runtimes[0].model == "image-model"


def test_managed_client_fails_closed_and_records_failed_request(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    monkeypatch.setattr(manager_bridge, "load_project_config", lambda project: {
        "ai_processor": {"api_key": "key", "base_url": "https://managed.test/v1", "model": "model"}
    })
    monkeypatch.setattr(manager_bridge, "load_project_routes", lambda project: {})
    events = []
    monkeypatch.setattr(manager_bridge, "record_usage", lambda project, event: events.append(event))
    client = LLMClient(api_key="legacy", base_url="https://legacy.test/v1",
                       model="legacy", provider_name="ai_processor")

    class Shared:
        model = "model"

        async def arequest(self, *_args, **_kwargs):
            await _mark_tracked_request(None)
            raise LLMError("failed", code="rate_limit", attempts=2)

    with pytest.raises(LLMError):
        asyncio.run(client._request_shared(Shared(), "hello"))
    assert events[0]["success"] is False
    assert events[0]["attempts"] == 2
    assert events[0]["error_code"] == "rate_limit"

    monkeypatch.setattr(manager_bridge, "load_project_config",
                        lambda project: (_ for _ in ()).throw(ConnectionRefusedError("manager offline")))
    with pytest.raises(ConnectionRefusedError, match="manager offline"):
        LLMClient(api_key="legacy", base_url="https://legacy.test/v1",
                  model="legacy", provider_name="ai_processor")


def test_managed_client_uses_explicit_socket_path(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    monkeypatch.setenv("LLM_REQUEST_KIT_SOCKET", "/tmp/atri-manager-test.sock")
    paths = []

    def load(_project, *, socket_path=None):
        paths.append(socket_path)
        return {"ai_processor": {
            "api_key": "key", "base_url": "https://managed.test/v1", "model": "model"
        }}

    monkeypatch.setattr(manager_bridge, "load_project_config", load)
    monkeypatch.setattr(manager_bridge, "load_project_routes", lambda project, *, socket_path=None: {})
    client = LLMClient(api_key="legacy", base_url="https://legacy.test/v1",
                       model="legacy", provider_name="ai_processor")
    assert client.model == "model"
    assert paths == [Path("/tmp/atri-manager-test.sock")]


def test_managed_roles_resolve_text_vision_order_and_image_generation(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    providers = {
        name: {"api_key": f"{name}-key", "base_url": "https://managed.test/v1",
               "model": f"{name}-model"}
        for name in ("chat_main", "vision_backup", "draw_main")
    }
    routes = {"text": ["chat_main"], "vision": ["vision_backup", "chat_main"],
              "image_generation": ["draw_main"]}
    monkeypatch.setattr(manager_bridge, "load_project_config", lambda project: providers)
    monkeypatch.setattr(manager_bridge, "load_project_routes", lambda project: routes)

    text = LLMClient(api_key="legacy", base_url="https://legacy.test/v1",
                     model="legacy", provider_name="ai_processor")
    assert (text.managed_provider_name, text.model) == ("chat_main", "chat_main-model")

    image = ImageUnderstander(api_key="", base_url="", model="")
    assert [runtime.provider_name for runtime in image._provider_runtimes] == [
        "vision_backup", "chat_main"]
    assert [runtime.client.model for runtime in image._provider_runtimes] == [
        "vision_backup-model", "chat_main-model"]
    assert [runtime.client.managed_provider_name for runtime in image._provider_runtimes] == [
        "vision_backup", "chat_main"]

    generation = manager_bridge.image_generation_settings()
    assert generation["_manager_provider_id"] == "draw_main"
    assert generation["model"] == "draw_main-model"


def test_unbound_text_role_fails_closed_without_falling_back_to_legacy_name(monkeypatch):
    monkeypatch.setenv("LLM_REQUEST_KIT_MANAGER", "1")
    monkeypatch.setattr(manager_bridge, "load_project_config", lambda project: {
        "ai_processor": {"api_key": "legacy", "base_url": "https://legacy.test/v1", "model": "old"}
    })
    monkeypatch.setattr(manager_bridge, "load_project_routes", lambda project: {"text": []})
    with pytest.raises(RuntimeError, match="text 用途尚未绑定"):
        manager_bridge.provider_settings("ai_processor")
