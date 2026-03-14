"""
Pipeline event bus and middleware for next-level observability and control.

Allows subscribing to pipeline lifecycle events (step_start, step_end, layer_start, etc.)
and optional middleware to modify or validate step inputs/outputs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PipelineEventType(str, Enum):
    """Pipeline lifecycle event types."""

    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"
    LAYER_START = "layer_start"
    LAYER_END = "layer_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    STEP_SKIP = "step_skip"
    STEP_ERROR = "step_error"
    CONTEXT_UPDATE = "context_update"


@dataclass
class PipelineEvent:
    """A single pipeline event with payload."""

    type: PipelineEventType
    pipeline_name: str = ""
    step_name: str = ""
    layer_index: int = -1
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "pipeline_name": self.pipeline_name,
            "step_name": self.step_name,
            "layer_index": self.layer_index,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


PipelineEventHandler = Callable[[PipelineEvent], Any]  # sync or async
PipelineMiddleware = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]  # step_name, context -> new_context


class PipelineEventBus:
    """Central event bus for pipeline execution. Handlers can be sync or async."""

    def __init__(self) -> None:
        self._handlers: list[PipelineEventHandler] = []
        self._middleware: list[PipelineMiddleware] = []

    def subscribe(self, handler: PipelineEventHandler) -> None:
        """Add an event handler. Handler may be sync or async."""
        self._handlers.append(handler)

    def unsubscribe(self, handler: PipelineEventHandler) -> bool:
        """Remove a handler. Returns True if it was present."""
        try:
            self._handlers.remove(handler)
            return True
        except ValueError:
            return False

    def add_middleware(self, mw: PipelineMiddleware) -> None:
        """Add middleware that can transform context before a step runs."""
        self._middleware.append(mw)

    async def emit(self, event: PipelineEvent) -> None:
        """Emit an event to all handlers."""
        for h in self._handlers:
            try:
                result = h(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Pipeline event handler failed: %s", e)

    async def run_middleware(self, step_name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Run all middleware in order and return transformed context."""
        current = dict(context)
        for mw in self._middleware:
            try:
                current = await mw(step_name, current)
            except Exception as e:
                logger.warning("Pipeline middleware failed for step %r: %s", step_name, e)
        return current

    def clear(self) -> None:
        """Remove all handlers and middleware."""
        self._handlers.clear()
        self._middleware.clear()


# Global default bus (optional use)
_default_bus: PipelineEventBus | None = None


def get_pipeline_event_bus() -> PipelineEventBus:
    """Return the default pipeline event bus (singleton)."""
    global _default_bus
    if _default_bus is None:
        _default_bus = PipelineEventBus()
    return _default_bus


def reset_pipeline_event_bus() -> None:
    """Reset the default bus (e.g. for tests)."""
    global _default_bus
    if _default_bus is not None:
        _default_bus.clear()
    _default_bus = None


# ---------------------------------------------------------------------------
# Middleware helpers
# ---------------------------------------------------------------------------


async def logging_middleware(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Middleware that logs step name and context keys (no secrets)."""
    keys = list(context.keys())
    logger.info("Pipeline step %r context keys: %s", step_name, keys)
    return context


async def truncate_context_middleware(
    step_name: str,
    context: dict[str, Any],
    max_value_chars: int = 5000,
) -> dict[str, Any]:
    """Middleware that truncates string values in context to avoid huge payloads."""

    def truncate(v: Any) -> Any:
        if isinstance(v, str) and len(v) > max_value_chars:
            return v[:max_value_chars] + "… [truncated]"
        if isinstance(v, dict):
            return {k: truncate(x) for k, x in v.items()}
        if isinstance(v, list):
            return [truncate(x) for x in v]
        return v

    return truncate(context)  # type: ignore[return-value]
