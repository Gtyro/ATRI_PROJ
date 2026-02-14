from __future__ import annotations

import asyncio
import logging
import threading
import traceback
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Deque, List, Optional, Union


@dataclass(frozen=True)
class LoggingConfig:
    log_dir: Union[str, Path] = "logs"
    log_level: int = logging.INFO
    log_file_name: str = "%Y-%m-%d_%H-%M.log"
    file_format: str = (
        "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    )
    datefmt: str = "%Y-%m-%d %H:%M:%S"
    webui_enabled: bool = True
    webui_buffer_size: int = 200


@dataclass(frozen=True)
class LogEvent:
    timestamp: float
    level: str
    level_no: int
    logger: str
    message: str
    file: str
    line: int
    function: str
    process: int
    thread: int
    thread_name: str
    exception: Optional[str]
    text: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "level_no": self.level_no,
            "logger": self.logger,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "function": self.function,
            "process": self.process,
            "thread": self.thread,
            "thread_name": self.thread_name,
            "exception": self.exception,
            "text": self.text,
        }


_initialized = False
_buffer: Optional[Deque[LogEvent]] = None
_buffer_lock = threading.Lock()
_webui_enabled = False
_buffer_maxlen = 0
_subscriber_queue_size = 0
_subscribers: List[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []
_subscribers_lock = threading.Lock()
_bridge_logger: Optional[logging.Logger] = None
_thread_local = threading.local()
_exc_formatter = logging.Formatter()


class BufferHandler(logging.Handler):
    def __init__(
        self,
        buffer_ref: Deque[LogEvent],
        buffer_lock: threading.Lock,
        subscribers: List[tuple[asyncio.Queue, asyncio.AbstractEventLoop]],
        subscribers_lock: threading.Lock,
        formatter: logging.Formatter,
    ) -> None:
        super().__init__()
        self._buffer = buffer_ref
        self._buffer_lock = buffer_lock
        self._subscribers = subscribers
        self._subscribers_lock = subscribers_lock
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
        except Exception:
            text = record.getMessage()
        event = _record_to_event(record, text)
        with self._buffer_lock:
            self._buffer.append(event)
        _publish_event(event, self._subscribers, self._subscribers_lock)


class LoguruConsoleHandler(logging.Handler):
    def __init__(self, loguru_logger) -> None:
        super().__init__()
        self._logger = loguru_logger.bind(_from_logging_bridge=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level_name = self._logger.level(record.levelname).name
        except Exception:
            level_name = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame:
            filename = frame.f_code.co_filename
            if filename in (logging.__file__, __file__):
                frame = frame.f_back
                depth += 1
                continue
            break

        self._logger.opt(depth=depth, exception=record.exc_info).log(
            level_name, record.getMessage()
        )


def setup_logging(config: LoggingConfig) -> None:
    global _initialized
    global _buffer
    global _webui_enabled
    global _buffer_maxlen
    global _subscriber_queue_size
    global _bridge_logger

    if _initialized:
        return

    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    filename = datetime.now().strftime(config.log_file_name)
    file_path = Path(filename)
    if not file_path.is_absolute():
        file_path = log_dir / file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    root_logger.setLevel(config.log_level)

    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(config.log_level)
    file_formatter = logging.Formatter(config.file_format, datefmt=config.datefmt)
    file_handler.setFormatter(file_formatter)

    loguru_logger = _try_import_loguru_logger()

    root_handlers: List[logging.Handler] = [file_handler]
    bridge_handlers: List[logging.Handler] = [file_handler]

    if loguru_logger is not None:
        loguru_console = LoguruConsoleHandler(loguru_logger)
        loguru_console.setLevel(config.log_level)
        root_handlers.append(loguru_console)

    if config.webui_enabled:
        _buffer_maxlen = max(1, int(config.webui_buffer_size))
        _subscriber_queue_size = _buffer_maxlen
        _buffer = deque(maxlen=_buffer_maxlen)
        _webui_enabled = True
        if loguru_logger is None:
            buffer_handler = BufferHandler(
                _buffer,
                _buffer_lock,
                _subscribers,
                _subscribers_lock,
                file_formatter,
            )
            buffer_handler.setLevel(config.log_level)
            root_handlers.append(buffer_handler)
            bridge_handlers.append(buffer_handler)
    else:
        _buffer = None
        _webui_enabled = False
        _buffer_maxlen = 0
        _subscriber_queue_size = 0

    for handler in root_handlers:
        root_logger.addHandler(handler)

    _bridge_logger = logging.getLogger("loguru.bridge")
    _bridge_logger.setLevel(config.log_level)
    _bridge_logger.propagate = False
    for handler in bridge_handlers:
        _bridge_logger.addHandler(handler)

    _configure_loguru_sinks(_bridge_logger, loguru_logger, config.webui_enabled)
    _initialized = True


def get_recent_logs(limit: int = 200) -> List[LogEvent]:
    if not _webui_enabled or _buffer is None:
        return []
    if limit <= 0:
        return []
    with _buffer_lock:
        items = list(_buffer)
    if limit < len(items):
        items = items[-limit:]
    return items


async def subscribe_logs() -> AsyncIterator[LogEvent]:
    if not _webui_enabled or _buffer is None:
        if False:
            yield LogEvent(0, "", 0, "", "", "", 0, "", 0, 0, "", None, "")
        return

    queue_size = _subscriber_queue_size or _buffer_maxlen or 200
    queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
    loop = asyncio.get_running_loop()
    token = (queue, loop)

    with _subscribers_lock:
        _subscribers.append(token)

    try:
        while True:
            event = await queue.get()
            yield event
    finally:
        with _subscribers_lock:
            if token in _subscribers:
                _subscribers.remove(token)


def _record_to_event(record: logging.LogRecord, text: str) -> LogEvent:
    exc_text = None
    if record.exc_info:
        exc_text = _exc_formatter.formatException(record.exc_info)
    elif record.exc_text:
        exc_text = record.exc_text

    return LogEvent(
        timestamp=record.created,
        level=record.levelname,
        level_no=record.levelno,
        logger=record.name,
        message=record.getMessage(),
        file=record.filename,
        line=record.lineno,
        function=record.funcName,
        process=record.process,
        thread=record.thread,
        thread_name=record.threadName,
        exception=exc_text,
        text=text,
    )


def _publish_event(
    event: LogEvent,
    subscribers: List[tuple[asyncio.Queue, asyncio.AbstractEventLoop]],
    subscribers_lock: threading.Lock,
) -> None:
    with subscribers_lock:
        current = list(subscribers)

    stale: List[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []
    for queue, loop in current:
        if loop.is_closed():
            stale.append((queue, loop))
            continue
        try:
            loop.call_soon_threadsafe(_enqueue_event, queue, event)
        except RuntimeError:
            stale.append((queue, loop))

    if stale:
        with subscribers_lock:
            for item in stale:
                if item in subscribers:
                    subscribers.remove(item)


def _enqueue_event(queue: asyncio.Queue, event: LogEvent) -> None:
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def _try_import_loguru_logger():
    try:
        from loguru import logger as loguru_logger
    except Exception:
        return None
    return loguru_logger


def _loguru_record_to_event(record: dict, text: str) -> LogEvent:
    level = record.get("level")
    level_no = getattr(level, "no", logging.INFO)
    level_name = getattr(level, "name", logging.getLevelName(level_no))

    exc_text = None
    exc = record.get("exception")
    if exc:
        exc_text = "".join(
            traceback.format_exception(exc.type, exc.value, exc.traceback)
        )

    time_value = record.get("time")
    timestamp = time_value.timestamp() if time_value else 0.0

    file_ref = record.get("file")
    file_name = file_ref.name if file_ref else ""

    process_ref = record.get("process")
    process_id = process_ref.id if process_ref else 0

    thread_ref = record.get("thread")
    thread_id = thread_ref.id if thread_ref else 0
    thread_name = thread_ref.name if thread_ref else ""

    return LogEvent(
        timestamp=timestamp,
        level=level_name,
        level_no=level_no,
        logger=record.get("name", "loguru"),
        message=record.get("message", ""),
        file=file_name,
        line=record.get("line", 0),
        function=record.get("function", ""),
        process=process_id,
        thread=thread_id,
        thread_name=thread_name,
        exception=exc_text,
        text=text,
    )


def _configure_loguru_sinks(
    bridge_logger: logging.Logger,
    loguru_logger,
    buffer_enabled: bool,
) -> None:
    if loguru_logger is None:
        return

    def bridge_sink(message) -> None:
        if getattr(_thread_local, "in_sink", False):
            return
        record = message.record
        if record.get("extra", {}).get("_from_logging_bridge"):
            return

        _thread_local.in_sink = True
        try:
            level = record.get("level")
            level_no = getattr(level, "no", logging.INFO)
            level_name = getattr(level, "name", logging.getLevelName(level_no))
            if logging.getLevelName(level_no) != level_name:
                logging.addLevelName(level_no, level_name)
            if not bridge_logger.isEnabledFor(level_no):
                return

            exc_info = None
            exc = record.get("exception")
            if exc:
                exc_info = (exc.type, exc.value, exc.traceback)

            log_record = logging.LogRecord(
                name=record.get("name", "loguru"),
                level=level_no,
                pathname=record["file"].path,
                lineno=record["line"],
                msg=record["message"],
                args=(),
                exc_info=exc_info,
                func=record.get("function"),
            )
            timestamp = record["time"].timestamp()
            log_record.created = timestamp
            log_record.msecs = (timestamp - int(timestamp)) * 1000
            try:
                log_record.process = record["process"].id
                log_record.processName = record["process"].name
            except Exception:
                pass
            try:
                log_record.thread = record["thread"].id
                log_record.threadName = record["thread"].name
            except Exception:
                pass

            setattr(log_record, "_from_loguru", True)
            bridge_logger.handle(log_record)
        finally:
            _thread_local.in_sink = False

    loguru_logger.add(bridge_sink, colorize=False)

    if not buffer_enabled or _buffer is None:
        return

    def buffer_sink(message) -> None:
        if getattr(_thread_local, "in_buffer_sink", False):
            return
        record = message.record
        _thread_local.in_buffer_sink = True
        try:
            text = str(message)
            event = _loguru_record_to_event(record, text)
            with _buffer_lock:
                _buffer.append(event)
            _publish_event(event, _subscribers, _subscribers_lock)
        finally:
            _thread_local.in_buffer_sink = False

    loguru_logger.add(buffer_sink, colorize=False)
