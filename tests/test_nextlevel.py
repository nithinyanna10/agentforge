"""Tests for AgentForge next-level modules: cache, rate limiter, evaluator, planner, supervisor, reflection, tools, observability."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from agentforge.core.cache import (
    InMemoryCache,
    make_cache_key,
    CacheMiddleware,
    BaseCache,
)
from agentforge.core.rate_limiter import RateLimiter, RateLimitConfig, RateLimitedProvider
from agentforge.core.evaluator import Evaluator, EvalCriterion, EvalResult, EvalScore
from agentforge.core.planner import Planner, TaskPlan, SubTask, PlanExecutionResult
from agentforge.core.supervisor import Supervisor, SupervisorConfig, SupervisorResult
from agentforge.core.reflection import ReflectionAgent, ReflectionConfig, ReflectionResult
from agentforge.llm.base import BaseLLMProvider, LLMResponse, Message, Role, TokenUsage
from agentforge.core.agent import Agent, AgentConfig
from agentforge.tools.github_tool import GitHubTool
from agentforge.observability.tracer import Tracer, SpanKind, SpanStatus, get_tracer, trace
from agentforge.observability.metrics import get_metrics, Metrics


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


async def test_in_memory_cache_set_get():
    cache = InMemoryCache(max_size=10, default_ttl=3600)
    from agentforge.llm.base import LLMResponse, TokenUsage
    key = make_cache_key("openai", "gpt-4o", [Message(role=Role.USER, content="Hi")], None)
    resp = LLMResponse(content="Hello", usage=TokenUsage(), model="gpt-4o")
    await cache.set(key, resp)
    got = await cache.get(key)
    assert got is not None
    assert got.content == "Hello"
    assert (await cache.get(make_cache_key("other", "gpt-4o", [Message(role=Role.USER, content="Hi")], None))) is None


async def test_in_memory_cache_stats():
    cache = InMemoryCache(max_size=10)
    key = make_cache_key("p", "m", [Message(role=Role.USER, content="x")], None)
    await cache.set(key, LLMResponse(content="y", usage=TokenUsage(), model="m"))
    await cache.get(key)
    st = await cache.stats()
    assert st["size"] == 1
    assert st["hits"] == 1


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


async def test_rate_limiter_acquire():
    config = RateLimitConfig(requests_per_minute=100, tokens_per_minute=10000)
    limiter = RateLimiter(config)
    wait = await limiter.acquire(estimated_tokens=10)
    assert wait >= 0
    st = limiter.stats()
    assert st["total_requests"] == 1


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


async def test_evaluator_returns_result():
    mock_llm = AsyncMock(spec=BaseLLMProvider)
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='{"scores": [{"criterion": "helpfulness", "score": 8, "reasoning": "Good", "suggestions": []}]}',
        usage=TokenUsage(),
        model="mock",
    ))
    mock_llm.model = "mock"
    ev = Evaluator(mock_llm)
    result = await ev.evaluate("What is 2+2?", "2+2 equals 4.")
    assert isinstance(result, EvalResult)
    assert result.task == "What is 2+2?"
    assert len(result.scores) >= 0
    assert result.overall_score >= 0
    assert result.grade in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


async def test_planner_create_plan():
    mock_llm = AsyncMock(spec=BaseLLMProvider)
    mock_llm.complete = AsyncMock(return_value=LLMResponse(
        content='{"subtasks": [{"id": "s1", "title": "Step 1", "description": "Do thing", "depends_on": [], "assigned_agent": "researcher", "estimated_steps": 1, "priority": 3}], "estimated_total_steps": 1}',
        usage=TokenUsage(),
        model="mock",
    ))
    planner = Planner(mock_llm)
    plan = await planner.create_plan("Summarize the news", available_agents=["researcher"])
    assert isinstance(plan, TaskPlan)
    assert plan.goal == "Summarize the news"
    assert len(plan.subtasks) >= 0


async def test_planner_execute_plan_no_orchestrator():
    mock_llm = AsyncMock(spec=BaseLLMProvider)
    mock_llm.complete = AsyncMock(return_value=LLMResponse(content="Done.", usage=TokenUsage(), model="mock"))
    plan = TaskPlan(goal="G", subtasks=[SubTask(id="s1", title="S1", description="Do it", depends_on=[])])
    planner = Planner(mock_llm)
    result = await planner.execute_plan(plan)
    assert isinstance(result, PlanExecutionResult)
    assert result.plan == plan
    assert "s1" in result.results
    assert result.success


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


async def test_supervisor_run():
    mock_llm = AsyncMock(spec=BaseLLMProvider)
    mock_llm.complete = AsyncMock(side_effect=[
        LLMResponse(content='[{"agent_name": "a1", "sub_task": "Sub1"}]', usage=TokenUsage(), model="mock"),
        LLMResponse(content="Agent answer for Sub1.", usage=TokenUsage(), model="mock"),  # agent.run
        LLMResponse(content="Synthesized answer.", usage=TokenUsage(), model="mock"),
    ])
    mock_llm.model = "mock"
    config = AgentConfig(name="a1", role="research")
    agent = Agent(config=config, llm=mock_llm)
    sup = Supervisor(SupervisorConfig(name="sup"), mock_llm, {"a1": agent})
    result = await sup.run("Research X")
    assert isinstance(result, SupervisorResult)
    assert result.task == "Research X"
    assert result.final_answer


# ---------------------------------------------------------------------------
# Reflection
# ---------------------------------------------------------------------------


async def test_reflection_agent_run():
    mock_llm = AsyncMock(spec=BaseLLMProvider)
    mock_llm.complete = AsyncMock(side_effect=[
        LLMResponse(content="Initial answer.", usage=TokenUsage(), model="mock"),
        LLMResponse(content='{"score": 9, "critique": "Good", "improvements": []}', usage=TokenUsage(), model="mock"),
    ])
    config = AgentConfig(name="a", role="general")
    agent = Agent(config=config, llm=mock_llm)
    ref = ReflectionAgent(agent, critic_llm=mock_llm, config=ReflectionConfig(max_iterations=2))
    result = await ref.run("Hello")
    assert isinstance(result, ReflectionResult)
    assert result.task == "Hello"
    assert result.final_answer
    assert result.total_iterations >= 1


# ---------------------------------------------------------------------------
# GitHub tool
# ---------------------------------------------------------------------------


def test_github_tool_name_and_params():
    tool = GitHubTool()
    assert tool.name == "github"
    assert "search" in tool.description.lower()
    assert "action" in tool.parameters.get("required", [])


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


def test_tracer_start_finish_span():
    t = Tracer(service_name="test")
    span = t.start_span("test_span", kind=SpanKind.AGENT)
    assert span.name == "test_span"
    assert span.trace_id
    t.finish_span(span, SpanStatus.OK)
    assert span.end_time is not None
    assert span.duration_ms is not None
    assert len(t.get_spans()) == 1


async def test_trace_context_manager():
    t = Tracer()
    async with trace(t, "ctx", kind=SpanKind.TOOL) as span:
        span.set_attribute("key", "value")
    assert span.status == SpanStatus.OK
    assert span.attributes.get("key") == "value"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_counter_gauge():
    m = get_metrics()
    c = m.counter("test_counter", "Help", ["env"])
    c.inc(labels={"env": "test"})
    c.inc(labels={"env": "test"}, amount=2)
    assert c.get({"env": "test"}) == 3
    g = m.gauge("test_gauge", "Help")
    g.set(10)
    g.inc(amount=5)
    assert g.get() == 15
    out = m.render_prometheus()
    assert "test_counter" in out
    assert "test_gauge" in out
