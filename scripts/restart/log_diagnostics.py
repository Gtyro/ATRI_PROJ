from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infra.logging.restart_diagnostics import (  # noqa: E402
    collect_restart_log_diagnostics,
    format_diagnostics_text,
)


def main() -> int:
    diagnostics = collect_restart_log_diagnostics(
        log_dir=PROJECT_ROOT / "logs",
        status_file=PROJECT_ROOT / "data/restart/status.json",
    )
    print(format_diagnostics_text(diagnostics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
