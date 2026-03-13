from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional


LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
    r"(?P<level>[A-Z]+) \| (?P<logger>[^|]+) \| (?P<source>[^|]+) \| "
    r"(?P<message>.*)$"
)
LOG_LINE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_TIME_FORMAT = "%Y-%m-%d_%H-%M"
DEFAULT_STARTUP_WINDOW_SECONDS = 180
MAX_SAMPLE_MESSAGES = 3


@dataclass(frozen=True)
class LogIssueSummary:
    errors: int = 0
    warnings: int = 0
    sample_messages: tuple[str, ...] = ()
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    status: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RestartLogDiagnostics:
    current_log: str | None
    previous_log: str | None
    startup_window_seconds: int
    startup_summary: LogIssueSummary
    previous_log_summary: LogIssueSummary

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["startup_summary"] = self.startup_summary.to_dict()
        payload["previous_log_summary"] = self.previous_log_summary.to_dict()
        return payload


def collect_restart_log_diagnostics(
    log_dir: str | Path = "logs",
    startup_reference: str | datetime | None = None,
    status_file: str | Path | None = None,
    startup_window_seconds: int = DEFAULT_STARTUP_WINDOW_SECONDS,
) -> dict[str, Any]:
    startup_dt = _coerce_datetime(startup_reference)
    if startup_dt is None and status_file is not None:
        startup_dt = _load_last_startup(status_file)

    log_entries = _list_log_entries(Path(log_dir))
    current_index = _select_current_log_index(log_entries, startup_dt)
    current_log = log_entries[current_index][0] if current_index is not None else None
    previous_log = (
        log_entries[current_index + 1][0]
        if current_index is not None and current_index + 1 < len(log_entries)
        else None
    )

    startup_summary = (
        _summarize_log(current_log, startup_window_seconds=startup_window_seconds)
        if current_log is not None
        else LogIssueSummary(status="missing")
    )
    previous_summary = (
        _summarize_log(previous_log)
        if previous_log is not None
        else LogIssueSummary(status="missing")
    )

    diagnostics = RestartLogDiagnostics(
        current_log=_display_path(current_log),
        previous_log=_display_path(previous_log),
        startup_window_seconds=startup_window_seconds,
        startup_summary=startup_summary,
        previous_log_summary=previous_summary,
    )
    return diagnostics.to_dict()


def summarize_issue_status(
    errors: int,
    warnings: int,
    status: str | None = None,
) -> str:
    if status == "missing":
        return "⚪ 未找到可用日志"
    if status == "unreadable":
        return "⚪ 日志无法读取"
    if status == "empty":
        return "⚪ 日志为空"
    if errors > 0:
        return f"❌ 检测到 {errors} 个 ERROR，{warnings} 个 WARNING"
    if warnings > 0:
        return f"⚠️ 检测到 {errors} 个 ERROR，{warnings} 个 WARNING"
    return "✅ 未检测到 ERROR/WARNING"


def format_diagnostics_text(diagnostics: dict[str, Any]) -> str:
    startup = diagnostics.get("startup_summary", {})
    previous = diagnostics.get("previous_log_summary", {})
    lines = [
        "启动日志诊断",
        "------------------------",
        f"本次启动日志: {diagnostics.get('current_log') or '未找到'}",
        (
            f"本次启动窗口: 前 {diagnostics.get('startup_window_seconds', DEFAULT_STARTUP_WINDOW_SECONDS)} 秒"
        ),
        summarize_issue_status(
            int(startup.get("errors", 0)),
            int(startup.get("warnings", 0)),
            str(startup.get("status", "")),
        ),
    ]

    samples = tuple(startup.get("sample_messages", ()) or ())
    if samples:
        lines.append("启动期问题样例:")
        for message in samples:
            lines.append(f"- {message}")

    lines.extend(
        [
            "",
            "上一份日志摘要",
            "------------------------",
            f"上一份日志: {diagnostics.get('previous_log') or '未找到'}",
            f"ERROR: {previous.get('errors', 0)}",
            f"WARNING: {previous.get('warnings', 0)}",
        ]
    )
    return "\n".join(lines)


