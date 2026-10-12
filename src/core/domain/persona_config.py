"""Persona 统一配置定义与加载入口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .runtime_settings import get_runtime_setting

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
    value = get_runtime_setting(env_key)
    if value is None:
        return default
    return value.strip()


def _parse_env_int(env_key: str, default: int) -> int:
    value = get_runtime_setting(env_key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{env_key} 必须是整数") from exc


def _parse_env_float(env_key: str, default: float) -> float:
    value = get_runtime_setting(env_key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{env_key} 必须是数字") from exc


@dataclass
class ImageUnderstandingProviderConfig:
    name: str = ""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4"

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]] = None,
        *,
        default_name: str = "",
        default_api_key: str = "",
        default_base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-5.4",
        source: str = "image_understanding.providers",
    ) -> "ImageUnderstandingProviderConfig":
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"{source} 必须是字典")
        return cls(
            name=str(data.get("name", default_name) or "").strip(),
            api_key=str(data.get("api_key", default_api_key) or "").strip(),
            base_url=str(data.get("base_url", default_base_url) or "").strip(),
            model=str(data.get("model", default_model) or "").strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "model": self.model,
        }


@dataclass
class ImageUnderstandingConfig:
    enabled: bool = True
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4"
    timeout_seconds: float = 60.0
    http_timeout_seconds: float = 30.0
    max_tokens: int = 2000
    detail: str = "auto"
    max_images_per_round: int = 5
    analyze_window_size: int = 20
    cache_enabled: bool = True
    retrieval_ab_mode: str = "tool_only"
    providers: List[ImageUnderstandingProviderConfig] = field(default_factory=list)

    @staticmethod
    def _normalize_retrieval_ab_mode(mode_value: Any, *, source: str) -> str:
        mode = str(mode_value or "tool_only").strip().lower() or "tool_only"
        if mode not in {"tool_only", "hybrid"}:
            raise ValueError(f"{source} 仅支持 tool_only 或 hybrid")
        return mode

    @staticmethod
    def _normalize_detail(detail_value: Any, *, source: str) -> str:
        detail = str(detail_value or "auto").strip().lower() or "auto"
        if detail not in {"auto", "high", "low"}:
            raise ValueError(f"{source} 仅支持 auto、high 或 low")
        return detail

    @classmethod
    def _normalize_providers(
        cls,
        raw_providers: Any,
        *,
        default_api_key: str,
        default_base_url: str,
        default_model: str,
        source: str,
    ) -> List[ImageUnderstandingProviderConfig]:
        if raw_providers is None:
            if not (default_api_key or default_base_url or default_model):
                return []
            return [
                ImageUnderstandingProviderConfig(
                    name="primary",
                    api_key=default_api_key,
                    base_url=default_base_url,
                    model=default_model,
                )
            ]
        if not isinstance(raw_providers, list):
            raise ValueError(f"{source} 必须是数组")
        providers: List[ImageUnderstandingProviderConfig] = []
        for index, item in enumerate(raw_providers):
            provider = ImageUnderstandingProviderConfig.from_dict(
                item,
                default_name=f"provider_{index + 1}",
                default_api_key=default_api_key,
                default_base_url=default_base_url,
                default_model=default_model,
                source=f"{source}[{index}]",
            )
            if not (provider.base_url and provider.model):
                raise ValueError(f"{source}[{index}] 缺少 base_url/model")
            providers.append(provider)
        return providers

    @staticmethod
    def _parse_env_provider_list(env_key: str, default: List[ImageUnderstandingProviderConfig]) -> List[ImageUnderstandingProviderConfig]:
        raw_value = get_runtime_setting(env_key)
        if raw_value is None:
            return list(default)
        try:
            parsed = yaml.safe_load(raw_value)
        except Exception as exc:
            raise ValueError(f"{env_key} 必须是有效的 YAML/JSON 数组") from exc
        return ImageUnderstandingConfig._normalize_providers(
            parsed,
            default_api_key="",
            default_base_url="https://api.openai.com/v1",
            default_model="gpt-5.4",
            source=env_key,
        )

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
        detail = cls._normalize_detail(
            data.get("detail", "auto"),
            source="image_understanding.detail",
        )
        default_api_key = str(data.get("api_key", "")).strip()
        default_base_url = str(data.get("base_url", "https://api.openai.com/v1")).strip()
        default_model = str(data.get("model", "gpt-5.4")).strip()
        providers = cls._normalize_providers(
            data.get("providers"),
            default_api_key=default_api_key,
            default_base_url=default_base_url,
            default_model=default_model,
            source="image_understanding.providers",
        )
        primary = providers[0] if providers else ImageUnderstandingProviderConfig(
            name="primary",
            api_key=default_api_key,
            base_url=default_base_url,
            model=default_model,
        )

        max_images_per_round = max(1, int(data.get("max_images_per_round", 5)))
        analyze_window_size = max(1, int(data.get("analyze_window_size", 20)))

        return cls(
            enabled=_to_bool(data.get("enabled"), default=True),
            api_key=primary.api_key,
            base_url=primary.base_url,
            model=primary.model,
            timeout_seconds=float(data.get("timeout_seconds", 60.0)),
            http_timeout_seconds=float(data.get("http_timeout_seconds", 30.0)),
            max_tokens=int(data.get("max_tokens", 2000)),
            detail=detail,
            max_images_per_round=max_images_per_round,
            analyze_window_size=analyze_window_size,
            cache_enabled=_to_bool(data.get("cache_enabled"), default=True),
            retrieval_ab_mode=mode,
            providers=providers,
        )

    def apply_env_overrides(self) -> "ImageUnderstandingConfig":
        mode = self._normalize_retrieval_ab_mode(
            _env_or_default(
                "IMAGE_UNDERSTANDING_RETRIEVAL_AB_MODE",
                self.retrieval_ab_mode,
            ),
            source="IMAGE_UNDERSTANDING_RETRIEVAL_AB_MODE",
        )
        detail = self._normalize_detail(
            _env_or_default("IMAGE_UNDERSTANDING_DETAIL", self.detail),
            source="IMAGE_UNDERSTANDING_DETAIL",
        )

        max_images_per_round = max(
            1,
            _parse_env_int("IMAGE_UNDERSTANDING_MAX_IMAGES_PER_ROUND", self.max_images_per_round),
        )
        analyze_window_size = max(
            1,
            _parse_env_int("IMAGE_UNDERSTANDING_ANALYZE_WINDOW_SIZE", self.analyze_window_size),
        )
        providers = self._parse_env_provider_list(
            "IMAGE_UNDERSTANDING_PROVIDERS",
            self.providers,
        )
        if get_runtime_setting("IMAGE_UNDERSTANDING_PROVIDERS") is None:
            if not providers and (self.base_url or self.model):
                providers = [
                    ImageUnderstandingProviderConfig(
                        name="primary",
                        base_url=self.base_url,
                        model=self.model,
                    )
                ]
            secured_providers = []
            for index, provider in enumerate(providers):
                suffix = "".join(
                    char if char.isalnum() else "_"
                    for char in (provider.name or f"provider_{index + 1}").upper()
                ).strip("_")
                setting_name = f"IMAGE_UNDERSTANDING_{suffix}_API_KEY"
                configured_key = get_runtime_setting(setting_name)
                if configured_key is None and index == 0:
                    configured_key = get_runtime_setting("IMAGE_UNDERSTANDING_API_KEY", "")
                configured_key = str(configured_key or "").strip()
                if provider.api_key and not configured_key:
                    logging.warning(
                        "Image-understanding API key remains in persona YAML; move it to %s",
                        setting_name,
                    )
                secured_providers.append(replace(provider, api_key=configured_key))
            providers = secured_providers

            primary = providers[0] if providers else ImageUnderstandingProviderConfig(
                name="primary",
                base_url=self.base_url,
                model=self.model,
            )
            primary = replace(
                primary,
                base_url=_env_or_default("IMAGE_UNDERSTANDING_BASE_URL", primary.base_url),
                model=_env_or_default("IMAGE_UNDERSTANDING_MODEL", primary.model),
            )
            if providers:
                providers[0] = primary
            elif primary.base_url or primary.model:
                providers = [primary]
        primary = providers[0] if providers else ImageUnderstandingProviderConfig(
            name="primary",
            api_key=_env_or_default("IMAGE_UNDERSTANDING_API_KEY", ""),
            base_url=_env_or_default("IMAGE_UNDERSTANDING_BASE_URL", self.base_url),
            model=_env_or_default("IMAGE_UNDERSTANDING_MODEL", self.model),
        )

        return replace(
            self,
            enabled=_to_bool(
                get_runtime_setting("IMAGE_UNDERSTANDING_ENABLED"),
                default=self.enabled,
            ),
            api_key=primary.api_key,
            base_url=primary.base_url,
            model=primary.model,
            timeout_seconds=_parse_env_float("IMAGE_UNDERSTANDING_TIMEOUT_SECONDS", self.timeout_seconds),
            http_timeout_seconds=_parse_env_float(
                "IMAGE_UNDERSTANDING_HTTP_TIMEOUT_SECONDS",
                self.http_timeout_seconds,
            ),
            max_tokens=_parse_env_int("IMAGE_UNDERSTANDING_MAX_TOKENS", self.max_tokens),
            detail=detail,
            max_images_per_round=max_images_per_round,
            analyze_window_size=analyze_window_size,
            cache_enabled=_to_bool(
                get_runtime_setting("IMAGE_UNDERSTANDING_CACHE_ENABLED"),
                default=self.cache_enabled,
            ),
            retrieval_ab_mode=mode,
            providers=providers,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "timeout_seconds": self.timeout_seconds,
            "http_timeout_seconds": self.http_timeout_seconds,
            "max_tokens": self.max_tokens,
            "detail": self.detail,
            "max_images_per_round": self.max_images_per_round,
            "analyze_window_size": self.analyze_window_size,
            "cache_enabled": self.cache_enabled,
            "retrieval_ab_mode": self.retrieval_ab_mode,
            "providers": [provider.to_dict() for provider in self.providers],
        }


@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str
    liveness_check_timeout: Optional[float] = 30.0

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> "Neo4jConfig":
        if not isinstance(data, dict):
            raise ValueError("neo4j_config 必须是字典")

        liveness_check_timeout = data.get("liveness_check_timeout", 30.0)

        return cls(
            uri=str(_require_key(data, "uri", "neo4j_config.uri")),
            user=str(_require_key(data, "user", "neo4j_config.user")),
            password=str(data.get("password", "")),
            liveness_check_timeout=liveness_check_timeout,
        )

    def apply_env_overrides(self) -> "Neo4jConfig":
        return replace(
            self,
            uri=_env_or_default("NEO4J_URI", self.uri),
            user=_env_or_default("NEO4J_USER", self.user),
            password=_env_or_default("NEO4J_PASSWORD", ""),
            liveness_check_timeout=get_runtime_setting(
                "NEO4J_LIVENESS_CHECK_TIMEOUT",
                self.liveness_check_timeout,
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "user": self.user,
            "liveness_check_timeout": self.liveness_check_timeout,
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
            password=str(data.get("password", "")),
            database=str(_require_key(data, "database", "postgres_config.database")),
        )

    def apply_env_overrides(self) -> "PostgresConfig":
        return replace(
            self,
            host=_env_or_default("POSTGRES_HOST", self.host),
            port=int(_env_or_default("POSTGRES_PORT", str(self.port))),
            user=_env_or_default("POSTGRES_USER", self.user),
            password=_env_or_default("POSTGRES_PASSWORD", ""),
            database=_env_or_default("POSTGRES_DB", self.database),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
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
            api_key=str(data.get("api_key", "")),
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
        if str(get_runtime_setting("USE_POSTGRES", "")).lower() == "true":
            use_postgres = True
            if postgres_config is None:
                raise ValueError("启用 USE_POSTGRES 时需要提供 postgres_config")
            postgres_config = postgres_config.apply_env_overrides()
        elif postgres_config:
            postgres_config = postgres_config.apply_env_overrides()

        api_key = _env_or_default("OPENAI_API_KEY", "")
        if self.api_key and not api_key:
            logging.warning("OPENAI_API_KEY is unset; move the LLM key from persona YAML into .env.dev/.env.prod")

        return replace(
            self,
            api_key=api_key,
            base_url=_env_or_default("OPENAI_BASE_URL", self.base_url),
            model=_env_or_default("OPENAI_MODEL", self.model),
            db_path=_env_or_default("DB_PATH", self.db_path),
            db_url=_env_or_default("DATABASE_URL", self.db_url),
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
