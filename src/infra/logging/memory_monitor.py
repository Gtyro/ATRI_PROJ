from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

import psutil


FAMILY_NAMES: tuple[str, ...] = (
    "neo4j",
    "atri_bot",
    "vscode_remote",
    "daily_insight_codex",
    "codex",
    "node_other",
    "other",
)
FAMILY_LABELS: dict[str, str] = {
    "neo4j": "Neo4j",
    "atri_bot": "ATRI Bot",
    "vscode_remote": "VS Code Remote",
    "daily_insight_codex": "Daily Insight Codex",
    "codex": "Codex",
    "node_other": "Other node",
    "other": "Other",
}
INHERITED_FAMILIES = {
    "neo4j",
    "atri_bot",
    "vscode_remote",
    "daily_insight_codex",
    "codex",
}
CATEGORY_METRICS = ("process_count", "rss_kb", "pss_kb", "swap_kb", "effective_kb")


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int
    ppid: int
    user: str
    name: str
    cmdline: str
    cgroup: str
    rss_kb: int
    pss_kb: int
    swap_kb: int
    effective_kb: int
    create_time: float
    family: str = "other"


@dataclass(frozen=True)
class CategorySnapshot:
    process_count: int = 0
    rss_kb: int = 0
    pss_kb: int = 0
    swap_kb: int = 0
    effective_kb: int = 0


@dataclass(frozen=True)
class SystemMemorySnapshot:
    mem_total_kb: int
    mem_available_kb: int
    mem_free_kb: int
    swap_total_kb: int
    swap_free_kb: int
    buffers_kb: int
    cached_kb: int
    loadavg_1m: float
    loadavg_5m: float
    loadavg_15m: float

    @property
    def used_kb(self) -> int:
        return max(self.mem_total_kb - self.mem_available_kb, 0)


@dataclass(frozen=True)
class MonitorSample:
    timestamp: str
    epoch_seconds: float
    system: SystemMemorySnapshot
    categories: dict[str, CategorySnapshot]
    top_processes: tuple[ProcessSnapshot, ...]


def _default_output_dir(project_root: Path) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    return project_root / "data" / "diagnostics" / "memory_monitor" / stamp


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError:
            continue
    return values


def collect_system_memory_snapshot() -> SystemMemorySnapshot:
    meminfo = _read_meminfo()
    try:
        loadavg = os.getloadavg()
    except OSError:
        loadavg = (0.0, 0.0, 0.0)
    return SystemMemorySnapshot(
        mem_total_kb=int(meminfo.get("MemTotal", 0)),
        mem_available_kb=int(meminfo.get("MemAvailable", 0)),
        mem_free_kb=int(meminfo.get("MemFree", 0)),
        swap_total_kb=int(meminfo.get("SwapTotal", 0)),
        swap_free_kb=int(meminfo.get("SwapFree", 0)),
        buffers_kb=int(meminfo.get("Buffers", 0)),
        cached_kb=int(meminfo.get("Cached", 0)),
        loadavg_1m=float(loadavg[0]),
        loadavg_5m=float(loadavg[1]),
        loadavg_15m=float(loadavg[2]),
    )


def _read_cgroup(pid: int) -> str:
    path = Path("/proc") / str(pid) / "cgroup"
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def _normalize_cmdline(parts: Sequence[str] | None, fallback: str) -> str:
    normalized = " ".join(part for part in (parts or ()) if part)
    return normalized.strip() or fallback.strip()


def _is_monitor_process(cmdline_lower: str) -> bool:
    return "monitor_memory.py" in cmdline_lower or "pytest" in cmdline_lower


def classify_process_direct(process: ProcessSnapshot, project_root: Path) -> str:
    cmdline_lower = process.cmdline.lower()
    name_lower = process.name.lower()
    cgroup_lower = process.cgroup.lower()
    project_root_lower = str(project_root).lower()

    if "neo4j.service" in cgroup_lower or "org.neo4j" in cmdline_lower:
        return "neo4j"
    if "/var/lib/neo4j" in cmdline_lower and process.name.lower() == "java":
        return "neo4j"
    if ".vscode-server" in cmdline_lower:
        return "vscode_remote"
    if "server-main.js" in cmdline_lower or "extensionhost" in cmdline_lower:
        return "vscode_remote"
    if name_lower.startswith("code-"):
        return "vscode_remote"
    if ".daily-insight-codex" in cmdline_lower:
        return "daily_insight_codex"
    if "/.codex/" in cmdline_lower or name_lower.startswith("codex"):
        return "codex"
    if project_root_lower in cmdline_lower and not _is_monitor_process(cmdline_lower):
        return "atri_bot"
    if name_lower == "node":
        return "node_other"
    return "other"


