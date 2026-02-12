"""事件发布/订阅机制。"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol

from .models import Event

EventHandler = Callable[[Event], Any]


class EventBus(Protocol):
    """事件总线接口。"""

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        ...

    async def publish(self, event: Event) -> None:
        ...


class InMemoryEventBus:
    """简单的内存事件总线实现。"""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers.setdefault(event_name, [])
        handlers.append(handler)

    async def publish(self, event: Event) -> None:
        handlers = list(self._subscribers.get(event.name, []))
        if not handlers:
            return
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logging.error(
                    "事件处理失败: %s, event=%s, handler=%s",
                    exc,
                    event.name,
                    getattr(handler, "__name__", repr(handler)),
                    exc_info=True,
                )


_default_event_bus: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    """获取默认事件总线实例。"""

    global _default_event_bus
    if _default_event_bus is None:
        _default_event_bus = InMemoryEventBus()
    return _default_event_bus
