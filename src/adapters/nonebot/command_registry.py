from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import nonebot
from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent, MessageEvent

try:
    from nonebot_plugin_alconna import Alconna, on_alconna
except Exception:  # pragma: no cover - optional dependency
    Alconna = None
    on_alconna = None

from src.core.services.plugin_policy_defaults import get_policy_defaults, get_policy_plugins
from src.core.services.plugin_policy_service import PluginPolicyService
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore

Role = Literal["normal", "admin", "superuser"]
Scope = Literal["any", "group_only", "private_only"]

ROLE_RANK: Dict[Role, int] = {
    "normal": 1,
    "admin": 2,
    "superuser": 3,
}


@dataclass(frozen=True)
class CommandSpec:
    name: str
    role: Role
    plugin: str
    scope: Scope = "any"
    hidden: bool = False
    matcher_type: Literal["command", "alconna"] = "command"
    aliases: List[str] = field(default_factory=list)
    description: Optional[str] = None
    usage: Optional[str] = None
    examples: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommandDisplay:
    name: str
    plugin: str
    enabled: bool
    status: Literal["enabled", "disabled", "contextual"] = "enabled"


@dataclass(frozen=True)
class CommandLookup:
    spec: CommandSpec
    enabled: bool
    permitted: bool
    status: Literal["enabled", "disabled", "contextual"] = "enabled"


@dataclass(frozen=True)
class AutoFeatureSpec:
    name: str
    role: Role
    plugin: str
    trigger_type: str
    hidden: bool = False


@dataclass(frozen=True)
class AutoFeatureDisplay:
    name: str
    plugin: str
    enabled: bool
    status: Literal["enabled", "disabled", "contextual"] = "enabled"


class CommandRegistry:
    def __init__(self) -> None:
        self._items: List[CommandSpec] = []
        self._keys: set[Tuple[str, str]] = set()

    def add(self, spec: CommandSpec) -> None:
        key = (spec.plugin, spec.name)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(spec)

    def list(self) -> List[CommandSpec]:
        return list(self._items)


class AutoFeatureRegistry:
    def __init__(self) -> None:
        self._items: List[AutoFeatureSpec] = []
        self._keys: set[Tuple[str, str]] = set()

    def add(self, spec: AutoFeatureSpec) -> None:
        key = (spec.plugin, spec.name)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(spec)

    def list(self) -> List[AutoFeatureSpec]:
        return list(self._items)


registry = CommandRegistry()
auto_feature_registry = AutoFeatureRegistry()

_policy_service: Optional[PluginPolicyService] = None


def _get_policy_service() -> PluginPolicyService:
    global _policy_service
    if _policy_service is None:
        _policy_service = PluginPolicyService(TortoisePluginPolicyStore())
    return _policy_service


def _infer_plugin_name() -> str:
    for frame in inspect.stack():
        module_name = frame.frame.f_globals.get("__name__", "")
        if module_name.startswith("plugins."):
            return module_name.split(".", 2)[1]
        filename = frame.filename.replace("\\", "/")
        marker = "/plugins/"
        if marker in filename:
            tail = filename.split(marker, 1)[1]
            return tail.split("/", 1)[0]
    return "unknown"


def register_command(
    name: str,
    *,
    role: Role = "normal",
    aliases: Optional[Iterable[str]] = None,
    plugin: Optional[str] = None,
    scope: Scope = "any",
    hidden: bool = False,
    description: Optional[str] = None,
    usage: Optional[str] = None,
    examples: Optional[Iterable[str]] = None,
    **matcher_kwargs,
):
    matcher = on_command(name, aliases=set(aliases or []), **matcher_kwargs)
    registry.add(
        CommandSpec(
            name=name,
            role=role,
            aliases=list(aliases or []),
            plugin=plugin or _infer_plugin_name(),
            scope=scope,
            hidden=hidden,
            matcher_type="command",
            description=description,
            usage=usage,
            examples=list(examples or []),
        )
    )
    return matcher


def register_alconna(
    name: str,
    *,
    role: Role = "normal",
    aliases: Optional[Iterable[str]] = None,
    plugin: Optional[str] = None,
    scope: Scope = "any",
    hidden: bool = False,
    description: Optional[str] = None,
    usage: Optional[str] = None,
    examples: Optional[Iterable[str]] = None,
    alconna_args: Optional[Iterable[object]] = None,
    alconna_kwargs: Optional[Dict[str, object]] = None,
    **matcher_kwargs,
):
    if on_alconna is None or Alconna is None:
        raise RuntimeError("nonebot_plugin_alconna is not available")
    alconna = Alconna(name, *(alconna_args or ()), **(alconna_kwargs or {}))
    matcher = on_alconna(alconna, aliases=set(aliases or []), **matcher_kwargs)
    registry.add(
        CommandSpec(
            name=name,
            role=role,
            aliases=list(aliases or []),
            plugin=plugin or _infer_plugin_name(),
            scope=scope,
            hidden=hidden,
            matcher_type="alconna",
            description=description,
            usage=usage,
            examples=list(examples or []),
        )
    )
    return matcher


