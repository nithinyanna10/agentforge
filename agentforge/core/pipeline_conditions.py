"""
Compile pipeline step conditions from YAML-safe string expressions (next-level).

Allows steps to have condition_expr: "true" | "key" | "not key" so that
steps can be skipped when loading from YAML without embedding Python.
"""

from __future__ import annotations

from typing import Any, Callable

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


def compile_condition(expr: str) -> Callable[[dict[str, Any]], bool]:
    """
    Compile a simple condition expression into a callable(context) -> bool.

    Supported forms:
      - "true" or "": always run (return True)
      - "key": run iff context.get("key") is truthy
      - "not key": run iff context.get("key") is falsy
      - "key in context": run iff "key" in context
    """
    expr = (expr or "").strip().lower()
    if expr in ("true", ""):
        return lambda ctx: True
    if expr.startswith("not "):
        key = expr[4:].strip()
        return lambda ctx: not ctx.get(key)
    if " in context" in expr:
        key = expr.replace(" in context", "").strip()
        return lambda ctx: key in ctx
    return lambda ctx: bool(ctx.get(expr))
