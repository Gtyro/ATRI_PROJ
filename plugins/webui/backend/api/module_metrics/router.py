from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.services.module_metrics_service import build_default_module_metrics_service

from ..auth.models import User
from ..auth.utils import get_current_active_user

router = APIRouter(
    prefix="/api/module-metrics",
    tags=["module-metrics"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

module_metrics_service = build_default_module_metrics_service()


def _validate_time_range(from_time: Optional[datetime], to_time: Optional[datetime]) -> None:
    normalized_from = from_time if isinstance(from_time, datetime) else None
    normalized_to = to_time if isinstance(to_time, datetime) else None
    if normalized_from is not None and normalized_to is not None and normalized_from > normalized_to:
        raise HTTPException(status_code=400, detail="from 不能大于 to")


def _normalize_module_ids(values: Optional[List[str]]) -> Optional[List[str]]:
    if values is None:
        return None
    if isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    elif isinstance(values, str):
        raw_values = [values]
    else:
        return None
    normalized: List[str] = []
    seen = set()
    for value in raw_values:
        text = str(value or "").strip()
        if not text:
            continue
        for part in text.split(","):
            item = part.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            normalized.append(item)
    return normalized or None


@router.get("/modules")
async def get_module_metric_modules(
    current_user: User = Depends(get_current_active_user),
):
    return {"items": module_metrics_service.list_provider_modules()}


@router.get("/overview")
async def get_module_metric_overview(
    from_time: Optional[datetime] = Query(None, alias="from", description="开始时间"),
    to_time: Optional[datetime] = Query(None, alias="to", description="结束时间"),
    module_id: Optional[List[str]] = Query(None, description="模块ID，可重复传参或逗号分隔"),
    plugin_name: Optional[str] = Query(None, description="插件名"),
    module_name: Optional[str] = Query(None, description="模块名"),
    operation: Optional[str] = Query(None, description="操作名"),
    conv_id: Optional[str] = Query(None, description="会话ID"),
    current_user: User = Depends(get_current_active_user),
):
    _validate_time_range(from_time, to_time)
    try:
        return await module_metrics_service.get_provider_overview(
            module_ids=_normalize_module_ids(module_id),
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"module provider 不存在: {exc.args[0]}") from exc


@router.get("/modules/{module_id}/detail")
async def get_module_metric_module_detail(
    module_id: str,
    from_time: Optional[datetime] = Query(None, alias="from", description="开始时间"),
    to_time: Optional[datetime] = Query(None, alias="to", description="结束时间"),
    plugin_name: Optional[str] = Query(None, description="插件名"),
    module_name: Optional[str] = Query(None, description="模块名"),
    operation: Optional[str] = Query(None, description="操作名"),
    conv_id: Optional[str] = Query(None, description="会话ID"),
    current_user: User = Depends(get_current_active_user),
):
    _validate_time_range(from_time, to_time)
    try:
        detail = await module_metrics_service.get_provider_detail(
            module_id,
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
        )
        get_filter_options = getattr(module_metrics_service, "get_provider_filter_options", None)
        if callable(get_filter_options):
            filter_options = await get_filter_options(
                module_id,
                from_time=from_time,
                to_time=to_time,
                plugin_name=plugin_name,
                module_name=module_name,
                operation=operation,
                conv_id=conv_id,
            )
            if isinstance(detail, dict):
                detail.setdefault("filter_options", filter_options)
        return detail
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"module provider 不存在: {exc.args[0]}") from exc


@router.get("/options")
async def get_module_metric_options(
    from_time: Optional[datetime] = Query(None, alias="from", description="开始时间"),
    to_time: Optional[datetime] = Query(None, alias="to", description="结束时间"),
    plugin_name: Optional[str] = Query(None, description="插件名"),
    module_name: Optional[str] = Query(None, description="模块名"),
    operation: Optional[str] = Query(None, description="操作名"),
    conv_id: Optional[str] = Query(None, description="会话ID"),
    current_user: User = Depends(get_current_active_user),
):
    _validate_time_range(from_time, to_time)
    return await module_metrics_service.get_options(
        from_time=from_time,
        to_time=to_time,
        plugin_name=plugin_name,
        module_name=module_name,
        operation=operation,
        conv_id=conv_id,
    )


@router.get("/summary")
async def get_module_metric_summary(
    from_time: Optional[datetime] = Query(None, alias="from", description="开始时间"),
    to_time: Optional[datetime] = Query(None, alias="to", description="结束时间"),
    plugin_name: Optional[str] = Query(None, description="插件名"),
    module_name: Optional[str] = Query(None, description="模块名"),
    operation: Optional[str] = Query(None, description="操作名"),
    conv_id: Optional[str] = Query(None, description="会话ID"),
    interval: str = Query("day", description="聚合粒度: day/hour"),
    current_user: User = Depends(get_current_active_user),
):
    _validate_time_range(from_time, to_time)
    try:
        return await module_metrics_service.get_summary(
            from_time=from_time,
            to_time=to_time,
            plugin_name=plugin_name,
            module_name=module_name,
            operation=operation,
            conv_id=conv_id,
            interval=interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/events")
async def get_module_metric_events(
    from_time: Optional[datetime] = Query(None, alias="from", description="开始时间"),
    to_time: Optional[datetime] = Query(None, alias="to", description="结束时间"),
    plugin_name: Optional[str] = Query(None, description="插件名"),
    module_name: Optional[str] = Query(None, description="模块名"),
    operation: Optional[str] = Query(None, description="操作名"),
    conv_id: Optional[str] = Query(None, description="会话ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, description="每页大小"),
    current_user: User = Depends(get_current_active_user),
):
    _validate_time_range(from_time, to_time)
    return await module_metrics_service.get_events(
        from_time=from_time,
        to_time=to_time,
        plugin_name=plugin_name,
        module_name=module_name,
        operation=operation,
        conv_id=conv_id,
        page=page,
        size=size,
    )
