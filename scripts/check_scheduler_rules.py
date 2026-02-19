"""Enforce APScheduler scheduled_job decorator usage rules.

Rule:
- Do not pass `replace_existing` to `scheduled_job(...)`.

Reason:
- `BaseScheduler.scheduled_job()` already forwards `replace_existing=True`
  internally. Passing it again causes:
  `TypeError: BaseScheduler.add_job() got multiple values for argument 'replace_existing'`
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if _is_ignored(path):
            continue
        yield path


def find_violations(root: Path) -> list[tuple[Path, int, int]]:
    violations: list[tuple[Path, int, int]] = []
    for path in _iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "scheduled_job":
                continue

            for keyword in node.keywords:
                if keyword.arg == "replace_existing":
                    lineno = getattr(keyword, "lineno", node.lineno)
                    col = getattr(keyword, "col_offset", node.col_offset) + 1
                    violations.append((path, lineno, col))
                    break

    return violations


def _format_violations(root: Path, violations: list[tuple[Path, int, int]]) -> str:
    lines = [
        "Scheduled job rule violation:",
        "Do not pass `replace_existing` to `scheduled_job(...)`.",
        "Violations:",
    ]
    for path, lineno, col in violations:
        lines.append(f"- {path.relative_to(root)}:{lineno}:{col}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]).resolve() if args else Path.cwd().resolve()
    violations = find_violations(root)
    if not violations:
        print("Scheduled job rule check passed.")
        return 0

    print(_format_violations(root, violations))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
