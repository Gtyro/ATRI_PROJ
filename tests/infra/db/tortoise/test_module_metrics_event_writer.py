import asyncio

from src.infra.db.tortoise.module_metrics_event_writer import ModuleMetricEventWriter


class _FakeEventModel:
    def __init__(self):
        self.created = []

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return kwargs


class _FakeModuleModel:
    def __init__(self):
        self.created = []

    async def get_or_create(self, **kwargs):
        self.created.append(kwargs)
        return kwargs, True


def test_module_metric_event_writer_rejects_missing_required_fields():
    event_model = _FakeEventModel()
    module_model = _FakeModuleModel()
    writer = ModuleMetricEventWriter(event_model=event_model, module_model=module_model)

    success = asyncio.run(writer.write_event({"plugin_name": "persona"}))

    assert success is False
    assert event_model.created == []
    assert module_model.created == []


def test_module_metric_event_writer_persists_normalized_event():
    event_model = _FakeEventModel()
    module_model = _FakeModuleModel()
    writer = ModuleMetricEventWriter(event_model=event_model, module_model=module_model)

    success = asyncio.run(
        writer.write_event(
            {
                "plugin_name": " persona ",
                "module_name": " image_understanding ",
                "operation": " image_understanding ",
                "conv_id": " group_1 ",
                "phase": " image_fetch ",
                "resolved_via": " get_image ",
                "success": "true",
                "prompt_tokens": "5",
                "completion_tokens": 7,
                "total_tokens": "12",
                "foo": "bar",
            }
        )
    )

    assert success is True
    assert len(event_model.created) == 1
    payload = event_model.created[0]
    assert payload["module_id"] == "persona.image_understanding"
    assert payload["plugin_name"] == "persona"
    assert payload["module_name"] == "image_understanding"
    assert payload["operation"] == "image_understanding"
    assert payload["conv_id"] == "group_1"
    assert payload["phase"] == "image_fetch"
    assert payload["resolved_via"] == "get_image"
    assert payload["success"] is True
    assert payload["prompt_tokens"] == 5
    assert payload["completion_tokens"] == 7
    assert payload["total_tokens"] == 12
    assert payload["extra"] == {"foo": "bar"}
    assert len(module_model.created) == 1
    assert module_model.created[0]["module_id"] == "persona.image_understanding"