def register_auto_feature(
    name: str,
    *,
    role: Role = "normal",
    plugin: Optional[str] = None,
    trigger_type: str = "message",
    hidden: bool = False,
) -> None:
    auto_feature_registry.add(
        AutoFeatureSpec(
            name=name,
            role=role,
            plugin=plugin or _infer_plugin_name(),
            trigger_type=trigger_type,
            hidden=hidden,
        )
    )


def get_viewer_role(event: Event) -> Role:
    try:
        user_id = str(event.get_user_id())
    except Exception:
        user_id = ""
    superusers = get_driver().config.superusers or set()
    if user_id and user_id in {str(value) for value in superusers}:
        return "superuser"
    if isinstance(event, GroupMessageEvent):
        role = getattr(getattr(event, "sender", None), "role", None)
        if role in {"admin", "owner"}:
            return "admin"
    return "normal"


def _match_scope(scope: Scope, *, gid: Optional[str]) -> bool:
    if scope == "group_only":
        return bool(gid)
    if scope == "private_only":
        return not gid
    return True


def _get_group_id(event: Event) -> Optional[str]:
    if isinstance(event, GroupMessageEvent):
        gid = getattr(event, "group_id", None)
        return str(gid) if gid is not None else None
    return None


async def _is_plugin_enabled(
    plugin: str,
    gid: Optional[str],
    *,
    policy_plugins: Optional[set[str]] = None,
) -> bool:
    policy_plugins = policy_plugins or set(get_policy_plugins(include_hidden=True))
    if plugin not in policy_plugins:
        return True

    defaults = get_policy_defaults(plugin)
    if not gid:
        return bool(defaults.enabled)

    try:
        policy = await _get_policy_service().get_policy(gid=gid, plugin_name=plugin)
        return bool(policy.enabled)
    except Exception as exc:
        logging.debug("Failed to load policy for plugin %s: %s", plugin, exc)
        return bool(defaults.enabled)


async def _resolve_plugin_status(
    plugin: str,
    gid: Optional[str],
    *,
    viewer_role: Role,
    required_role: Role,
    policy_plugins: set[str],
) -> Tuple[bool, Literal["enabled", "disabled", "contextual"]]:
    if plugin not in policy_plugins:
        return True, "enabled"

    # In private contexts, management commands/features for manageable plugins
    # are determined by the target group rather than the current chat itself.
    if not gid and viewer_role == "superuser" and required_role in {"admin", "superuser"}:
        return True, "contextual"

    enabled = await _is_plugin_enabled(
        plugin,
        gid,
        policy_plugins=policy_plugins,
    )
    return enabled, ("enabled" if enabled else "disabled")


async def list_commands_for_event(
    event: MessageEvent,
    *,
    include_hidden: bool = False,
) -> List[CommandDisplay]:
    viewer_role = get_viewer_role(event)
    viewer_rank = ROLE_RANK[viewer_role]
    gid = _get_group_id(event)

    plugin_enabled_cache: Dict[str, bool] = {}
    results: List[CommandDisplay] = []

    policy_plugins = set(get_policy_plugins())

    for spec in registry.list():
        if spec.hidden and not include_hidden:
            continue
        if ROLE_RANK.get(spec.role, 0) > viewer_rank:
            continue
        if not _match_scope(spec.scope, gid=gid):
            continue

        if spec.plugin not in plugin_enabled_cache:
            enabled, _ = await _resolve_plugin_status(
                spec.plugin,
                gid,
                viewer_role=viewer_role,
                required_role=spec.role,
                policy_plugins=policy_plugins,
            )
            plugin_enabled_cache[spec.plugin] = enabled
        enabled = plugin_enabled_cache[spec.plugin]

        if enabled or viewer_role == "superuser":
            results.append(
                CommandDisplay(
                    name=spec.name,
                    plugin=spec.plugin,
                    enabled=enabled,
                    status="enabled" if enabled else "disabled",
                )
            )
    return results


async def list_commands_for_role(
    event: MessageEvent,
    target_role: Role,
    *,
    include_hidden: bool = False,
) -> List[CommandDisplay]:
    gid = _get_group_id(event)
    policy_plugins = set(get_policy_plugins())

    plugin_enabled_cache: Dict[str, bool] = {}
    results: List[CommandDisplay] = []

    for spec in registry.list():
        if spec.hidden and not include_hidden:
            continue
        if spec.role != target_role:
            continue
        if not _match_scope(spec.scope, gid=gid):
            continue

        if spec.plugin not in plugin_enabled_cache:
            enabled, status = await _resolve_plugin_status(
                spec.plugin,
                gid,
                viewer_role=target_role,
                required_role=spec.role,
                policy_plugins=policy_plugins,
            )
            plugin_enabled_cache[spec.plugin] = enabled
        else:
            status = "enabled" if plugin_enabled_cache[spec.plugin] else "disabled"
        enabled = plugin_enabled_cache[spec.plugin]
        if enabled and target_role == "superuser" and not gid and spec.role in {"admin", "superuser"} and spec.plugin in policy_plugins:
            status = "contextual"

        if enabled or target_role == "superuser":
            results.append(
                CommandDisplay(
                    name=spec.name,
                    plugin=spec.plugin,
                    enabled=enabled,
                    status=status,
                )
            )
    return results


