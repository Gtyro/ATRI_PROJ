from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.services.module_metrics_service import ModuleMetricsService

from ..auth.models import User
from ..auth.utils import get_current_active_user

router = APIRouter(
    prefix="/api/module-metrics",
    tags=["module-metrics"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)

module_metrics_service = ModuleMetricsService()


def _validate_time_range(from_time: Optional[datetime], to_time: Optional[datetime]) -> None:
    if from_time is not None and to_time is not None and from_time > to_time:
        raise HTTPException(status_code=400, detail="from 不能大于 to")


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
