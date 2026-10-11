"""判断 Persona 应使用轻量脚本导入还是完整 NoneBot 插件导入。"""

from __future__ import annotations

from typing import Iterable, Optional


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part for part in str(path).replace("\\", "/").split("/") if part)


def _contains_path(parts: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    width = len(expected)
    return any(parts[index : index + width] == expected for index in range(len(parts) - width + 1))


def should_use_script_mode(
    main_file: Optional[str],
    stack_files: Iterable[str] = (),
    active_main_files: Iterable[str] = (),
) -> bool:
    """Return whether Persona is imported from a script or adapter context.

    Script mode is based on the actual process entry point. A wrapper such as
    ``scripts/manage_processes.py`` may appear in the stack while it launches
    ``bot.py`` with ``runpy``; that must not suppress the Persona plugin.
    Adapter imports retain the legacy lightweight-mode safeguard.
    """
    # runpy.run_path(..., run_name="__main__") executes a new __main__ globals
    # dict without replacing sys.modules["__main__"]. Prefer that active frame
    # over the outer process module (often scripts/manage_processes.py).
    active_main_file = next(iter(active_main_files), None)
    entrypoint = active_main_file or main_file
    if entrypoint and "scripts" in _path_parts(entrypoint):
        return True

    return any(
        _contains_path(_path_parts(filename), ("src", "adapters"))
        for filename in stack_files
    )
