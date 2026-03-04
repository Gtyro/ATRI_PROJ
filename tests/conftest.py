from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_sessionstart(session: pytest.Session) -> None:
    from scripts.check_scheduler_rules import find_violations

    violations = find_violations(PROJECT_ROOT)
    if not violations:
        return

    lines = [
        "禁止在 scheduled_job(...) 中显式传入 replace_existing。",
        "原因：该装饰器内部已固定 replace_existing=True，重复传参会导致导入失败。",
        "违规位置：",
    ]
    lines.extend(
        f"- {path.relative_to(PROJECT_ROOT)}:{line}:{col}"
        for path, line, col in violations
    )
    raise pytest.UsageError("\n".join(lines))
