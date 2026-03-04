#!/usr/bin/env python3
import argparse
import gc
import sqlite3
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class LegacyRunResult:
    elapsed_ms: float
    peak_mb: float
    loaded_rows: int


@dataclass
class OptimizedRunResult:
    elapsed_ms: float
    peak_mb: float
    grouped_rows: int


def _resolve_db_path(db_url: Optional[str]) -> Path:
    if db_url is None:
        from src.core.domain import PersonaConfig

        db_url = PersonaConfig.load().db_url
    if not db_url.startswith("sqlite://"):
        raise ValueError(f"Only sqlite db_url is supported by this benchmark: {db_url}")
    return Path(db_url[len("sqlite://") :]).resolve()


def _parse_created_at(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif value is None:
        return None
    else:
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _legacy_collect_timestamps(conn: sqlite3.Connection, start: datetime) -> Tuple[List[datetime], int]:
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT created_at FROM basic_message WHERE created_at >= ?",
        (start_str,),
    ).fetchall()
    timestamps: List[datetime] = []
    for row in rows:
        dt = _parse_created_at(row[0] if isinstance(row, tuple) else row["created_at"])
        if dt is None:
            continue
        timestamps.append(dt)
    return timestamps, len(rows)


def _legacy_daily_once(conn: sqlite3.Connection, now: datetime, days: int) -> Tuple[List[Tuple[str, int]], int]:
    total_days = max(7, min(days, 365))
    end_date = now.date()
    start_date = end_date - timedelta(days=total_days - 1)
    start_time = datetime.combine(start_date, dtime.min)
    buckets: Dict[str, int] = {}
    for idx in range(total_days):
        day = start_date + timedelta(days=idx)
        buckets[day.isoformat()] = 0

    timestamps, loaded_rows = _legacy_collect_timestamps(conn, start_time)
    for created_at in timestamps:
        day_key = created_at.date().isoformat()
        if day_key in buckets:
            buckets[day_key] += 1
    return [(key, buckets[key]) for key in sorted(buckets.keys())], loaded_rows


def _legacy_hourly_once(conn: sqlite3.Connection, now: datetime, hours: int) -> Tuple[List[int], int]:
    total_hours = max(1, min(hours, 24))
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=total_hours - 1)
    buckets: Dict[datetime, int] = {}
    for idx in range(total_hours):
        point = start + timedelta(hours=idx)
        buckets[point] = 0

    timestamps, loaded_rows = _legacy_collect_timestamps(conn, start)
    for created_at in timestamps:
        key = created_at.replace(minute=0, second=0, microsecond=0)
        if key in buckets:
            buckets[key] += 1
    return [buckets[start + timedelta(hours=idx)] for idx in range(total_hours)], loaded_rows


def _optimized_daily_once(conn: sqlite3.Connection, now: datetime, days: int) -> Tuple[List[Tuple[str, int]], int]:
    total_days = max(7, min(days, 365))
    end_date = now.date()
    start_date = end_date - timedelta(days=total_days - 1)
    start_time = datetime.combine(start_date, dtime.min)
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

    rows = conn.execute(
        """
        SELECT strftime('%Y-%m-%d', created_at) AS bucket, COUNT(*) AS total
        FROM basic_message
        WHERE created_at >= ?
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        (start_str,),
    ).fetchall()

    buckets: Dict[str, int] = {}
    for idx in range(total_days):
        day = start_date + timedelta(days=idx)
        buckets[day.isoformat()] = 0
    for row in rows:
        bucket = row[0] if isinstance(row, tuple) else row["bucket"]
        total = row[1] if isinstance(row, tuple) else row["total"]
        if bucket in buckets:
            buckets[bucket] = int(total or 0)
    return [(key, buckets[key]) for key in sorted(buckets.keys())], len(rows)


def _optimized_hourly_once(conn: sqlite3.Connection, now: datetime, hours: int) -> Tuple[List[int], int]:
    total_hours = max(1, min(hours, 24))
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=total_hours - 1)
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")

    rows = conn.execute(
        """
        SELECT strftime('%Y-%m-%d %H:00:00', created_at) AS bucket, COUNT(*) AS total
        FROM basic_message
        WHERE created_at >= ?
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        (start_str,),
    ).fetchall()
    row_map: Dict[str, int] = {}
    for row in rows:
        bucket = row[0] if isinstance(row, tuple) else row["bucket"]
        total = row[1] if isinstance(row, tuple) else row["total"]
        row_map[str(bucket)] = int(total or 0)
    data: List[int] = []
    for idx in range(total_hours):
        point = start + timedelta(hours=idx)
        data.append(row_map.get(point.strftime("%Y-%m-%d %H:00:00"), 0))
    return data, len(rows)


def _measure_legacy_daily(conn: sqlite3.Connection, now: datetime, days: int) -> LegacyRunResult:
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    _, loaded_rows = _legacy_daily_once(conn, now, days)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return LegacyRunResult(elapsed_ms=elapsed_ms, peak_mb=peak_bytes / (1024 * 1024), loaded_rows=loaded_rows)


def _measure_optimized_daily(conn: sqlite3.Connection, now: datetime, days: int) -> OptimizedRunResult:
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    _, grouped_rows = _optimized_daily_once(conn, now, days)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return OptimizedRunResult(
        elapsed_ms=elapsed_ms,
        peak_mb=peak_bytes / (1024 * 1024),
        grouped_rows=grouped_rows,
    )


