import importlib.util
import sys
from pathlib import Path


def _load_config_module(relative_path: str, module_name: str):
    config_path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, config_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_daily60s_key_comes_from_runtime_environment_not_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "daily60s.yaml"
    config_path.write_text("alapi_key: legacy-key\nschedule_time: '08:00'\n", encoding="utf-8")
    monkeypatch.setenv("ALAPI_API_KEY", "runtime-key")

    config_class = _load_config_module("plugins/daily60s/config.py", "daily60s_config_for_test").Daily60sConfig
    config = config_class.load(str(config_path))

    assert config.alapi_key == "runtime-key"
    assert config.schedule_time == "08:00"


def test_itad_key_comes_from_runtime_environment_not_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "itad.yaml"
    config_path.write_text("api_key: legacy-key\ntimezone: UTC\n", encoding="utf-8")
    monkeypatch.setenv("ITAD_API_KEY", "runtime-key")

    config_class = _load_config_module(
        "plugins/itad_giveaways/config.py",
        "itad_config_for_test",
    ).ItadGiveawaysConfig
    config = config_class.load(str(config_path))

    assert config.api_key == "runtime-key"
    assert config.timezone == "UTC"
