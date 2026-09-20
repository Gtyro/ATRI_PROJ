import asyncio
import json

import httpx

from plugins.itad_giveaways.service import (
    DailyGiveawayState,
    Giveaway,
    build_daily_report,
    fetch_active_giveaways,
    format_giveaway_messages,
    load_state,
    parse_giveaways,
    write_state,
)


def _payload(giveaway_id: int, title: str = "Free Game") -> dict:
    return {
        "id": giveaway_id,
        "title": title,
        "shop": {"id": 35, "name": "GOG"},
        "url": f"https://example.com/giveaway/{giveaway_id}?affiliate=itad",
        "publish": "2026-09-17T09:00:00+08:00",
        "expiry": "2026-09-20T09:00:00+08:00",
        "games": [{"title": title}],
    }


def test_parse_giveaways_keeps_only_valid_unique_items():
    giveaways = parse_giveaways(
        [
            _payload(101, "Alpha"),
            _payload(101, "Duplicate"),
            {"id": "not-an-id", "title": "Invalid", "url": "https://example.com"},
        ]
    )

    assert [giveaway.id for giveaway in giveaways] == [101]
    assert giveaways[0].games == ("Alpha",)


def test_fetch_active_giveaways_uses_itad_header_and_paginates():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        offset = int(request.url.params["offset"])
        if offset == 0:
            payload = [_payload(index) for index in range(1, 51)]
        elif offset == 50:
            payload = [_payload(51)]
        else:
            raise AssertionError(f"unexpected offset: {offset}")
        return httpx.Response(200, json=payload)

    async def run() -> list[Giveaway]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_active_giveaways(
                api_key="test-key",
                api_url="https://api.isthereanydeal.com/giveaways/v1",
                timeout_seconds=15,
                client=client,
            )

    giveaways = asyncio.run(run())

    assert [giveaway.id for giveaway in giveaways] == list(range(1, 52))
    assert len(requests) == 2
    assert requests[0].headers["ITAD-API-Key"] == "test-key"
    assert requests[0].url.params["expired"] == "false"
    assert requests[0].url.params["mature"] == "false"


def test_build_daily_report_compares_against_previous_daily_snapshot():
    previous_state = DailyGiveawayState(
        report_date="2026-09-19",
        snapshot_ids=frozenset({1}),
        todays_giveaways=(Giveaway(1, "First", "GOG", "https://example.com/1", "", None, ("First",)),),
        notification_sent=True,
    )
    giveaways = [
        Giveaway(1, "First", "GOG", "https://example.com/1", "", None, ("First",)),
        Giveaway(2, "Second", "GOG", "https://example.com/2", "", None, ("Second",)),
    ]

    state = build_daily_report(
        giveaways,
        previous_state=previous_state,
        report_date="2026-09-20",
    )

    assert state.snapshot_ids == frozenset({1, 2})
    assert [giveaway.id for giveaway in state.todays_giveaways] == [2]
    assert state.notification_sent is False


def test_build_daily_report_keeps_same_day_result_stable():
    previous_state = DailyGiveawayState(
        report_date="2026-09-20",
        snapshot_ids=frozenset({1, 2}),
        todays_giveaways=(Giveaway(2, "Second", "GOG", "https://example.com/2", "", None, ("Second",)),),
        notification_sent=False,
    )
    later_giveaways = [
        Giveaway(1, "First", "GOG", "https://example.com/1", "", None, ("First",)),
        Giveaway(2, "Second", "GOG", "https://example.com/2", "", None, ("Second",)),
        Giveaway(3, "Third", "GOG", "https://example.com/3", "", None, ("Third",)),
    ]

    state = build_daily_report(
        later_giveaways,
        previous_state=previous_state,
        report_date="2026-09-20",
    )

    assert state == previous_state


def test_state_round_trip_preserves_daily_report(tmp_path):
    state_path = tmp_path / "itad_giveaways_last_result.json"
    state = DailyGiveawayState(
        report_date="2026-09-20",
        snapshot_ids=frozenset({1, 2}),
        todays_giveaways=(Giveaway(2, "Second", "GOG", "https://example.com/2", "", None, ("Second",)),),
        notification_sent=True,
    )

    write_state(state_path, state)
    loaded = load_state(state_path)

    assert loaded == state
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["snapshot_ids"] == [1, 2]
    assert payload["notification_sent"] is True


def test_format_giveaway_messages_keeps_source_url_and_chunks_entries():
    giveaways = [
        Giveaway(
            giveaway_id,
            f"Game {giveaway_id}",
            "GOG",
            f"https://example.com/{giveaway_id}?affiliate=itad",
            "",
            "2026-09-20T09:00:00+08:00",
            (f"Game {giveaway_id}",),
        )
        for giveaway_id in range(1, 4)
    ]

    messages = format_giveaway_messages(giveaways, max_length=200)

    assert len(messages) > 1
    assert "https://example.com/1?affiliate=itad" in "\n".join(messages)
