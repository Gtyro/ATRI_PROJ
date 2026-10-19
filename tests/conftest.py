from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_runtime_dotenv(monkeypatch, tmp_path):
    """Prevent ordinary tests from reading repository dotenv files.

    Live-service tests must use explicitly supplied process environment values;
    no test should implicitly read the repository's development or production
    dotenv files.
    """
    from src.core.domain import runtime_settings

    (tmp_path / ".env.prod").write_text("", encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setattr(runtime_settings, "PROJECT_ROOT", tmp_path)
    yield


def pytest_sessionstart(session: pytest.Session) -> None:
    # Fixtures run after collection. Guard imports as well, since Persona's
    # default policy is loaded while test modules are imported.
    import dotenv

    original_dotenv_values = dotenv.dotenv_values

    def reject_repository_dotenv(dotenv_path=None, *args, **kwargs):
        if dotenv_path is not None:
            candidate = Path(dotenv_path).resolve()
            if (
                candidate.parent == PROJECT_ROOT.resolve()
                and candidate.name in {".env.dev", ".env.prod"}
            ):
                raise AssertionError("tests must not read repository dotenv files")
        return original_dotenv_values(dotenv_path, *args, **kwargs)

    session_patch = pytest.MonkeyPatch()
    session_patch.setattr(dotenv, "dotenv_values", reject_repository_dotenv)
    session.config.add_cleanup(session_patch.undo)

    from src.core.domain import runtime_settings

    isolated_dotenv = TemporaryDirectory(prefix="atri-test-env-")
    session.config.add_cleanup(isolated_dotenv.cleanup)
    session_patch.setenv("ENVIRONMENT", "prod")
    session_patch.setattr(runtime_settings, "PROJECT_ROOT", Path(isolated_dotenv.name))

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
