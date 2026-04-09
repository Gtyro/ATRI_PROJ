from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional


_DATE_TOKEN_RE = re.compile(r"(20\d{6})")


@dataclass(frozen=True)
class DailyImageFetchResult:
    image_bytes: bytes
    content_type: str
    source_url: str = ""
    last_modified: str = ""


@dataclass(frozen=True)
class DailyImageSuccessRecord:
    date_key: str
    sha256: str
    source_url: str = ""
    last_modified: str = ""


@dataclass(frozen=True)
class DailyImageInspection:
    accepted: bool
    reason: str
    expected_date: str
    source_url_date: Optional[str]
    last_modified_date: Optional[str]
    content_sha256: str
    last_success_date: Optional[str] = None


def normalize_date_key(date_key: str) -> str:
    return str(date_key).strip().replace("-", "")


def extract_date_token(text: str) -> Optional[str]:
    if not text:
        return None
    match = _DATE_TOKEN_RE.search(text)
    return match.group(1) if match else None


def _normalize_sha256(value: str) -> str:
    return str(value).strip().lower()


def compute_image_sha256(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _extract_last_modified_date_key(last_modified: str) -> Optional[str]:
    if not last_modified:
        return None
    try:
        parsed = parsedate_to_datetime(last_modified)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    return parsed.astimezone(local_tz).strftime("%Y%m%d")


def _previous_date_key(date_key: str) -> Optional[str]:
    try:
        parsed = datetime.strptime(date_key, "%Y%m%d")
    except ValueError:
        return None
    return (parsed - timedelta(days=1)).strftime("%Y%m%d")


def inspect_daily_image(
    result: DailyImageFetchResult,
    *,
    expected_date_key: str,
    last_success_record: Optional[DailyImageSuccessRecord] = None,
) -> DailyImageInspection:
    expected_date = normalize_date_key(expected_date_key)
    source_url_date = extract_date_token(result.source_url)
    last_modified_date = _extract_last_modified_date_key(result.last_modified)
    content_sha256 = compute_image_sha256(result.image_bytes)
    last_success_date = (
        normalize_date_key(last_success_record.date_key) if last_success_record else None
    )
    previous_date = _previous_date_key(expected_date)

    if last_success_record is not None:
        if last_success_date == expected_date:
            return DailyImageInspection(
                accepted=True,
                reason="last_success_same_day",
                expected_date=expected_date,
                source_url_date=source_url_date,
                last_modified_date=last_modified_date,
                content_sha256=content_sha256,
                last_success_date=last_success_date,
            )

        if previous_date is not None and last_success_date == previous_date:
            if _normalize_sha256(last_success_record.sha256) != content_sha256:
                return DailyImageInspection(
                    accepted=True,
                    reason="hash_changed_from_previous_day",
                    expected_date=expected_date,
                    source_url_date=source_url_date,
                    last_modified_date=last_modified_date,
                    content_sha256=content_sha256,
                    last_success_date=last_success_date,
                )
            return DailyImageInspection(
                accepted=False,
                reason="same_hash_as_previous_day",
                expected_date=expected_date,
                source_url_date=source_url_date,
                last_modified_date=last_modified_date,
                content_sha256=content_sha256,
                last_success_date=last_success_date,
            )

    # Cold-start fallback: only use remote timestamps when no useful local success record exists.
    if last_modified_date == expected_date:
        return DailyImageInspection(
            accepted=True,
            reason="last_modified_date",
            expected_date=expected_date,
            source_url_date=source_url_date,
            last_modified_date=last_modified_date,
            content_sha256=content_sha256,
            last_success_date=last_success_date,
        )

    if source_url_date is None and last_modified_date is None:
        return DailyImageInspection(
            accepted=True,
            reason="no_date_signal",
            expected_date=expected_date,
            source_url_date=source_url_date,
            last_modified_date=last_modified_date,
            content_sha256=content_sha256,
            last_success_date=last_success_date,
        )

    failure_reason = "no_fresh_signal"
    if last_success_record is not None and last_success_date not in {expected_date, previous_date}:
        failure_reason = "last_success_not_recent"
    elif last_modified_date and last_modified_date != expected_date:
        failure_reason = "last_modified_date_mismatch"
    elif source_url_date and source_url_date != expected_date:
        failure_reason = "source_url_date_mismatch"

    return DailyImageInspection(
        accepted=False,
        reason=failure_reason,
        expected_date=expected_date,
        source_url_date=source_url_date,
        last_modified_date=last_modified_date,
        content_sha256=content_sha256,
        last_success_date=last_success_date,
    )


def build_success_record(
    result: DailyImageFetchResult,
    *,
    date_key: str,
) -> DailyImageSuccessRecord:
    return DailyImageSuccessRecord(
        date_key=normalize_date_key(date_key),
        sha256=compute_image_sha256(result.image_bytes),
        source_url=result.source_url,
        last_modified=result.last_modified,
    )


def read_success_record(path: Path) -> Optional[DailyImageSuccessRecord]:
    if not path.exists():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    date_key = str(data.get("date_key") or data.get("date") or "").strip()
    sha256 = _normalize_sha256(data.get("sha256") or "")
    if not date_key or not sha256:
        return None

    return DailyImageSuccessRecord(
        date_key=normalize_date_key(date_key),
        sha256=sha256,
        source_url=str(data.get("source_url") or "").strip(),
        last_modified=str(data.get("last_modified") or "").strip(),
    )


def write_success_record(path: Path, record: DailyImageSuccessRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date_key": normalize_date_key(record.date_key),
        "sha256": _normalize_sha256(record.sha256),
        "source_url": record.source_url,
        "last_modified": record.last_modified,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def fetch_with_date_guard(
    fetch_once: Callable[[], Awaitable[DailyImageFetchResult]],
    *,
    expected_date_key: str,
    last_success_record: Optional[DailyImageSuccessRecord] = None,
    max_retries: int = 0,
    retry_delay_seconds: float = 0.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    logger: Optional[logging.Logger] = None,
) -> DailyImageFetchResult:
    expected_date = normalize_date_key(expected_date_key)
    max_retries = max(0, int(max_retries))
    retry_delay_seconds = max(0.0, float(retry_delay_seconds))
    total_attempts = max_retries + 1
    last_inspection: Optional[DailyImageInspection] = None

    for attempt in range(1, total_attempts + 1):
        result = await fetch_once()
        inspection = inspect_daily_image(
            result,
            expected_date_key=expected_date,
            last_success_record=last_success_record,
        )
        last_inspection = inspection

        if inspection.accepted:
            if logger:
                if inspection.reason != "source_url_date":
                    logger.info(
                        "daily60s accepted image via fallback signal: reason=%s expected_date=%s "
                        "source_url_date=%s last_modified_date=%s last_success_date=%s "
                        "sha256=%s source_url=%s",
                        inspection.reason,
                        inspection.expected_date,
                        inspection.source_url_date or "unknown",
                        inspection.last_modified_date or "unknown",
                        inspection.last_success_date or "unknown",
                        inspection.content_sha256[:12],
                        result.source_url,
                    )
            return result

        if attempt >= total_attempts:
            break

        if logger:
            logger.warning(
                "daily60s fetched stale image, prepare retry: expected_date=%s source_url_date=%s "
                "last_modified_date=%s last_success_date=%s reason=%s attempt=%s/%s "
                "retry_in_seconds=%s source_url=%s sha256=%s",
                inspection.expected_date,
                inspection.source_url_date or "unknown",
                inspection.last_modified_date or "unknown",
                inspection.last_success_date or "unknown",
                inspection.reason,
                attempt,
                total_attempts,
                retry_delay_seconds,
                result.source_url,
                inspection.content_sha256[:12],
            )
        if retry_delay_seconds > 0:
            await sleep(retry_delay_seconds)

    if last_inspection is None:
        raise RuntimeError("Daily image freshness check failed: no response")

    raise RuntimeError(
        "Daily image freshness check failed: "
        f"expected {expected_date}, "
        f"source_url_date={last_inspection.source_url_date or 'unknown'}, "
        f"last_modified_date={last_inspection.last_modified_date or 'unknown'}, "
        f"last_success_date={last_inspection.last_success_date or 'unknown'}, "
        f"reason={last_inspection.reason}"
    )
