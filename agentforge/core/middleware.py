"""
Pipeline middleware collection for AgentForge (next-level).

Pre-built middleware for logging, truncation, redaction, and metrics.
"""

from __future__ import annotations

import time
from typing import Any

from agentforge.core.pipeline_events import PipelineEventBus
from agentforge.observability.events import emit_event, EventKind, StructuredEvent
from agentforge.utils.logging import get_logger
from agentforge.utils.sanitize import sanitize_for_log, truncate

logger = get_logger(__name__)


async def metrics_middleware(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Emit a pipeline_step event for each step start (call before step runs)."""
    emit_event(
        StructuredEvent(
            kind=EventKind.PIPELINE_STEP,
            name=step_name,
            message=f"step_start {step_name}",
            metadata={"step": step_name, "context_keys": list(context.keys())},
        )
    )
    return context


async def redact_context_middleware(
    step_name: str,
    context: dict[str, Any],
    max_str_length: int = 500,
) -> dict[str, Any]:
    """Sanitize context for logging (redact secrets, truncate)."""
    return sanitize_for_log(context, max_str_length)  # type: ignore[return-value]


async def timing_middleware(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Add a timestamp key for the step (for later duration calculation)."""
    context["_middleware_timing_start"] = time.monotonic()
    return context


def create_truncate_middleware(max_value_chars: int = 5000) -> Any:
    """Factory that returns a truncate middleware with the given max chars."""

    async def mw(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for k, v in context.items():
            if isinstance(v, str) and len(v) > max_value_chars:
                result[k] = truncate(v, max_value_chars)
            elif isinstance(v, list):
                result[k] = [
                    truncate(x, max_value_chars) if isinstance(x, str) else x
                    for x in v
                ]
            else:
                result[k] = v
        return result

    return mw


def register_default_middleware(bus: PipelineEventBus | None = None) -> PipelineEventBus:
    """Register logging and truncate middleware on the given bus (or default)."""
    from agentforge.core.pipeline_events import get_pipeline_event_bus, logging_middleware
    b = bus or get_pipeline_event_bus()
    b.add_middleware(logging_middleware)
    b.add_middleware(create_truncate_middleware(5000))
    return b
