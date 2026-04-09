import asyncio
import json

from plugins.daily60s_fetch_policy import (
    DailyImageFetchResult,
    DailyImageSuccessRecord,
    build_success_record,
    compute_image_sha256,
    extract_date_token,
    fetch_with_date_guard,
    inspect_daily_image,
    read_success_record,
    write_success_record,
)


def test_extract_date_token_from_source_url():
    assert (
        extract_date_token("https://file.alapi.cn/60s/202603311774920363.png")
        == "20260331"
    )


def test_extract_date_token_returns_none_when_missing():
    assert extract_date_token("https://example.com/daily.png") is None


def test_fetch_with_date_guard_accepts_response_without_date_token():
    async def _fetch_once():
        return DailyImageFetchResult(
            image_bytes=b"image",
            content_type="image/png",
            source_url="https://example.com/daily.png",
        )

    result = asyncio.run(
        fetch_with_date_guard(
            _fetch_once,
            expected_date_key="2026-03-31",
        )
    )

    assert result.source_url == "https://example.com/daily.png"


def test_inspect_daily_image_accepts_when_last_modified_matches_today():
    inspection = inspect_daily_image(
        DailyImageFetchResult(
            image_bytes=b"image",
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202603311774999203.png",
            last_modified="Tue, 31 Mar 2026 23:20:04 GMT",
        ),
        expected_date_key="2026-04-01",
    )

    assert inspection.accepted is True
    assert inspection.reason == "last_modified_date"


def test_inspect_daily_image_accepts_when_hash_changes_from_previous_day():
    inspection = inspect_daily_image(
        DailyImageFetchResult(
            image_bytes=b"today-image",
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202603311774999203.png",
        ),
        expected_date_key="2026-04-01",
        last_success_record=DailyImageSuccessRecord(
            date_key="2026-03-31",
            sha256=compute_image_sha256(b"yesterday-image"),
        ),
    )

    assert inspection.accepted is True
    assert inspection.reason == "hash_changed_from_previous_day"


def test_inspect_daily_image_rejects_same_hash_as_previous_day():
    content = b"same-image"
    inspection = inspect_daily_image(
        DailyImageFetchResult(
            image_bytes=content,
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202603311774999203.png",
        ),
        expected_date_key="2026-04-01",
        last_success_record=DailyImageSuccessRecord(
            date_key="2026-03-31",
            sha256=compute_image_sha256(content),
        ),
    )

    assert inspection.accepted is False
    assert inspection.reason == "same_hash_as_previous_day"


def test_fetch_with_date_guard_retries_until_today_image_arrives():
    attempts = []
    sleeps = []

    async def _fetch_once():
        attempts.append("fetch")
        if len(attempts) == 1:
            return DailyImageFetchResult(
                image_bytes=b"old",
                content_type="image/png",
                source_url="https://file.alapi.cn/60s/202603301774812601.png",
                last_modified="Sun, 30 Mar 2026 00:20:04 GMT",
            )
        return DailyImageFetchResult(
            image_bytes=b"new",
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202603311774920363.png",
            last_modified="Mon, 30 Mar 2026 16:00:00 GMT",
        )

    async def _sleep(seconds: float):
        sleeps.append(seconds)

    result = asyncio.run(
        fetch_with_date_guard(
            _fetch_once,
            expected_date_key="2026-03-31",
            max_retries=2,
            retry_delay_seconds=300,
            sleep=_sleep,
        )
    )

    assert result.image_bytes == b"new"
    assert len(attempts) == 2
    assert sleeps == [300]


def test_inspect_daily_image_rejects_when_only_source_url_date_matches_today():
    inspection = inspect_daily_image(
        DailyImageFetchResult(
            image_bytes=b"image",
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202604011234567890.png",
        ),
        expected_date_key="2026-04-01",
    )

    assert inspection.accepted is False
    assert inspection.reason == "no_fresh_signal"


def test_fetch_with_date_guard_raises_after_retry_budget_exhausted():
    async def _fetch_once():
        return DailyImageFetchResult(
            image_bytes=b"old",
            content_type="image/png",
            source_url="https://file.alapi.cn/60s/202603301774812601.png",
        )

    try:
        asyncio.run(
            fetch_with_date_guard(
                _fetch_once,
                expected_date_key="2026-03-31",
                max_retries=1,
            )
        )
    except RuntimeError as exc:
        assert "expected 20260331" in str(exc)
        assert "source_url_date=20260330" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for stale daily image")


def test_build_and_persist_success_record(tmp_path):
    path = tmp_path / "daily60s_last_success.json"
    result = DailyImageFetchResult(
        image_bytes=b"image",
        content_type="image/png",
        source_url="https://example.com/today.png",
        last_modified="Tue, 31 Mar 2026 23:20:04 GMT",
    )

    record = build_success_record(result, date_key="2026-04-01")
    write_success_record(path, record)
    loaded = read_success_record(path)

    assert loaded == record
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["date_key"] == "20260401"
    assert payload["sha256"] == compute_image_sha256(b"image")
