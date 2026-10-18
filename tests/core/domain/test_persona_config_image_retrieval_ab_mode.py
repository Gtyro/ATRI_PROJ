import pytest

import src.core.domain.runtime_settings as runtime_settings
from src.core.domain.persona_config import ImageGenerationConfig, ImageUnderstandingConfig


def _use_empty_runtime_env(monkeypatch, tmp_path):
    (tmp_path / ".env.prod").write_text("", encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setattr(runtime_settings, "PROJECT_ROOT", tmp_path)


def test_image_understanding_accepts_hybrid_mode():
    cfg = ImageUnderstandingConfig.from_dict({"retrieval_ab_mode": "hybrid"})
    assert cfg.retrieval_ab_mode == "hybrid"


def test_image_understanding_uses_2000_as_default_max_tokens():
    cfg = ImageUnderstandingConfig.from_dict({})
    assert cfg.max_tokens == 2000


def test_image_understanding_uses_auto_as_default_detail():
    cfg = ImageUnderstandingConfig.from_dict({})
    assert cfg.detail == "auto"


def test_image_understanding_supports_multiple_providers():
    cfg = ImageUnderstandingConfig.from_dict(
        {
            "api_key": "primary-key",
            "base_url": "https://primary.example.com/v1",
            "model": "gpt-5.4",
            "providers": [
                {
                    "name": "primary",
                    "api_key": "primary-key",
                    "base_url": "https://primary.example.com/v1",
                    "model": "gpt-5.4",
                },
                {
                    "name": "backup",
                    "api_key": "backup-key",
                    "base_url": "https://backup.example.com/v1",
                    "model": "gpt-5.4-mini",
                },
            ],
        }
    )

    assert cfg.api_key == "primary-key"
    assert cfg.base_url == "https://primary.example.com/v1"
    assert cfg.model == "gpt-5.4"
    assert [provider.name for provider in cfg.providers] == ["primary", "backup"]
    assert cfg.providers[1].model == "gpt-5.4-mini"


def test_image_understanding_allows_blank_provider_api_keys():
    cfg = ImageUnderstandingConfig.from_dict(
        {
            "providers": [
                {
                    "name": "primary",
                    "api_key": "",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-5.4",
                }
            ]
        }
    )

    assert cfg.providers[0].api_key == ""
    assert cfg.base_url == "https://api.openai.com/v1"


def test_image_understanding_env_can_override_full_provider_list(monkeypatch):
    monkeypatch.setenv(
        "IMAGE_UNDERSTANDING_PROVIDERS",
        """
        - name: primary
          api_key: env-primary
          base_url: https://primary.example.com/v1
          model: gpt-5.4
        - name: backup
          api_key: env-backup
          base_url: https://backup.example.com/v1
          model: gpt-5.4-mini
        """,
    )

    cfg = ImageUnderstandingConfig.from_dict({}).apply_env_overrides()

    assert cfg.api_key == "env-primary"
    assert cfg.providers[0].name == "primary"
    assert cfg.providers[1].name == "backup"
    assert cfg.providers[1].api_key == "env-backup"


def test_image_understanding_to_dict_does_not_serialize_provider_secrets():
    cfg = ImageUnderstandingConfig.from_dict(
        {
            "providers": [
                {
                    "name": "primary",
                    "api_key": "primary-key",
                    "base_url": "https://primary.example.com/v1",
                    "model": "gpt-5.4",
                }
            ]
        }
    )

    payload = cfg.to_dict()

    assert "api_key" not in payload
    assert "base_url" not in payload
    assert "model" not in payload
    assert "api_key" not in payload["providers"][0]


def test_image_understanding_loads_named_provider_keys_from_environment(monkeypatch):
    monkeypatch.setenv("IMAGE_UNDERSTANDING_PRIMARY_API_KEY", "primary-env-key")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_BACKUP_API_KEY", "backup-env-key")
    monkeypatch.delenv("IMAGE_UNDERSTANDING_API_KEY", raising=False)

    cfg = ImageUnderstandingConfig.from_dict(
        {
            "providers": [
                {"name": "primary", "api_key": "legacy-primary", "base_url": "https://p.example/v1"},
                {"name": "backup", "api_key": "legacy-backup", "base_url": "https://b.example/v1"},
            ]
        }
    ).apply_env_overrides()

    assert [provider.api_key for provider in cfg.providers] == [
        "primary-env-key",
        "backup-env-key",
    ]
    assert cfg.to_dict()["providers"] == [
        {"name": "primary", "base_url": "https://p.example/v1", "model": "gpt-5.4"},
        {"name": "backup", "base_url": "https://b.example/v1", "model": "gpt-5.4"},
    ]


@pytest.mark.parametrize("mode", ["ab_split", "unknown"])
def test_image_understanding_rejects_unsupported_mode(mode):
    with pytest.raises(ValueError):
        ImageUnderstandingConfig.from_dict({"retrieval_ab_mode": mode})


@pytest.mark.parametrize("detail", ["original", "invalid"])
def test_image_understanding_rejects_unsupported_detail(detail):
    with pytest.raises(ValueError):
        ImageUnderstandingConfig.from_dict({"detail": detail})


def test_image_understanding_rejects_invalid_providers_shape():
    with pytest.raises(ValueError):
        ImageUnderstandingConfig.from_dict({"providers": {"name": "primary"}})


def test_image_generation_uses_yaml_defaults_and_runtime_overrides(monkeypatch, tmp_path):
    _use_empty_runtime_env(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAGE_GENERATION_API_KEY", "generation-key")
    monkeypatch.setenv("IMAGE_GENERATION_MODEL", "provider/image-model")
    monkeypatch.setenv("IMAGE_GENERATION_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("IMAGE_GENERATION_ENDPOINT_PATH", "/images")
    monkeypatch.setenv("IMAGE_GENERATION_REFERENCE_ENDPOINT_PATH", "/images/edits-v2")
    monkeypatch.setenv("IMAGE_GENERATION_REFERENCE_IMAGES", '["data/references/one.png"]')
    monkeypatch.setenv("IMAGE_GENERATION_MAX_RETRIES", "2")

    config = ImageGenerationConfig.from_dict(
        {
            "enabled": True,
            "base_url": "https://yaml.example/v1",
            "model": "yaml-model",
            "timeout_seconds": 120,
        }
    ).apply_env_overrides()

    assert config.enabled is True
    assert config.api_key == "generation-key"
    assert config.base_url == "https://yaml.example/v1"
    assert config.model == "provider/image-model"
    assert config.timeout_seconds == 90
    assert config.endpoint_path == "/images"
    assert config.reference_endpoint_path == "/images/edits-v2"
    assert config.reference_images == ["data/references/one.png"]
    assert config.max_retries == 2
    assert "api_key" not in config.to_dict()


def test_image_generation_can_reuse_image_understanding_key(monkeypatch, tmp_path):
    _use_empty_runtime_env(monkeypatch, tmp_path)
    monkeypatch.delenv("IMAGE_GENERATION_API_KEY", raising=False)
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "openrouter-key")

    config = ImageGenerationConfig.from_dict({}).apply_env_overrides()

    assert config.api_key == "openrouter-key"
