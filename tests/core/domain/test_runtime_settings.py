import pytest
from pathlib import Path

import src.core.domain.runtime_settings as runtime_settings
from src.core.domain import PersonaConfig, get_runtime_setting


@pytest.mark.parametrize("filename", [".env.dev", ".env.prod"])
def test_repository_dotenv_is_rejected_before_opening(filename):
    project_root = Path(runtime_settings.__file__).resolve().parents[3]

    with pytest.raises(AssertionError, match="tests must not read repository dotenv files"):
        runtime_settings.dotenv_values(dotenv_path=project_root / filename)


def test_runtime_setting_uses_selected_env_file_then_process_environment(tmp_path, monkeypatch):
    (tmp_path / ".env.dev").write_text("SAMPLE_SECRET=from-dev-file\n", encoding="utf-8")
    (tmp_path / ".env.prod").write_text("SAMPLE_SECRET=from-prod-file\n", encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.delenv("SAMPLE_SECRET", raising=False)

    assert get_runtime_setting("SAMPLE_SECRET", project_root=tmp_path) == "from-dev-file"

    monkeypatch.setenv("SAMPLE_SECRET", "from-process")
    assert get_runtime_setting("SAMPLE_SECRET", project_root=tmp_path) == "from-process"

    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("SAMPLE_SECRET")
    assert get_runtime_setting("SAMPLE_SECRET", project_root=tmp_path) == "from-prod-file"


def test_runtime_setting_rejects_unknown_environment_instead_of_falling_back_to_prod(
    tmp_path,
    monkeypatch,
):
    (tmp_path / ".env.prod").write_text("SAMPLE_SECRET=prod-only\n", encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "typo")
    monkeypatch.delenv("SAMPLE_SECRET", raising=False)

    with pytest.raises(ValueError, match="ENVIRONMENT"):
        get_runtime_setting("SAMPLE_SECRET", project_root=tmp_path)


def test_persona_config_reads_secrets_from_environment_and_never_serializes_them(
    monkeypatch,
    tmp_path,
):
    (tmp_path / ".env.prod").write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime_settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "env-llm-key")
    monkeypatch.setenv("NEO4J_PASSWORD", "env-neo4j-password")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env-postgres-password")
    monkeypatch.setenv("IMAGE_UNDERSTANDING_API_KEY", "env-image-key")

    config = PersonaConfig.from_dict(
        {
            "api_key": "legacy-llm-key",
            "base_url": "https://llm.example/v1",
            "model": "example-model",
            "use_postgres": False,
            "db_path": "data/persona.db",
            "db_url": "sqlite://data/persona.db",
            "batch_interval": 60,
            "node_decay_rate": 0.01,
            "queue_history_size": 10,
            "default_response_rate": 0.2,
            "max_nodes_per_conv": 100,
            "max_memories_per_conv": 50,
            "next_decay_interval": 600,
            "neo4j_config": {
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "legacy-neo4j-password",
            },
            "postgres_config": {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "legacy-postgres-password",
                "database": "persona",
            },
            "llm_flags_defaults": {},
            "image_understanding": {
                "providers": [
                    {
                        "name": "primary",
                        "api_key": "legacy-image-key",
                        "base_url": "https://image.example/v1",
                        "model": "image-model",
                    }
                ]
            },
        }
    ).apply_env_overrides()

    assert config.api_key == "env-llm-key"
    assert config.neo4j_config.password == "env-neo4j-password"
    assert config.postgres_config.password == "env-postgres-password"
    assert config.image_understanding.api_key == "env-image-key"

    serialized = repr(config.to_dict())
    for secret in (
        "env-llm-key",
        "legacy-llm-key",
        "env-neo4j-password",
        "legacy-neo4j-password",
        "env-postgres-password",
        "legacy-postgres-password",
        "env-image-key",
        "legacy-image-key",
    ):
        assert secret not in serialized
