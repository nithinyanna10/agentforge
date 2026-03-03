"""Rich-powered logging for AgentForge."""

from __future__ import annotations

import logging
from typing import Any

_CONFIGURED = False


def setup_logging(level: int | str = logging.INFO) -> None:
    """Initialise the AgentForge root logger with a Rich console handler.

    Safe to call multiple times — only the first invocation installs
    the handler; subsequent calls just update the level.
    """
    global _CONFIGURED  # noqa: PLW0603

    root = logging.getLogger("agentforge")
    root.setLevel(level)

    if _CONFIGURED:
        return

    try:
        from rich.logging import RichHandler

        handler = RichHandler(
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            show_time=True,
            show_path=True,
            markup=True,
        )
        fmt = "%(message)s"
    except ImportError:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str, **_kw: Any) -> logging.Logger:
    """Return a child logger under the ``agentforge`` namespace.

    Automatically calls ``setup_logging`` if it hasn't been called yet
    so callers never have to worry about initialisation order.
    """
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(f"agentforge.{name}" if not name.startswith("agentforge") else name)
