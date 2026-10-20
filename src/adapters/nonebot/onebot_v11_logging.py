"""Keep expected OneBot service restarts out of warning logs."""

import sys

from nonebot.adapters.onebot.v11 import adapter as onebot_adapter
from nonebot.exception import WebSocketClosed


_original_log = onebot_adapter.log


def _log_without_restart_warning(level: str, message: str, exception=None) -> None:
    closed = sys.exception()
    if (
        level == "WARNING"
        and message.startswith("WebSocket for Bot ")
        and message.endswith(" closed by peer")
        and isinstance(closed, WebSocketClosed)
        and closed.code == 1012
    ):
        return
    _original_log(level, message, exception)


def install_onebot_v11_restart_log_filter() -> None:
    # The adapter logs from inside its WebSocketClosed handler, where the code
    # remains available through sys.exception().
    onebot_adapter.log = _log_without_restart_warning
