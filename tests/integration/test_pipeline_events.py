"""
Integration tests for pipeline event bus and middleware.
"""

from __future__ import annotations

import pytest

from agentforge.core.pipeline_events import (
    PipelineEventBus,
    PipelineEvent,
    PipelineEventType,
    get_pipeline_event_bus,
    reset_pipeline_event_bus,
    logging_middleware,
    truncate_context_middleware,
)


@pytest.fixture(autouse=True)
def reset_bus() -> None:
    reset_pipeline_event_bus()
    yield
    reset_pipeline_event_bus()


class TestPipelineEventBus:
    """Tests for PipelineEventBus."""

    @pytest.mark.asyncio
    async def test_subscribe_emit(self) -> None:
        bus = PipelineEventBus()
        received: list[PipelineEvent] = []
        bus.subscribe(received.append)
        event = PipelineEvent(type=PipelineEventType.STEP_START, pipeline_name="p", step_name="s1")
        await bus.emit(event)
        assert len(received) == 1
        assert received[0].step_name == "s1"

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = PipelineEventBus()
        received: list[PipelineEvent] = []
        bus.subscribe(received.append)
        bus.unsubscribe(received.append)
        event = PipelineEvent(type=PipelineEventType.STEP_END, step_name="s1")
        await bus.emit(event)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_middleware_transforms_context(self) -> None:
        bus = PipelineEventBus()
        async def add_foo(step_name: str, context: dict) -> dict:
            context["foo"] = "bar"
            return context
        bus.add_middleware(add_foo)
        out = await bus.run_middleware("step1", {"a": 1})
        assert out.get("foo") == "bar"
        assert out.get("a") == 1


class TestPipelineEvent:
    """Tests for PipelineEvent."""

    def test_to_dict(self) -> None:
        event = PipelineEvent(
            type=PipelineEventType.PIPELINE_START,
            pipeline_name="my_pipeline",
            payload={"key": "value"},
        )
        d = event.to_dict()
        assert d["type"] == "pipeline_start"
        assert d["pipeline_name"] == "my_pipeline"
        assert d["payload"]["key"] == "value"
        assert "timestamp" in d


class TestMiddlewareHelpers:
    """Tests for built-in middleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware_passthrough(self) -> None:
        ctx = {"step_a": "result"}
        out = await logging_middleware("step_b", ctx)
        assert out == ctx

    @pytest.mark.asyncio
    async def test_truncate_context_middleware(self) -> None:
        long_str = "x" * 10000
        ctx = {"a": "short", "b": long_str}
        out = await truncate_context_middleware("s", ctx, max_value_chars=100)
        assert out["a"] == "short"
        assert len(out["b"]) <= 110
        assert "truncated" in out["b"] or "…" in out["b"]


class TestGetPipelineEventBus:
    """Tests for singleton bus."""

    def test_singleton(self) -> None:
        bus1 = get_pipeline_event_bus()
        bus2 = get_pipeline_event_bus()
        assert bus1 is bus2

    def test_reset_clears_handlers(self) -> None:
        bus = get_pipeline_event_bus()
        bus.subscribe(lambda e: None)
        reset_pipeline_event_bus()
        bus2 = get_pipeline_event_bus()
        assert bus is not bus2 or len(bus2._handlers) == 0
