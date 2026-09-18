from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Set

import httpx


PAGE_SIZE = 50


@dataclass(frozen=True)
class Giveaway:
    id: int
    title: str
    shop_name: str
    url: str
    publish: str
    expiry: str | None
    games: tuple[str, ...]


@dataclass(frozen=True)
class GiveawayState:
    giveaway_ids: frozenset[int]


def _coerce_giveaway(raw: object) -> Giveaway | None:
    if not isinstance(raw, Mapping):
        return None

    giveaway_id = raw.get("id")
    if isinstance(giveaway_id, bool):
        return None
    try:
        normalized_id = int(giveaway_id)
    except (TypeError, ValueError):
        return None
    if normalized_id <= 0:
        return None

    title = raw.get("title")
    url = raw.get("url")
    if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.strip():
        return None

    shop_name = "未知商店"
    shop = raw.get("shop")
    if isinstance(shop, Mapping) and isinstance(shop.get("name"), str):
        shop_name = shop["name"].strip() or shop_name

    games: list[str] = []
    raw_games = raw.get("games")
    if isinstance(raw_games, list):
        for game in raw_games:
            if isinstance(game, Mapping) and isinstance(game.get("title"), str):
                game_title = game["title"].strip()
                if game_title:
                    games.append(game_title)

    expiry = raw.get("expiry")
    return Giveaway(
        id=normalized_id,
        title=title.strip(),
        shop_name=shop_name,
        url=url.strip(),
        publish=str(raw.get("publish") or ""),
        expiry=expiry.strip() if isinstance(expiry, str) and expiry.strip() else None,
        games=tuple(games),
    )


def parse_giveaways(payload: object) -> list[Giveaway]:
    if not isinstance(payload, list):
        raise ValueError("ITAD giveaways response must be a list")

    giveaways: list[Giveaway] = []
    seen_ids: set[int] = set()
    for raw in payload:
        giveaway = _coerce_giveaway(raw)
        if giveaway is None or giveaway.id in seen_ids:
            continue
        giveaways.append(giveaway)
        seen_ids.add(giveaway.id)
    return giveaways


async def _fetch_page(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    api_url: str,
    offset: int,
) -> tuple[list[Giveaway], int]:
    response = await client.get(
        api_url,
        headers={"ITAD-API-Key": api_key},
        params={
            "offset": offset,
            "limit": PAGE_SIZE,
            "mature": "false",
            "expired": "false",
            "sort": "-publish",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("ITAD giveaways response must be a list")
    return parse_giveaways(payload), len(payload)


async def fetch_active_giveaways(
    *,
    api_key: str,
    api_url: str,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> list[Giveaway]:
    if not api_key.strip():
        raise ValueError("ITAD API key is not configured")

    async def fetch_all(active_client: httpx.AsyncClient) -> list[Giveaway]:
        all_giveaways: list[Giveaway] = []
        seen_ids: set[int] = set()
        offset = 0
        while True:
            page, raw_page_size = await _fetch_page(
                active_client,
                api_key=api_key,
                api_url=api_url,
                offset=offset,
            )
            new_page_ids = 0
            for giveaway in page:
                if giveaway.id not in seen_ids:
                    all_giveaways.append(giveaway)
                    seen_ids.add(giveaway.id)
                    new_page_ids += 1
            if raw_page_size < PAGE_SIZE or new_page_ids == 0:
                return all_giveaways
            offset += PAGE_SIZE

    if client is not None:
        return await fetch_all(client)

    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as owned_client:
        return await fetch_all(owned_client)


def select_new_giveaways(
    giveaways: Iterable[Giveaway],
    previous_ids: Set[int] | frozenset[int],
) -> list[Giveaway]:
    return [giveaway for giveaway in giveaways if giveaway.id not in previous_ids]


def load_state(path: Path) -> GiveawayState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return GiveawayState(giveaway_ids=frozenset())
    except (OSError, json.JSONDecodeError):
        return GiveawayState(giveaway_ids=frozenset())

    raw_ids = payload.get("giveaway_ids", []) if isinstance(payload, Mapping) else []
    if not isinstance(raw_ids, list):
        return GiveawayState(giveaway_ids=frozenset())

    normalized_ids: set[int] = set()
    for value in raw_ids:
        if isinstance(value, bool):
            continue
        try:
            giveaway_id = int(value)
        except (TypeError, ValueError):
            continue
        if giveaway_id > 0:
            normalized_ids.add(giveaway_id)
    return GiveawayState(giveaway_ids=frozenset(normalized_ids))


def write_state(path: Path, giveaway_ids: Iterable[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "giveaway_ids": sorted({int(giveaway_id) for giveaway_id in giveaway_ids}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        Path(temporary_name).replace(path)
    except Exception:
        try:
            Path(temporary_name).unlink(missing_ok=True)
        finally:
            raise


def format_giveaway_messages(
    giveaways: Sequence[Giveaway],
    *,
    max_length: int = 3000,
) -> list[str]:
    if max_length < 200:
        raise ValueError("max_length must be at least 200")

    prefix = f"ITAD 限免更新，共 {len(giveaways)} 项：\n"
    messages: list[str] = []
    current = prefix
    for index, giveaway in enumerate(giveaways, start=1):
        games = "、".join(giveaway.games) if giveaway.games else giveaway.title
        expiry = giveaway.expiry or "未提供"
        entry = (
            f"\n{index}. {giveaway.title}\n"
            f"游戏：{games}\n"
            f"商店：{giveaway.shop_name}\n"
            f"截止：{expiry}\n"
            f"链接：{giveaway.url}\n"
        )
        if current != prefix and len(current) + len(entry) > max_length:
            messages.append(current.rstrip())
            current = prefix + entry.lstrip()
        else:
            current += entry
    if current != prefix:
        messages.append(current.rstrip())
    return messages
