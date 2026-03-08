"""Span-based request tracer for AgentForge — logs agent runs, tool calls, and LLM calls."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import StrEnum
from functools import wraps
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class SpanKind(StrEnum):
    INTERNAL = "internal"
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"
    PIPELINE = "pipeline"


class SpanEvent(BaseModel):
    name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: dict[str, Any] = Field(default_factory=dict)


class Span(BaseModel):
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    name: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)
    error: str | None = None

    def add_event(self, name: str, attrs: dict[str, Any] | None = None) -> None:
        self.events.append(SpanEvent(name=name, attributes=attrs or {}))

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: SpanStatus, error: str | None = None) -> None:
        self.status = status
        self.error = error

    def end(self) -> None:
        self.end_time = datetime.now(timezone.utc)
        if self.start_time and self.end_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": [e.model_dump() for e in self.events],
            "error": self.error,
        }


_tracer: "Tracer | None" = None


class Tracer:
    """In-process tracer storing spans for a service."""

    def __init__(self, service_name: str = "agentforge", export_to_file: str | None = None) -> None:
        self._service_name = service_name
        self._export_path = export_to_file
        self._spans: list[Span] = []
        self._lock: Any = None

    def _lock_sync(self) -> Any:
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Span | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        span = Span(
            name=name,
            kind=kind,
            parent_id=parent.span_id if parent else None,
            trace_id=parent.trace_id if parent else uuid.uuid4().hex,
            attributes=attributes or {},
        )
        self._spans.append(span)
        return span

    def finish_span(self, span: Span, status: SpanStatus = SpanStatus.OK, error: str | None = None) -> None:
        span.set_status(status, error=error)
        span.end()

    def get_spans(self, trace_id: str | None = None) -> list[Span]:
        if trace_id is None:
            return list(self._spans)
        return [s for s in self._spans if s.trace_id == trace_id]

    def export_json(self, path: str) -> None:
        with open(path, "w") as f:
            for s in self._spans:
                f.write(json.dumps(s.to_dict()) + "\n")

    def clear(self) -> None:
        self._spans.clear()

    def stats(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        durations: list[float] = []
        errors = 0
        for s in self._spans:
            by_kind[s.kind.value] = by_kind.get(s.kind.value, 0) + 1
            if s.duration_ms is not None:
                durations.append(s.duration_ms)
            if s.status == SpanStatus.ERROR:
                errors += 1
        return {
            "total_spans": len(self._spans),
            "by_kind": by_kind,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "error_count": errors,
        }


@asynccontextmanager
async def trace(tracer: Tracer, name: str, kind: SpanKind = SpanKind.INTERNAL, **attrs: Any) -> AsyncGenerator[Span, None]:
    """Context manager: start a span, yield it, finish on exit. Sets ERROR on exception."""
    span = tracer.start_span(name, kind=kind, attributes=attrs)
    try:
        yield span
        tracer.finish_span(span, SpanStatus.OK)
    except Exception as e:
        tracer.finish_span(span, SpanStatus.ERROR, error=str(e))
        raise


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
