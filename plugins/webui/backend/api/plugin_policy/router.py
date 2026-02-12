from typing import Any, Dict, List, Optional

import nonebot
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.models import User
from ..auth.utils import get_current_active_user
from ..dashboard.bot_info import get_group_list
from src.core.services.plugin_policy_service import PluginPolicyService
from src.core.services.plugin_policy_defaults import (
    build_defaults_payload,
    build_policy_meta_payload,
    get_ingest_plugins,
    get_policy_plugins,
)
from src.core.services.persona_policy_flags import normalize_persona_policy_config
from src.infra.db.tortoise.plugin_policy_store import TortoisePluginPolicyStore

router = APIRouter(
    prefix="/api/plugin-policy",
    tags=["plugin-policy"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

policy_service = PluginPolicyService(TortoisePluginPolicyStore())


class PolicyUpdate(BaseModel):
    gid: str
    plugin_name: str
    enabled: Optional[bool] = None
    ingest_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    group_name: Optional[str] = None


class BatchPolicyUpdate(BaseModel):
    gid: Optional[str] = None
    plugin_name: Optional[str] = None
    enabled: Optional[bool] = None
    ingest_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


def _merge_config(base: Optional[Dict[str, Any]], patch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in (patch or {}).items():
        merged[key] = value
    return merged


async def _load_groups() -> List[Dict[str, Any]]:
    bots = nonebot.get_bots()
    for bot in bots.values():
        groups = await get_group_list(bot, False)
        normalized = []
        for group in groups:
            gid = str(group.get("group_id") or group.get("gid") or "")
            if not gid:
                continue
            normalized.append(
                {
                    "group_id": gid,
                    "group_name": group.get("group_name") or group.get("name") or gid,
                }
            )
        return normalized
    return []


async def _load_group_map(policies: List[Any]) -> Dict[str, Dict[str, Any]]:
    group_map = {group["group_id"]: group for group in await _load_groups()}

    for policy in policies:
        if policy.gid not in group_map:
            group_map[policy.gid] = {
                "group_id": policy.gid,
                "group_name": policy.group_name or policy.gid,
            }

    return group_map


def _load_visible_plugins() -> List[str]:
    return get_policy_plugins()


@router.get("/matrix")
async def get_policy_matrix(current_user: User = Depends(get_current_active_user)):
    policies = await policy_service.list_policies()
    group_map = await _load_group_map(policies)
    visible_plugins = _load_visible_plugins()

    await policy_service.ensure_policies(list(group_map.values()), visible_plugins)
    policies = await policy_service.list_policies(gids=list(group_map.keys()))
    policies = [policy for policy in policies if policy.plugin_name in visible_plugins]
    ingest_plugins = get_ingest_plugins()
    ingest_plugin = ingest_plugins[0] if ingest_plugins else ""

    return {
        "groups": sorted(group_map.values(), key=lambda item: item["group_id"]),
        "plugins": visible_plugins,
        "policies": [p.to_dict() for p in policies],
        "defaults": build_defaults_payload(visible_plugins),
        "policy_meta": build_policy_meta_payload(visible_plugins),
        "ingest_plugin": ingest_plugin,
    }


@router.post("/policy")
async def update_policy(payload: PolicyUpdate, current_user: User = Depends(get_current_active_user)):
    config = payload.config
    if payload.plugin_name == "persona" and config is not None:
        config = normalize_persona_policy_config(config)
    policy = await policy_service.set_policy(
        gid=payload.gid,
        plugin_name=payload.plugin_name,
        enabled=payload.enabled,
        ingest_enabled=payload.ingest_enabled,
        config=config,
        group_name=payload.group_name,
    )
    return {"policy": policy.to_dict()}


@router.post("/batch")
async def batch_update_policies(payload: BatchPolicyUpdate, current_user: User = Depends(get_current_active_user)):
    if not payload.gid and not payload.plugin_name:
        raise HTTPException(status_code=400, detail="gid 或 plugin_name 不能为空")
    if payload.enabled is None and payload.ingest_enabled is None and payload.config is None:
        raise HTTPException(status_code=400, detail="enabled、ingest_enabled 或 config 不能为空")

    policies = await policy_service.list_policies()
    group_map = await _load_group_map(policies)
    visible_plugins = _load_visible_plugins()

    if payload.gid:
        if payload.config is not None:
            raise HTTPException(status_code=400, detail="config 批量更新仅支持 plugin_name")
        gid = str(payload.gid)
        group = group_map.get(gid, {"group_id": gid, "group_name": gid})
        group_name = group.get("group_name") or gid
        updated = 0
        for plugin_name in visible_plugins:
            await policy_service.set_policy(
                gid=gid,
                plugin_name=plugin_name,
                enabled=payload.enabled,
                ingest_enabled=payload.ingest_enabled,
                group_name=group_name,
            )
            updated += 1
        return {"updated": updated}

    plugin_name = payload.plugin_name or ""
    if plugin_name not in visible_plugins:
        raise HTTPException(status_code=400, detail="插件不可批量管理")

    updated = 0
    for group in group_map.values():
        gid = str(group.get("group_id") or "")
        if not gid:
            continue
        group_name = group.get("group_name") or gid
        if payload.config is not None:
            current = await policy_service.get_policy(
                gid=gid,
                plugin_name=plugin_name,
                group_name=group_name,
            )
            next_config = _merge_config(current.config, payload.config)
            if plugin_name == "persona":
                next_config = normalize_persona_policy_config(next_config)
            await policy_service.set_policy(
                gid=gid,
                plugin_name=plugin_name,
                enabled=payload.enabled,
                ingest_enabled=payload.ingest_enabled,
                config=next_config,
                group_name=group_name,
            )
        else:
            await policy_service.set_policy(
                gid=gid,
                plugin_name=plugin_name,
                enabled=payload.enabled,
                ingest_enabled=payload.ingest_enabled,
                group_name=group_name,
            )
        updated += 1
    return {"updated": updated}
