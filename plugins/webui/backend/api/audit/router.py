import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..auth.models import User
from ..auth.utils import get_current_active_user
from ..core.config import settings
from ..db.models import OperationAuditLog
from .cleanup import cleanup_expired_operation_audit_logs
from .service import record_operation_audit
from .types import (
    AuditAction,
    AuditTargetType,
    list_known_actions,
    list_known_target_types,
)

router = APIRouter(
    prefix="/api/audit",
    tags=["operation-audit"],
    dependencies=[Depends(get_current_active_user)],
    responses={401: {"description": "未经授权"}},
)


class OperationAuditItem(BaseModel):
    id: int
    username: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    success: bool
    detail: Optional[Any] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class OperationAuditListPayload(BaseModel):
    total: int
    items: List[OperationAuditItem]


class OperationAuditMetaPayload(BaseModel):
    actions: List[str]
    target_types: List[str]
    default_retention_days: int


class OperationAuditCleanupPayload(BaseModel):
    retention_days: int
    deleted: int


def _parse_detail(detail: Optional[str]) -> Optional[Any]:
    if not detail:
        return None
    try:
        return json.loads(detail)
    except Exception:
        return detail


@router.get("/logs", response_model=OperationAuditListPayload)
async def list_operation_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    username: str = Query("", description="按操作者过滤（包含匹配）"),
    action: str = Query("", description="按动作过滤（包含匹配）"),
    target_type: str = Query("", description="按资源类型过滤（精确匹配）"),
    success: Optional[bool] = Query(None, description="按是否成功过滤"),
    current_user: User = Depends(get_current_active_user),
):
    del current_user

    query = OperationAuditLog.all()
    if username:
        query = query.filter(username__contains=username.strip())
    if action:
        query = query.filter(action__contains=action.strip())
    if target_type:
        query = query.filter(target_type=target_type.strip())
    if success is not None:
        query = query.filter(success=success)

    total = await query.count()
    rows = await query.order_by("-created_at").offset(offset).limit(limit)
    items = [
        OperationAuditItem(
            id=row.id,
            username=row.username,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            success=row.success,
            detail=_parse_detail(row.detail),
            request_method=row.request_method,
            request_path=row.request_path,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return OperationAuditListPayload(total=total, items=items)


@router.get("/meta", response_model=OperationAuditMetaPayload)
async def get_operation_audit_meta(
    current_user: User = Depends(get_current_active_user),
):
    del current_user
    return OperationAuditMetaPayload(
        actions=list_known_actions(),
        target_types=list_known_target_types(),
        default_retention_days=max(1, int(settings.AUDIT_LOG_RETENTION_DAYS)),
    )


@router.post("/cleanup", response_model=OperationAuditCleanupPayload)
async def cleanup_operation_audit_logs(
    request: Request,
    retention_days: Optional[int] = Query(
        None,
        ge=1,
        le=3650,
        description="保留天数；为空时使用后端默认配置",
    ),
    current_user: User = Depends(get_current_active_user),
):
    normalized_days = retention_days or max(1, int(settings.AUDIT_LOG_RETENTION_DAYS))
    try:
        deleted = await cleanup_expired_operation_audit_logs(retention_days=normalized_days)
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.AUDIT_LOG_CLEANUP.value,
            target_type=AuditTargetType.AUDIT_LOG.value,
            target_id=f"retention:{normalized_days}d",
            request=request,
            success=True,
            after={"deleted": deleted, "retention_days": normalized_days},
        )
        return OperationAuditCleanupPayload(retention_days=normalized_days, deleted=deleted)
    except Exception as exc:
        await record_operation_audit(
            username=current_user.username,
            action=AuditAction.AUDIT_LOG_CLEANUP.value,
            target_type=AuditTargetType.AUDIT_LOG.value,
            target_id=f"retention:{normalized_days}d",
            request=request,
            success=False,
            error_message=str(exc),
        )
        raise
