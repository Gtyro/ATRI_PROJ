"""NoneBot 适配层。"""

from __future__ import annotations

from typing import Any


def assemble_persona_engine(*args: Any, **kwargs: Any):
    from .persona_assembler import assemble_persona_engine as _assemble_persona_engine

    return _assemble_persona_engine(*args, **kwargs)

__all__ = ["assemble_persona_engine"]
