"""
Structured events for AgentForge observability (next-level).

Emit typed events for agent runs, tool calls, pipeline steps, and errors
so that external systems (logging, metrics, tracing) can consume them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class EventKind(str, Enum):
    """Top-level event kind for filtering."""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PIPELINE_STEP = "pipeline_step"
    ERROR = "error"
    METRIC = "metric"


@dataclass
class StructuredEvent:
    """A single structured event for logging/metrics."""

    kind: EventKind
    name: str = ""
    message: str = ""
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": self.kind.value,
            "name": self.name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.duration_seconds is not None:
            d["duration_seconds"] = self.duration_seconds
        if self.metadata:
            d["metadata"] = self.metadata
        if self.correlation_id:
            d["correlation_id"] = self.correlation_id
        return d


_event_handlers: list[Callable[[StructuredEvent], None]] = []


def emit_event(event: StructuredEvent) -> None:
    """Emit a structured event to all registered handlers."""
    for h in _event_handlers:
        try:
            h(event)
        except Exception:
            pass


def register_event_handler(handler: Callable[[StructuredEvent], None]) -> None:
    """Register a handler (event) -> None. Called synchronously."""
    _event_handlers.append(handler)


def clear_event_handlers() -> None:
    """Remove all event handlers (e.g. for tests)."""
    _event_handlers.clear()