def assign_process_families(
    processes: Sequence[ProcessSnapshot],
    project_root: Path,
) -> list[ProcessSnapshot]:
    families: dict[int, str] = {
        process.pid: classify_process_direct(process, project_root)
        for process in processes
    }

    changed = True
    while changed:
        changed = False
        for process in processes:
            parent_family = families.get(process.ppid)
            current_family = families.get(process.pid, "other")
            if parent_family not in INHERITED_FAMILIES:
                continue
            if current_family in {"other", "node_other"}:
                families[process.pid] = parent_family
                changed = True

    assigned: list[ProcessSnapshot] = []
    for process in processes:
        family = families.get(process.pid, "other")
        if family not in FAMILY_NAMES:
            family = "other"
        assigned.append(replace(process, family=family))
    return assigned


def collect_process_snapshots(
    project_root: Path,
    *,
    include_pss: bool = True,
) -> list[ProcessSnapshot]:
    processes: list[ProcessSnapshot] = []
    current_pid = os.getpid()
    for proc in psutil.process_iter(
        ["pid", "ppid", "username", "name", "cmdline", "create_time"]
    ):
        try:
            info = proc.info
            memory_info = proc.memory_info()
            rss_kb = int(memory_info.rss / 1024)
            pss_kb = 0
            swap_kb = 0
            if include_pss:
                try:
                    full_info = proc.memory_full_info()
                    rss_kb = int(getattr(full_info, "rss", memory_info.rss) / 1024)
                    pss_kb = int(getattr(full_info, "pss", 0) / 1024)
                    swap_kb = int(getattr(full_info, "swap", 0) / 1024)
                except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                    pass

            cmdline = _normalize_cmdline(info.get("cmdline"), info.get("name") or "")
            if int(info["pid"]) == current_pid and _is_monitor_process(cmdline.lower()):
                continue
            user = str(info.get("username") or "")
            create_time = float(info.get("create_time") or 0.0)

            processes.append(
                ProcessSnapshot(
                    pid=int(info["pid"]),
                    ppid=int(info.get("ppid") or 0),
                    user=user,
                    name=str(info.get("name") or ""),
                    cmdline=cmdline,
                    cgroup=_read_cgroup(int(info["pid"])),
                    rss_kb=rss_kb,
                    pss_kb=pss_kb,
                    swap_kb=swap_kb,
                    effective_kb=pss_kb if pss_kb > 0 else rss_kb,
                    create_time=create_time,
                )
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return assign_process_families(processes, project_root)


def aggregate_categories(
    processes: Sequence[ProcessSnapshot],
) -> dict[str, CategorySnapshot]:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for process in processes:
        family = process.family if process.family in FAMILY_NAMES else "other"
        bucket = totals[family]
        bucket["process_count"] += 1
        bucket["rss_kb"] += process.rss_kb
        bucket["pss_kb"] += process.pss_kb
        bucket["swap_kb"] += process.swap_kb
        bucket["effective_kb"] += process.effective_kb

    snapshots: dict[str, CategorySnapshot] = {}
    for family in FAMILY_NAMES:
        bucket = totals.get(family, {})
        snapshots[family] = CategorySnapshot(
            process_count=int(bucket.get("process_count", 0)),
            rss_kb=int(bucket.get("rss_kb", 0)),
            pss_kb=int(bucket.get("pss_kb", 0)),
            swap_kb=int(bucket.get("swap_kb", 0)),
            effective_kb=int(bucket.get("effective_kb", 0)),
        )
    return snapshots


def select_top_processes(
    processes: Sequence[ProcessSnapshot],
    top_n: int,
) -> tuple[ProcessSnapshot, ...]:
    ranked = sorted(
        processes,
        key=lambda process: (process.effective_kb, process.rss_kb, -process.pid),
        reverse=True,
    )
    return tuple(ranked[: max(top_n, 0)])


def collect_monitor_sample(
    project_root: Path,
    *,
    include_pss: bool = True,
    top_n: int = 10,
) -> MonitorSample:
    timestamp = datetime.now().astimezone()
    processes = collect_process_snapshots(project_root, include_pss=include_pss)
    categories = aggregate_categories(processes)
    top_processes = select_top_processes(processes, top_n)
    return MonitorSample(
        timestamp=timestamp.isoformat(timespec="seconds"),
        epoch_seconds=timestamp.timestamp(),
        system=collect_system_memory_snapshot(),
        categories=categories,
        top_processes=top_processes,
    )


def sample_fieldnames() -> list[str]:
    fieldnames = [
        "timestamp",
        "epoch_seconds",
        "mem_total_kb",
        "mem_available_kb",
        "mem_free_kb",
        "mem_used_kb",
        "swap_total_kb",
        "swap_free_kb",
        "buffers_kb",
        "cached_kb",
        "loadavg_1m",
        "loadavg_5m",
        "loadavg_15m",
    ]
    for family in FAMILY_NAMES:
        for metric in CATEGORY_METRICS:
            fieldnames.append(f"{family}_{metric}")
    return fieldnames


def monitor_sample_to_row(sample: MonitorSample) -> dict[str, int | float | str]:
    row: dict[str, int | float | str] = {
        "timestamp": sample.timestamp,
        "epoch_seconds": sample.epoch_seconds,
        "mem_total_kb": sample.system.mem_total_kb,
        "mem_available_kb": sample.system.mem_available_kb,
        "mem_free_kb": sample.system.mem_free_kb,
        "mem_used_kb": sample.system.used_kb,
        "swap_total_kb": sample.system.swap_total_kb,
        "swap_free_kb": sample.system.swap_free_kb,
        "buffers_kb": sample.system.buffers_kb,
        "cached_kb": sample.system.cached_kb,
        "loadavg_1m": sample.system.loadavg_1m,
        "loadavg_5m": sample.system.loadavg_5m,
        "loadavg_15m": sample.system.loadavg_15m,
    }
    for family in FAMILY_NAMES:
        category = sample.categories.get(family, CategorySnapshot())
        row[f"{family}_process_count"] = category.process_count
        row[f"{family}_rss_kb"] = category.rss_kb
        row[f"{family}_pss_kb"] = category.pss_kb
        row[f"{family}_swap_kb"] = category.swap_kb
        row[f"{family}_effective_kb"] = category.effective_kb
    return row


def iter_top_process_rows(sample: MonitorSample) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, process in enumerate(sample.top_processes, start=1):
        rows.append(
            {
                "timestamp": sample.timestamp,
                "rank": rank,
                "family": process.family,
                "pid": process.pid,
                "ppid": process.ppid,
                "user": process.user,
                "name": process.name,
                "rss_kb": process.rss_kb,
                "pss_kb": process.pss_kb,
                "swap_kb": process.swap_kb,
                "effective_kb": process.effective_kb,
                "create_time": process.create_time,
                "cgroup": process.cgroup,
                "cmdline": process.cmdline,
            }
        )
    return rows


def _process_to_dict(process: ProcessSnapshot) -> dict[str, Any]:
    return asdict(process)


def update_peak_snapshots(
    sample: MonitorSample,
    peak_snapshots: dict[str, dict[str, Any]],
) -> None:
    system_used_kb = sample.system.used_kb
    current_system_peak = peak_snapshots.get("system_used_kb", {})
    if system_used_kb >= int(current_system_peak.get("value_kb", -1)):
        peak_snapshots["system_used_kb"] = {
            "timestamp": sample.timestamp,
            "value_kb": system_used_kb,
            "top_processes": [_process_to_dict(process) for process in sample.top_processes],
        }

    swap_used_kb = max(sample.system.swap_total_kb - sample.system.swap_free_kb, 0)
    current_swap_peak = peak_snapshots.get("swap_used_kb", {})
    if swap_used_kb >= int(current_swap_peak.get("value_kb", -1)):
        peak_snapshots["swap_used_kb"] = {
            "timestamp": sample.timestamp,
            "value_kb": swap_used_kb,
            "top_processes": [_process_to_dict(process) for process in sample.top_processes],
        }

    for family in FAMILY_NAMES:
        effective_kb = sample.categories.get(family, CategorySnapshot()).effective_kb
        key = f"{family}_effective_kb"
        current_peak = peak_snapshots.get(key, {})
        if effective_kb >= int(current_peak.get("value_kb", -1)):
            peak_snapshots[key] = {
                "timestamp": sample.timestamp,
                "value_kb": effective_kb,
                "top_processes": [_process_to_dict(process) for process in sample.top_processes],
            }


def summarize_samples(
    sample_rows: Sequence[dict[str, int | float | str]],
    peak_snapshots: dict[str, dict[str, Any]],
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    metadata = dict(metadata or {})
    if not sample_rows:
        return {
            "metadata": metadata,
            "system": {
                "sample_count": 0,
                "peak_used_kb": 0,
                "peak_used_timestamp": None,
                "avg_used_kb": 0,
                "lowest_swap_free_kb": 0,
                "lowest_swap_free_timestamp": None,
            },
            "families": {},
            "peak_snapshots": peak_snapshots,
        }

    system_peak_row = max(sample_rows, key=lambda row: int(row["mem_used_kb"]))
    lowest_swap_row = min(sample_rows, key=lambda row: int(row["swap_free_kb"]))
    sample_count = len(sample_rows)

    families: dict[str, Any] = {}
    for family in FAMILY_NAMES:
        process_counts = [int(row[f"{family}_process_count"]) for row in sample_rows]
        rss_values = [int(row[f"{family}_rss_kb"]) for row in sample_rows]
        pss_values = [int(row[f"{family}_pss_kb"]) for row in sample_rows]
        swap_values = [int(row[f"{family}_swap_kb"]) for row in sample_rows]
        effective_values = [int(row[f"{family}_effective_kb"]) for row in sample_rows]

        peak_index = max(range(sample_count), key=lambda idx: effective_values[idx])
        families[family] = {
            "label": FAMILY_LABELS.get(family, family),
            "avg_process_count": sum(process_counts) / sample_count,
            "avg_rss_kb": sum(rss_values) / sample_count,
            "avg_pss_kb": sum(pss_values) / sample_count,
            "avg_swap_kb": sum(swap_values) / sample_count,
            "avg_effective_kb": sum(effective_values) / sample_count,
            "peak_process_count": process_counts[peak_index],
            "peak_rss_kb": max(rss_values),
            "peak_pss_kb": max(pss_values),
            "peak_swap_kb": max(swap_values),
            "peak_effective_kb": effective_values[peak_index],
            "peak_timestamp": sample_rows[peak_index]["timestamp"],
        }

    return {
        "metadata": metadata,
        "system": {
            "sample_count": sample_count,
            "peak_used_kb": int(system_peak_row["mem_used_kb"]),
            "peak_used_timestamp": system_peak_row["timestamp"],
            "avg_used_kb": sum(int(row["mem_used_kb"]) for row in sample_rows) / sample_count,
            "lowest_swap_free_kb": int(lowest_swap_row["swap_free_kb"]),
            "lowest_swap_free_timestamp": lowest_swap_row["timestamp"],
        },
        "families": families,
        "peak_snapshots": peak_snapshots,
    }


def _format_kb(value_kb: float | int) -> str:
    value = float(value_kb)
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} GiB"
    return f"{value / 1024:.1f} MiB"


def _shorten_cmdline(cmdline: str, limit: int = 120) -> str:
    normalized = " ".join(cmdline.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def format_memory_summary(summary: dict[str, Any]) -> str:
    system = summary.get("system", {})
    metadata = summary.get("metadata", {})
    families = summary.get("families", {})
    peak_snapshots = summary.get("peak_snapshots", {})

    lines = [
        "内存监测摘要",
        "------------------------",
        f"项目目录: {metadata.get('project_root', 'unknown')}",
        f"开始时间: {metadata.get('started_at', 'unknown')}",
        f"结束时间: {metadata.get('ended_at', 'unknown')}",
        f"采样间隔: {metadata.get('interval_seconds', 'unknown')} 秒",
        f"样本数量: {system.get('sample_count', 0)}",
        f"系统峰值占用: {_format_kb(system.get('peak_used_kb', 0))}",
        f"系统峰值时刻: {system.get('peak_used_timestamp') or 'unknown'}",
        f"平均系统占用: {_format_kb(system.get('avg_used_kb', 0))}",
        f"最低剩余 Swap: {_format_kb(system.get('lowest_swap_free_kb', 0))}",
        f"最低剩余 Swap 时刻: {system.get('lowest_swap_free_timestamp') or 'unknown'}",
        "",
        "分类概览",
        "------------------------",
    ]

    for family in FAMILY_NAMES:
        family_summary = families.get(family)
        if not family_summary:
            continue
        if family_summary.get("avg_effective_kb", 0) <= 0 and family_summary.get(
            "peak_effective_kb", 0
        ) <= 0:
            continue
        lines.append(
            "- {label}: avg={avg} peak={peak} peak_at={peak_at} avg_proc={avg_proc:.2f}".format(
                label=family_summary["label"],
                avg=_format_kb(family_summary["avg_effective_kb"]),
                peak=_format_kb(family_summary["peak_effective_kb"]),
                peak_at=family_summary["peak_timestamp"],
                avg_proc=float(family_summary["avg_process_count"]),
            )
        )

    system_peak = peak_snapshots.get("system_used_kb", {})
    if system_peak.get("top_processes"):
        lines.extend(
            [
                "",
                "系统峰值时 Top 进程",
                "------------------------",
            ]
        )
        for process in system_peak["top_processes"][:5]:
            lines.append(
                "- {family} pid={pid} effective={effective} cmd={cmdline}".format(
                    family=FAMILY_LABELS.get(process.get("family", "other"), process.get("family", "other")),
                    pid=process.get("pid"),
                    effective=_format_kb(process.get("effective_kb", 0)),
                    cmdline=_shorten_cmdline(str(process.get("cmdline", ""))),
                )
            )

    return "\n".join(lines)


def top_process_fieldnames() -> list[str]:
    return [
        "timestamp",
        "rank",
        "family",
        "pid",
        "ppid",
        "user",
        "name",
        "rss_kb",
        "pss_kb",
        "swap_kb",
        "effective_kb",
        "create_time",
        "cgroup",
        "cmdline",
    ]


def run_memory_monitor(
    *,
    output_dir: Path,
    project_root: Path,
    interval_seconds: float = 10.0,
    duration_seconds: Optional[float] = None,
    include_pss: bool = True,
    top_n: int = 10,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    start_monotonic = time.monotonic()
    sample_rows: list[dict[str, int | float | str]] = []
    peak_snapshots: dict[str, dict[str, Any]] = {}
    stop_requested = False

    def _request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    previous_int = signal.signal(signal.SIGINT, _request_stop)
    previous_term = signal.signal(signal.SIGTERM, _request_stop)
    try:
        next_run = time.monotonic()
        with (
            (output_dir / "samples.csv").open("w", encoding="utf-8", newline="") as samples_file,
            (output_dir / "top_processes.csv").open("w", encoding="utf-8", newline="") as top_file,
        ):
            sample_writer = csv.DictWriter(samples_file, fieldnames=sample_fieldnames())
            top_writer = csv.DictWriter(top_file, fieldnames=top_process_fieldnames())
            sample_writer.writeheader()
            top_writer.writeheader()

            while True:
                sample = collect_monitor_sample(
                    project_root,
                    include_pss=include_pss,
                    top_n=top_n,
                )
                row = monitor_sample_to_row(sample)
                sample_rows.append(row)
                sample_writer.writerow(row)
                top_writer.writerows(iter_top_process_rows(sample))
                samples_file.flush()
                top_file.flush()
                update_peak_snapshots(sample, peak_snapshots)

                if stop_requested:
                    break
                if duration_seconds is not None:
                    elapsed = time.monotonic() - start_monotonic
                    if elapsed >= duration_seconds:
                        break

                next_run += interval_seconds
                sleep_seconds = max(0.0, next_run - time.monotonic())
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)

    ended_at = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = {
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "interval_seconds": interval_seconds,
        "duration_seconds": duration_seconds,
        "include_pss": include_pss,
        "top_n": top_n,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    summary = summarize_samples(sample_rows, peak_snapshots, metadata)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.txt").write_text(
        format_memory_summary(summary),
        encoding="utf-8",
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor system, Neo4j, ATRI bot and VS Code Remote memory usage over time.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root used to identify ATRI bot processes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for samples and summary outputs.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=10.0,
        help="Sampling interval in seconds.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Total sampling duration in seconds. Omit to run until Ctrl+C.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="How many processes to keep per-sample in top_processes.csv.",
    )
    parser.add_argument(
        "--no-pss",
        action="store_true",
        help="Disable PSS collection if you need lower overhead.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else _default_output_dir(project_root)
    )
    summary = run_memory_monitor(
        output_dir=output_dir,
        project_root=project_root,
        interval_seconds=float(args.interval_seconds),
        duration_seconds=(
            float(args.duration_seconds)
            if args.duration_seconds is not None
            else None
        ),
        include_pss=not bool(args.no_pss),
        top_n=int(args.top_n),
    )
    print(format_memory_summary(summary))
    print("")
    print(f"输出目录: {output_dir}")
    return 0


__all__ = [
    "CATEGORY_METRICS",
    "FAMILY_LABELS",
    "FAMILY_NAMES",
    "CategorySnapshot",
    "MonitorSample",
    "ProcessSnapshot",
    "SystemMemorySnapshot",
    "assign_process_families",
    "classify_process_direct",
    "collect_monitor_sample",
    "collect_process_snapshots",
    "collect_system_memory_snapshot",
    "format_memory_summary",
    "iter_top_process_rows",
    "main",
    "monitor_sample_to_row",
    "run_memory_monitor",
    "sample_fieldnames",
    "select_top_processes",
    "summarize_samples",
    "update_peak_snapshots",
]
