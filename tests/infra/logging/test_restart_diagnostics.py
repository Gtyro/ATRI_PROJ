from pathlib import Path

from src.infra.logging.restart_diagnostics import (
    collect_restart_log_diagnostics,
    summarize_issue_status,
)


def test_collect_restart_log_diagnostics_counts_startup_window_and_previous_log(
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    (log_dir / "2026-03-09_20-37.log").write_text(
        "\n".join(
            [
                "2026-03-09 20:37:15 | INFO | nonebot | init.py:1 | booting",
                "2026-03-09 20:37:18 | WARNING | root | check.py:2 | previous warning",
                "2026-03-09 20:37:19 | ERROR | root | check.py:3 | previous error 1",
                "2026-03-09 20:37:20 | ERROR | root | check.py:4 | previous error 2",
            ]
        ),
        encoding="utf-8",
    )
    (log_dir / "2026-03-09_21-38.log").write_text(
        "\n".join(
            [
                "2026-03-09 21:38:04 | INFO | nonebot | init.py:1 | booting",
                "2026-03-09 21:38:05 | WARNING | root | startup.py:2 | config degraded",
                "2026-03-09 21:38:06 | ERROR | root | startup.py:3 | neo4j unavailable",
                "2026-03-09 21:38:07 | ERROR | root | startup.py:4 | webui disabled",
                "2026-03-09 21:42:10 | ERROR | root | runtime.py:5 | runtime failure",
            ]
        ),
        encoding="utf-8",
    )

    diagnostics = collect_restart_log_diagnostics(
        log_dir=log_dir,
        startup_reference="2026-03-09T21:38:09",
        startup_window_seconds=180,
    )

    assert diagnostics["current_log"].endswith("2026-03-09_21-38.log")
    assert diagnostics["previous_log"].endswith("2026-03-09_20-37.log")
    assert diagnostics["startup_summary"]["errors"] == 2
    assert diagnostics["startup_summary"]["warnings"] == 1
    assert diagnostics["previous_log_summary"]["errors"] == 2
    assert diagnostics["previous_log_summary"]["warnings"] == 1
    assert diagnostics["startup_summary"]["status"] == "error"
    assert all(
        "runtime failure" not in sample
        for sample in diagnostics["startup_summary"]["sample_messages"]
    )


def test_collect_restart_log_diagnostics_handles_missing_logs(tmp_path: Path) -> None:
    diagnostics = collect_restart_log_diagnostics(
        log_dir=tmp_path / "logs",
        startup_reference="2026-03-09T21:38:09",
    )

    assert diagnostics["current_log"] is None
    assert diagnostics["previous_log"] is None
    assert diagnostics["startup_summary"]["status"] == "missing"
    assert diagnostics["previous_log_summary"]["status"] == "missing"


def test_summarize_issue_status_formats_error_warning_and_ok() -> None:
    assert summarize_issue_status(2, 1) == "❌ 检测到 2 个 ERROR，1 个 WARNING"
    assert summarize_issue_status(0, 3) == "⚠️ 检测到 0 个 ERROR，3 个 WARNING"
    assert summarize_issue_status(0, 0) == "✅ 未检测到 ERROR/WARNING"