def _display_path(path: Optional[Path]) -> str | None:
    if path is None:
        return None
    try:
        return path.as_posix()
    except Exception:
        return str(path)


def _load_last_startup(status_file: str | Path) -> datetime | None:
    path = Path(status_file)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _coerce_datetime(data.get("last_startup"))


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _list_log_entries(log_dir: Path) -> list[tuple[Path, datetime]]:
    if not log_dir.exists():
        return []

    entries: list[tuple[Path, datetime]] = []
    for path in log_dir.glob("*.log"):
        parsed = _parse_log_file_time(path)
        if parsed is None:
            try:
                parsed = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
        entries.append((path, parsed))
    entries.sort(key=lambda item: item[1], reverse=True)
    return entries


def _parse_log_file_time(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem, LOG_FILE_TIME_FORMAT)
    except ValueError:
        return None


def _select_current_log_index(
    log_entries: list[tuple[Path, datetime]],
    startup_reference: datetime | None,
) -> int | None:
    if not log_entries:
        return None
    if startup_reference is None:
        return 0

    candidates: list[tuple[float, int]] = []
    for index, (_, log_time) in enumerate(log_entries):
        diff_seconds = abs((log_time - startup_reference).total_seconds())
        if diff_seconds <= 15 * 60:
            candidates.append((diff_seconds, index))
    if not candidates:
        return 0
    return min(candidates, key=lambda item: (item[0], item[1]))[1]


def _summarize_log(
    path: Path,
    startup_window_seconds: int | None = None,
) -> LogIssueSummary:
    if not path.exists():
        return LogIssueSummary(status="missing")

    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    window_end: datetime | None = None
    error_count = 0
    warning_count = 0
    sample_messages: list[str] = []
    seen_samples: set[str] = set()

    try:
        lines: Iterable[str] = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return LogIssueSummary(status="unreadable")

    for line in lines:
        parsed = _parse_log_line(line)
        if parsed is None:
            continue

        timestamp, level, logger, message = parsed
        if first_timestamp is None:
            first_timestamp = timestamp
            if startup_window_seconds is not None:
                window_end = timestamp + timedelta(seconds=startup_window_seconds)
        if window_end is not None and timestamp > window_end:
            break

        last_timestamp = timestamp
        if level == "ERROR":
            error_count += 1
            _append_sample(sample_messages, seen_samples, logger, message)
        elif level == "WARNING":
            warning_count += 1
            _append_sample(sample_messages, seen_samples, logger, message)

    if first_timestamp is None:
        return LogIssueSummary(status="empty")

    if error_count > 0:
        status = "error"
    elif warning_count > 0:
        status = "warning"
    else:
        status = "ok"

    return LogIssueSummary(
        errors=error_count,
        warnings=warning_count,
        sample_messages=tuple(sample_messages),
        first_timestamp=first_timestamp.strftime(LOG_LINE_TIME_FORMAT),
        last_timestamp=(
            last_timestamp.strftime(LOG_LINE_TIME_FORMAT) if last_timestamp is not None else None
        ),
        status=status,
    )


def _parse_log_line(line: str) -> tuple[datetime, str, str, str] | None:
    match = LOG_LINE_RE.match(line.strip())
    if match is None:
        return None
    try:
        timestamp = datetime.strptime(match.group("timestamp"), LOG_LINE_TIME_FORMAT)
    except ValueError:
        return None
    return (
        timestamp,
        match.group("level").strip(),
        match.group("logger").strip(),
        match.group("message").strip(),
    )


def _append_sample(
    sample_messages: list[str],
    seen_samples: set[str],
    logger: str,
    message: str,
) -> None:
    if len(sample_messages) >= MAX_SAMPLE_MESSAGES:
        return
    normalized = f"[{logger}] {message}".strip()
    normalized = normalized[:157] + "..." if len(normalized) > 160 else normalized
    if normalized in seen_samples:
        return
    seen_samples.add(normalized)
    sample_messages.append(normalized)
