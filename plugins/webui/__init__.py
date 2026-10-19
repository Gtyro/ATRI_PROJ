import logging
import os
from datetime import datetime, timedelta

from nonebot import require
from nonebot.plugin import PluginMetadata

STANDALONE_WEBUI = os.getenv("ATRI_WEBUI_STANDALONE") == "1"

# 在插件入口点引入数据库依赖，并注册 NoneBot 生命周期钩子。
if not STANDALONE_WEBUI:
    require("db_core")
    from . import backend

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="WebUI管理面板",
    description="提供可视化的方式管理和监控您的数据库",
    usage="启动后访问 http://127.0.0.1:8188/webui",
    type="application",
    homepage="https://github.com/yourusername/nonebot-plugin-webui",
    config=None,
    supported_adapters={"~onebot.v11"},
    extra={
        "policy": {
            "manageable": False,
        }
    }
)

try:
    from nonebot_plugin_apscheduler import scheduler
except Exception:
    scheduler = None

if scheduler is not None and not STANDALONE_WEBUI:
    from .backend.api.audit.cleanup import cleanup_expired_operation_audit_logs
    from .backend.api.core.config import settings

    @scheduler.scheduled_job(
        "cron",
        hour=max(0, min(23, int(settings.AUDIT_LOG_CLEANUP_HOUR))),
        minute=max(0, min(59, int(settings.AUDIT_LOG_CLEANUP_MINUTE))),
        id="webui_operation_audit_retention_cleanup",
    )
    async def _cleanup_operation_audit_logs() -> None:
        retention_days = max(1, int(settings.AUDIT_LOG_RETENTION_DAYS))
        now = datetime.utcnow()
        try:
            deleted_count = await cleanup_expired_operation_audit_logs(
                retention_days=retention_days,
                now=now,
            )
            cutoff = now - timedelta(days=retention_days)
            logging.info(
                "操作审计日志定时清理完成: deleted=%s cutoff=%s",
                deleted_count,
                cutoff.isoformat(),
            )
        except Exception as exc:
            logging.error("操作审计日志定时清理异常: %s", exc, exc_info=True)