def _simulate_legacy_sse_queries(
    conn: sqlite3.Connection,
    now: datetime,
    hours: int,
    days: int,
    ticks: int,
    interval_seconds: int,
    clients: int,
) -> Tuple[int, int]:
    total_queries = 0
    total_loaded_rows = 0
    for i in range(ticks):
        tick_now = now + timedelta(seconds=i * interval_seconds)
        for _ in range(clients):
            _, hourly_rows = _legacy_hourly_once(conn, tick_now, hours)
            _, daily_rows = _legacy_daily_once(conn, tick_now, days)
            total_queries += 2
            total_loaded_rows += hourly_rows + daily_rows
    return total_queries, total_loaded_rows


def _simulate_optimized_sse_queries_with_cache(
    conn: sqlite3.Connection,
    now: datetime,
    hours: int,
    days: int,
    ticks: int,
    interval_seconds: int,
    streams: int,
    hourly_ttl_seconds: int = 5,
    daily_ttl_seconds: int = 60,
) -> Tuple[int, int]:
    total_queries = 0
    total_group_rows = 0
    for _ in range(streams):
        hourly_expire_at: Optional[datetime] = None
        daily_expire_at: Optional[datetime] = None
        for i in range(ticks):
            tick_now = now + timedelta(seconds=i * interval_seconds)
            if hourly_expire_at is None or hourly_expire_at <= tick_now:
                _, grouped_rows = _optimized_hourly_once(conn, tick_now, hours)
                total_queries += 1
                total_group_rows += grouped_rows
                hourly_expire_at = tick_now + timedelta(seconds=hourly_ttl_seconds)
            if daily_expire_at is None or daily_expire_at <= tick_now:
                _, grouped_rows = _optimized_daily_once(conn, tick_now, days)
                total_queries += 1
                total_group_rows += grouped_rows
                daily_expire_at = tick_now + timedelta(seconds=daily_ttl_seconds)
    return total_queries, total_group_rows


def _format_num(value: float) -> str:
    return f"{value:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark legacy vs optimized dashboard throughput computation on sqlite."
    )
    parser.add_argument("--db-url", default=None, help="Override db_url, default from persona config.")
    parser.add_argument("--hours", type=int, default=24, help="Hourly window size.")
    parser.add_argument("--days", type=int, default=120, help="Daily window size.")
    parser.add_argument("--ticks", type=int, default=12, help="SSE ticks to simulate.")
    parser.add_argument("--interval", type=int, default=5, help="SSE interval seconds.")
    parser.add_argument(
        "--legacy-clients",
        type=int,
        default=2,
        help="Legacy frontend SSE client count per dashboard page (before shared stream).",
    )
    parser.add_argument(
        "--optimized-streams",
        type=int,
        default=1,
        help="Optimized SSE physical stream count per dashboard page (after shared stream).",
    )
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db_url)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        table_exists = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name='basic_message'"
        ).fetchone()["c"]
        if table_exists == 0:
            raise RuntimeError("Table basic_message does not exist.")

        total_messages = conn.execute("SELECT COUNT(*) AS c FROM basic_message").fetchone()["c"]
        now = datetime.now().replace(microsecond=0)

        legacy_daily = _measure_legacy_daily(conn, now, args.days)
        optimized_daily = _measure_optimized_daily(conn, now, args.days)

        legacy_queries, legacy_rows = _simulate_legacy_sse_queries(
            conn=conn,
            now=now,
            hours=args.hours,
            days=args.days,
            ticks=args.ticks,
            interval_seconds=args.interval,
            clients=args.legacy_clients,
        )
        optimized_queries, optimized_rows = _simulate_optimized_sse_queries_with_cache(
            conn=conn,
            now=now,
            hours=args.hours,
            days=args.days,
            ticks=args.ticks,
            interval_seconds=args.interval,
            streams=args.optimized_streams,
        )

        print("=== Dashboard Throughput Benchmark ===")
        print(f"db_path: {db_path}")
        print(f"total_messages: {total_messages}")
        print(f"window: hours={args.hours}, days={args.days}")
        print(
            f"sse_simulation: ticks={args.ticks}, interval={args.interval}s, "
            f"legacy_clients={args.legacy_clients}, optimized_streams={args.optimized_streams}"
        )
        print("")
        print("[single daily calculation]")
        print(
            "legacy:    "
            f"elapsed_ms={_format_num(legacy_daily.elapsed_ms)}, "
            f"peak_mb={_format_num(legacy_daily.peak_mb)}, "
            f"loaded_rows={legacy_daily.loaded_rows}"
        )
        print(
            "optimized: "
            f"elapsed_ms={_format_num(optimized_daily.elapsed_ms)}, "
            f"peak_mb={_format_num(optimized_daily.peak_mb)}, "
            f"grouped_rows={optimized_daily.grouped_rows}"
        )
        print("")
        print("[sse query volume simulation]")
        print(
            "legacy:    "
            f"queries={legacy_queries}, "
            f"rows_loaded_to_app={legacy_rows}"
        )
        print(
            "optimized: "
            f"queries={optimized_queries}, "
            f"group_rows_loaded_to_app={optimized_rows}"
        )
        if legacy_queries > 0:
            print(
                "query_reduction: "
                f"{_format_num((1 - optimized_queries / legacy_queries) * 100)}%"
            )
        if legacy_rows > 0:
            print(
                "row_transfer_reduction: "
                f"{_format_num((1 - optimized_rows / legacy_rows) * 100)}%"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