def _find_command_spec(name: str) -> Optional[CommandSpec]:
    if not name:
        return None
    for spec in registry.list():
        if spec.name == name:
            return spec
    for spec in registry.list():
        if name in spec.aliases:
            return spec
    return None


async def resolve_command_for_event(
    event: MessageEvent,
    name: str,
    *,
    include_hidden: bool = False,
) -> Optional[CommandLookup]:
    spec = _find_command_spec(name)
    if not spec:
        return None
    viewer_role = get_viewer_role(event)
    if spec.hidden and not include_hidden and viewer_role != "superuser":
        return None
    gid = _get_group_id(event)
    permitted = ROLE_RANK.get(spec.role, 0) <= ROLE_RANK.get(viewer_role, 0)
    policy_plugins = set(get_policy_plugins())

    # In private help for management commands, the current chat context cannot
    # represent the target group's policy state. Surface that as contextual
    # instead of incorrectly marking the command as disabled.
    enabled, status = await _resolve_plugin_status(
        spec.plugin,
        gid,
        viewer_role=viewer_role,
        required_role=spec.role,
        policy_plugins=policy_plugins,
    )
    return CommandLookup(
        spec=spec,
        enabled=enabled,
        permitted=permitted,
        status=status,
    )


async def list_auto_features_for_event(
    event: MessageEvent,
    *,
    include_hidden: bool = False,
) -> List[AutoFeatureDisplay]:
    viewer_role = get_viewer_role(event)
    viewer_rank = ROLE_RANK[viewer_role]
    gid = _get_group_id(event)

    plugin_enabled_cache: Dict[str, bool] = {}
    results: List[AutoFeatureDisplay] = []

    policy_plugins = set(get_policy_plugins())

    for spec in auto_feature_registry.list():
        if spec.hidden and not include_hidden:
            continue
        if ROLE_RANK.get(spec.role, 0) > viewer_rank:
            continue

        if spec.plugin not in plugin_enabled_cache:
            enabled, _ = await _resolve_plugin_status(
                spec.plugin,
                gid,
                viewer_role=viewer_role,
                required_role=spec.role,
                policy_plugins=policy_plugins,
            )
            plugin_enabled_cache[spec.plugin] = enabled
        enabled = plugin_enabled_cache[spec.plugin]

        if enabled or viewer_role == "superuser":
            results.append(
                AutoFeatureDisplay(
                    name=spec.name,
                    plugin=spec.plugin,
                    enabled=enabled,
                    status="enabled" if enabled else "disabled",
                )
            )
    return results


async def list_auto_features_for_role(
    event: MessageEvent,
    target_role: Role,
    *,
    include_hidden: bool = False,
) -> List[AutoFeatureDisplay]:
    gid = _get_group_id(event)
    policy_plugins = set(get_policy_plugins())

    plugin_enabled_cache: Dict[str, bool] = {}
    results: List[AutoFeatureDisplay] = []

    for spec in auto_feature_registry.list():
        if spec.hidden and not include_hidden:
            continue
        if spec.role != target_role:
            continue

        if spec.plugin not in plugin_enabled_cache:
            enabled, status = await _resolve_plugin_status(
                spec.plugin,
                gid,
                viewer_role=target_role,
                required_role=spec.role,
                policy_plugins=policy_plugins,
            )
            plugin_enabled_cache[spec.plugin] = enabled
        else:
            status = "enabled" if plugin_enabled_cache[spec.plugin] else "disabled"
        enabled = plugin_enabled_cache[spec.plugin]
        if enabled and target_role == "superuser" and not gid and spec.role in {"admin", "superuser"} and spec.plugin in policy_plugins:
            status = "contextual"

        if enabled or target_role == "superuser":
            results.append(
                AutoFeatureDisplay(
                    name=spec.name,
                    plugin=spec.plugin,
                    enabled=enabled,
                    status=status,
                )
            )
    return results


def get_plugin_metadata(plugin: str):
    plugin_obj = nonebot.get_plugin(plugin)
    if not plugin_obj and not plugin.startswith("plugins."):
        plugin_obj = nonebot.get_plugin(f"plugins.{plugin}")
    return getattr(plugin_obj, "metadata", None) if plugin_obj else None


def get_plugin_display_name(plugin: str) -> str:
    meta = get_plugin_metadata(plugin)
    name = getattr(meta, "name", None)
    if isinstance(name, str) and name:
        return name
    return plugin
