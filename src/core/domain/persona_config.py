"""Persona 统一配置定义与加载入口。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional
import os

import yaml


DEFAULT_CONFIG_PATH = "data/persona/persona.yaml"


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并字典（patch 覆盖 base）。"""
    merged: Dict[str, Any] = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _require_key(data: Dict[str, Any], key: str, path: Optional[str] = None) -> Any:
    if key not in data:
        raise ValueError(f"配置缺少必填项: {path or key}")
    return data[key]


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "y"}:
            return True
        if lowered in {"0", "false", "no", "off", "n"}:
            return False
    return default


def _env_or_default(env_key: str, default: str) -> str:
    value = os.environ.get(env_key)
    if value is None:
        return default
    return value.strip()


def _parse_env_int(env_key: str, default: int) -> int:
    value = os.environ.get(env_key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{env_key} 必须是整数") from exc


def _parse_env_float(env_key: str, default: float) -> float:
    value = os.environ.get(env_key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{env_key} 必须是数字") from exc


@dataclass
class ImageUnderstandingConfig:
    enabled: bool = True
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "google/gemini-3-pro-preview"
    timeout_seconds: float = 60.0
    http_timeout_seconds: float = 30.0
    max_tokens: int = 2000
    max_images_per_round: int = 5
    analyze_window_size: int = 20
    cache_enabled: bool = True
    retrieval_ab_mode: str = "tool_only"

    @staticmethod
    def _normalize_retrieval_ab_mode(mode_value: Any, *, source: str) -> str:
        mode = str(mode_value or "tool_only").strip().lower() or "tool_only"
        if mode not in {"tool_only", "hybrid"}:
            raise ValueError(f"{source} 仅支持 tool_only 或 hybrid")
        return mode

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "ImageUnderstandingConfig":
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("image_understanding 必须是字典")

        mode = cls._normalize_retrieval_ab_mode(
            data.get("retrieval_ab_mode", "tool_only"),
            source="image_understanding.retrieval_ab_mode",
        )

        max_images_per_round = max(1, int(data.get("max_images_per_round", 5)))
        analyze_window_size = max(1, int(data.get("analyze_window_size", 20)))

        return cls(
            enabled=_to_bool(data.get("enabled"), default=True),
            api_key=str(data.get("api_key", "")).strip(),
            base_url=str(data.get("base_url", "https://openrouter.ai/api/v1")).strip(),
            model=str(data.get("model", "google/gemini-3-pro-preview")).strip(),
            timeout_seconds=float(data.get("timeout_seconds", 60.0)),
            http_timeout_seconds=float(data.get("http_timeout_seconds", 30.0)),
            max_tokens=int(data.get("max_tokens", 2000)),
            max_images_per_round=max_images_per_round,
            analyze_window_size=analyze_window_size,
            cache_enabled=_to_bool(data.get("cache_enabled"), default=True),
            retrieval_ab_mode=mode,
        )

    def apply_env_overrides(self) -> "ImageUnderstandingConfig":
        mode = self._normalize_retrieval_ab_mode(
            _env_or_default(
                "IMAGE_UNDERSTANDING_RETRIEVAL_AB_MODE",
                self.retrieval_ab_mode,
            ),
            source="IMAGE_UNDERSTANDING_RETRIEVAL_AB_MODE",
        )

        max_images_per_round = max(
            1,
            _parse_env_int("IMAGE_UNDERSTANDING_MAX_IMAGES_PER_ROUND", self.max_images_per_round),
        )
        analyze_window_size = max(
            1,
            _parse_env_int("IMAGE_UNDERSTANDING_ANALYZE_WINDOW_SIZE", self.analyze_window_size),
        )

        return replace(
            self,
            enabled=_to_bool(
                os.environ.get("IMAGE_UNDERSTANDING_ENABLED"),
                default=self.enabled,
            ),
            api_key=_env_or_default("IMAGE_UNDERSTANDING_API_KEY", self.api_key),
            base_url=_env_or_default("IMAGE_UNDERSTANDING_BASE_URL", self.base_url),
            model=_env_or_default("IMAGE_UNDERSTANDING_MODEL", self.model),
            timeout_seconds=_parse_env_float("IMAGE_UNDERSTANDING_TIMEOUT_SECONDS", self.timeout_seconds),
            http_timeout_seconds=_parse_env_float(
                "IMAGE_UNDERSTANDING_HTTP_TIMEOUT_SECONDS",
                self.http_timeout_seconds,
            ),
            max_tokens=_parse_env_int("IMAGE_UNDERSTANDING_MAX_TOKENS", self.max_tokens),
            max_images_per_round=max_images_per_round,
            analyze_window_size=analyze_window_size,
            cache_enabled=_to_bool(
                os.environ.get("IMAGE_UNDERSTANDING_CACHE_ENABLED"),
                default=self.cache_enabled,
            ),
            retrieval_ab_mode=mode,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "http_timeout_seconds": self.http_timeout_seconds,
            "max_tokens": self.max_tokens,
            "max_images_per_round": self.max_images_per_round,
            "analyze_window_size": self.analyze_window_size,
            "cache_enabled": self.cache_enabled,
            "retrieval_ab_mode": self.retrieval_ab_mode,
        }


@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "Neo4jConfig":
        if not isinstance(data, dict):
            raise ValueError("neo4j_config 必须是字典")
        return cls(
            uri=str(_require_key(data, "uri", "neo4j_config.uri")),
            user=str(_require_key(data, "user", "neo4j_config.user")),
            password=str(_require_key(data, "password", "neo4j_config.password")),
        )

    def apply_env_overrides(self) -> "Neo4jConfig":
        return replace(
            self,
            uri=os.environ.get("NEO4J_URI", self.uri),
            user=os.environ.get("NEO4J_USER", self.user),
            password=os.environ.get("NEO4J_PASSWORD", self.password),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "user": self.user,
            "password": self.password,
        }


@dataclass
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "PostgresConfig":
        if not isinstance(data, dict):
            raise ValueError("postgres_config 必须是字典")
        return cls(
            host=str(_require_key(data, "host", "postgres_config.host")),
            port=int(_require_key(data, "port", "postgres_config.port")),
            user=str(_require_key(data, "user", "postgres_config.user")),
            password=str(_require_key(data, "password", "postgres_config.password")),
            database=str(_require_key(data, "database", "postgres_config.database")),
        )

    def apply_env_overrides(self) -> "PostgresConfig":
        return replace(
            self,
            host=os.environ.get("POSTGRES_HOST", self.host),
            port=int(os.environ.get("POSTGRES_PORT", self.port)),
            user=os.environ.get("POSTGRES_USER", self.user),
            password=os.environ.get("POSTGRES_PASSWORD", self.password),
            database=os.environ.get("POSTGRES_DB", self.database),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }


@dataclass
class PersonaConfig:
    api_key: str
    base_url: str
    model: str
    use_postgres: bool
    db_path: str
    db_url: str
    batch_interval: int
    node_decay_rate: float
    queue_history_size: int
    default_response_rate: float
    max_nodes_per_conv: int
    max_memories_per_conv: int
    next_decay_interval: int
    neo4j_config: Neo4jConfig
    llm_flags_defaults: Dict[str, bool]
    image_understanding: ImageUnderstandingConfig = field(default_factory=ImageUnderstandingConfig)
    postgres_config: Optional[PostgresConfig] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]] = None,
        *,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> "PersonaConfig":
        if data is None:
            data = {}
        if defaults:
            if not isinstance(defaults, dict):
                raise ValueError("defaults 必须是字典")
            data = _deep_merge(defaults, data)
        if not isinstance(data, dict):
            raise ValueError("Persona 配置必须是字典")
        if not data:
            raise ValueError("Persona 配置为空，请检查配置文件")
        extras = {k: v for k, v in data.items() if k not in {
            "api_key",
            "base_url",
            "model",
            "use_postgres",
            "db_path",
            "db_url",
            "batch_interval",
            "node_decay_rate",
            "queue_history_size",
            "default_response_rate",
            "max_nodes_per_conv",
            "max_memories_per_conv",
            "next_decay_interval",
            "neo4j_config",
            "postgres_config",
            "llm_flags_defaults",
            "image_understanding",
        }}
        postgres_config = None
        if "postgres_config" in data and data.get("postgres_config") is not None:
            postgres_config = PostgresConfig.from_dict(data.get("postgres_config"))
        image_understanding = ImageUnderstandingConfig.from_dict(data.get("image_understanding"))
        llm_flags_defaults = data.get("llm_flags_defaults")
        if not isinstance(llm_flags_defaults, dict):
            raise ValueError("llm_flags_defaults 必须是字典")
        llm_flags_defaults = {str(k): bool(v) for k, v in llm_flags_defaults.items()}
        return cls(
            api_key=str(_require_key(data, "api_key")),
            base_url=str(_require_key(data, "base_url")),
            model=str(_require_key(data, "model")),
            use_postgres=bool(_require_key(data, "use_postgres")),
            db_path=str(_require_key(data, "db_path")),
            db_url=str(_require_key(data, "db_url")),
            batch_interval=int(_require_key(data, "batch_interval")),
            node_decay_rate=float(_require_key(data, "node_decay_rate")),
            queue_history_size=int(_require_key(data, "queue_history_size")),
            default_response_rate=float(_require_key(data, "default_response_rate")),
            max_nodes_per_conv=int(_require_key(data, "max_nodes_per_conv")),
            max_memories_per_conv=int(_require_key(data, "max_memories_per_conv")),
            next_decay_interval=int(_require_key(data, "next_decay_interval")),
            neo4j_config=Neo4jConfig.from_dict(_require_key(data, "neo4j_config")),
            llm_flags_defaults=llm_flags_defaults,
            image_understanding=image_understanding,
            postgres_config=postgres_config,
            extras=extras,
        )

    @classmethod
    def load(cls, config_path: str = DEFAULT_CONFIG_PATH, create_if_missing: bool = True) -> "PersonaConfig":
        path = Path(config_path)
        if not path.exists():
            message = f"配置文件不存在: {path}"
            raise FileNotFoundError(message)
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            raise ValueError("Persona 配置格式错误，必须是字典结构")
        config = cls.from_dict(raw).apply_env_overrides()
        return config

    def apply_env_overrides(self) -> "PersonaConfig":
        use_postgres = self.use_postgres
        postgres_config = self.postgres_config
        if os.environ.get("USE_POSTGRES", "").lower() == "true":
            use_postgres = True
            if postgres_config is None:
                raise ValueError("启用 USE_POSTGRES 时需要提供 postgres_config")
            postgres_config = postgres_config.apply_env_overrides()
        elif postgres_config:
            postgres_config = postgres_config.apply_env_overrides()

        return replace(
            self,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            db_path=self.db_path,
            db_url=self.db_url,
            batch_interval=self.batch_interval,
            node_decay_rate=self.node_decay_rate,
            queue_history_size=self.queue_history_size,
            default_response_rate=self.default_response_rate,
            max_nodes_per_conv=self.max_nodes_per_conv,
            max_memories_per_conv=self.max_memories_per_conv,
            next_decay_interval=self.next_decay_interval,
            use_postgres=use_postgres,
            neo4j_config=self.neo4j_config.apply_env_overrides(),
            postgres_config=postgres_config,
            llm_flags_defaults=self.llm_flags_defaults,
            image_understanding=self.image_understanding.apply_env_overrides(),
            extras=self.extras,
        )

    def with_db_path(self, db_path: str) -> "PersonaConfig":
        db_url = self.db_url
        if isinstance(db_url, str) and db_url.startswith("sqlite://"):
            db_url = f"sqlite://{db_path}"
        return replace(self, db_path=db_path, db_url=db_url)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "use_postgres": self.use_postgres,
            "db_path": self.db_path,
            "db_url": self.db_url,
            "batch_interval": self.batch_interval,
            "node_decay_rate": self.node_decay_rate,
            "queue_history_size": self.queue_history_size,
            "default_response_rate": self.default_response_rate,
            "max_nodes_per_conv": self.max_nodes_per_conv,
            "max_memories_per_conv": self.max_memories_per_conv,
            "next_decay_interval": self.next_decay_interval,
            "neo4j_config": self.neo4j_config.to_dict(),
            "llm_flags_defaults": self.llm_flags_defaults,
            "image_understanding": self.image_understanding.to_dict(),
        }
        if self.postgres_config:
            data["postgres_config"] = self.postgres_config.to_dict()
        data.update(self.extras)
        return data
