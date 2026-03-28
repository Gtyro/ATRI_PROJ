from pathlib import Path

from src.infra.logging.memory_monitor import (
    FAMILY_NAMES,
    CategorySnapshot,
    MonitorSample,
    ProcessSnapshot,
    SystemMemorySnapshot,
    assign_process_families,
    format_memory_summary,
    monitor_sample_to_row,
    summarize_samples,
    update_peak_snapshots,
)


def _process(
    pid: int,
    ppid: int,
    name: str,
    cmdline: str,
    *,
    cgroup: str = "",
    user: str = "ubuntu",
    rss_kb: int = 100,
    pss_kb: int = 0,
    swap_kb: int = 0,
) -> ProcessSnapshot:
    effective_kb = pss_kb if pss_kb > 0 else rss_kb
    return ProcessSnapshot(
        pid=pid,
        ppid=ppid,
        user=user,
        name=name,
        cmdline=cmdline,
        cgroup=cgroup,
        rss_kb=rss_kb,
        pss_kb=pss_kb,
        swap_kb=swap_kb,
        effective_kb=effective_kb,
        create_time=1.0,
    )


def test_assign_process_families_prefers_specific_roots_and_inherits_children() -> None:
    project_root = Path("/home/ubuntu/ATRI_PROJ")
    processes = [
        _process(100, 1, "python", "/home/ubuntu/ATRI_PROJ/bot.py"),
        _process(101, 100, "node", "/usr/bin/node helper.js"),
        _process(
            200,
            1,
            "node",
            "/home/ubuntu/.vscode-server/bin/hash/node /home/ubuntu/.vscode-server/bin/hash/out/server-main.js",
        ),
        _process(201, 200, "node", "/usr/bin/node extensionHost.js"),
        _process(
            300,
            1,
            "python",
            "/home/ubuntu/.daily-insight-codex/codex_automation.py run",
        ),
        _process(301, 300, "node", "/usr/bin/node child.js"),
        _process(
            400,
            1,
            "java",
            "org.neo4j.server.Neo4jCommunity",
            cgroup="0::/system.slice/neo4j.service",
            user="neo4j",
        ),
        _process(500, 1, "codex", "/home/ubuntu/.codex/bin/codex"),
        _process(600, 1, "node", "/usr/bin/node random.js"),
    ]

    assigned = {process.pid: process.family for process in assign_process_families(processes, project_root)}

    assert assigned[100] == "atri_bot"
    assert assigned[101] == "atri_bot"
    assert assigned[200] == "vscode_remote"
    assert assigned[201] == "vscode_remote"
    assert assigned[300] == "daily_insight_codex"
    assert assigned[301] == "daily_insight_codex"
    assert assigned[400] == "neo4j"
    assert assigned[500] == "codex"
    assert assigned[600] == "node_other"


def test_summarize_samples_tracks_peaks_and_formats_summary() -> None:
    categories_one = {family: CategorySnapshot() for family in FAMILY_NAMES}
    categories_two = {family: CategorySnapshot() for family in FAMILY_NAMES}
    categories_one["neo4j"] = CategorySnapshot(process_count=1, rss_kb=120_000, pss_kb=110_000, effective_kb=110_000)
    categories_one["vscode_remote"] = CategorySnapshot(
        process_count=3,
        rss_kb=320_000,
        pss_kb=250_000,
        effective_kb=250_000,
    )
    categories_two["neo4j"] = CategorySnapshot(process_count=1, rss_kb=160_000, pss_kb=150_000, effective_kb=150_000)
    categories_two["vscode_remote"] = CategorySnapshot(
        process_count=4,
        rss_kb=500_000,
        pss_kb=420_000,
        effective_kb=420_000,
        swap_kb=32_000,
    )

    sample_one = MonitorSample(
        timestamp="2026-03-19T10:00:00+08:00",
        epoch_seconds=1.0,
        system=SystemMemorySnapshot(
            mem_total_kb=1_000_000,
            mem_available_kb=400_000,
            mem_free_kb=200_000,
            swap_total_kb=200_000,
            swap_free_kb=150_000,
            buffers_kb=10_000,
            cached_kb=20_000,
            loadavg_1m=1.0,
            loadavg_5m=0.8,
            loadavg_15m=0.5,
        ),
        categories=categories_one,
        top_processes=(_process(1, 0, "node", "vscode", pss_kb=250_000),),
    )
    sample_two = MonitorSample(
        timestamp="2026-03-19T10:00:10+08:00",
        epoch_seconds=11.0,
        system=SystemMemorySnapshot(
            mem_total_kb=1_000_000,
            mem_available_kb=250_000,
            mem_free_kb=120_000,
            swap_total_kb=200_000,
            swap_free_kb=90_000,
            buffers_kb=10_000,
            cached_kb=20_000,
            loadavg_1m=1.2,
            loadavg_5m=0.9,
            loadavg_15m=0.6,
        ),
        categories=categories_two,
        top_processes=(
            _process(2, 0, "node", "vscode", pss_kb=420_000),
            _process(3, 0, "java", "neo4j", pss_kb=150_000),
        ),
    )

    peak_snapshots: dict[str, dict[str, object]] = {}
    update_peak_snapshots(sample_one, peak_snapshots)
    update_peak_snapshots(sample_two, peak_snapshots)

    summary = summarize_samples(
        [monitor_sample_to_row(sample_one), monitor_sample_to_row(sample_two)],
        peak_snapshots,
        {
            "project_root": "/home/ubuntu/ATRI_PROJ",
            "started_at": "2026-03-19T10:00:00+08:00",
            "ended_at": "2026-03-19T10:00:10+08:00",
            "interval_seconds": 10.0,
        },
    )

    assert summary["system"]["peak_used_kb"] == 750_000
    assert summary["system"]["lowest_swap_free_kb"] == 90_000
    assert summary["families"]["neo4j"]["peak_effective_kb"] == 150_000
    assert summary["families"]["vscode_remote"]["peak_effective_kb"] == 420_000
    assert summary["peak_snapshots"]["system_used_kb"]["timestamp"] == "2026-03-19T10:00:10+08:00"

    text = format_memory_summary(summary)
    assert "内存监测摘要" in text
    assert "Neo4j" in text
    assert "VS Code Remote" in text
