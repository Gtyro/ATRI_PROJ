"""事件模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

MESSAGE_RECEIVED = "message.received"


@dataclass(frozen=True)
class Event:
    """通用事件对象。"""

    name: str
    payload: Any
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class MessagePayload:
    """标准化消息载荷。"""

    conv_id: str
    user_id: str
    user_name: str
    content: str
    is_direct: bool
    is_bot: bool
    is_processed: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    raw_event: Optional[Any] = None
