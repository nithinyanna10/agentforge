"""Tests for agentforge.core.orchestrator.Orchestrator."""

from __future__ import annotations

import pytest

from agentforge.core.agent import Agent, AgentConfig
from agentforge.core.orchestrator import Orchestrator, OrchestratorResult
from agentforge.llm.base import LLMResponse, TokenUsage

from .conftest import MockLLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name: str, role: str = "general", answer: str = "ok") -> Agent:
    """Create an Agent backed by a MockLLMProvider that returns *answer*."""
    llm = MockLLMProvider(responses=[
        LLMResponse(
            content=answer,
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            model="mock-model",
            finish_reason="stop",
        ),
    ])
    config = AgentConfig(name=name, role=role, max_react_steps=1)
    return Agent(config=config, llm=llm)


def _make_agent_multi(name: str, role: str = "general", answers: list[str] | None = None) -> Agent:
    """Agent with multiple canned responses (one per ``run()`` call)."""
    responses = [
        LLMResponse(
            content=a,
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            model="mock-model",
            finish_reason="stop",
        )
        for a in (answers or ["ok"])
    ]
    llm = MockLLMProvider(responses=responses)
    config = AgentConfig(name=name, role=role, max_react_steps=1)
    return Agent(config=config, llm=llm)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_register_and_get_agent():
    orch = Orchestrator()
    agent = _make_agent("alpha")
    orch.register(agent)

    retrieved = orch.get_agent("alpha")
    assert retrieved is agent
    assert "alpha" in orch.agents


async def test_register_and_get_agent_missing():
    orch = Orchestrator()
    with pytest.raises(KeyError):
        orch.get_agent("nonexistent")


async def test_run_single():
    orch = Orchestrator()
    orch.register(_make_agent("worker", answer="done"))

    result = await orch.run_single("worker", "do work")

    assert result.answer == "done"
    assert result.agent_name == "worker"


async def test_run_sequential():
    orch = Orchestrator()
    orch.register(_make_agent("a", answer="result-a"))
    orch.register(_make_agent("b", answer="result-b"))

    orch_result = await orch.run_sequential(["a", "b"], "task")

    assert isinstance(orch_result, OrchestratorResult)
    assert orch_result.execution_order == ["a", "b"]
    assert "a" in orch_result.results
    assert "b" in orch_result.results
    assert orch_result.merged_answer == "result-b"


async def test_run_sequential_chained():
    """When chain=True, each agent receives the prior agent's answer as context."""
    orch = Orchestrator()
    a = _make_agent("a", answer="context from a")
    b_llm = MockLLMProvider()
    b = Agent(
        config=AgentConfig(name="b", role="general", max_react_steps=1),
        llm=b_llm,
    )
    orch.register(a)
    orch.register(b)

    await orch.run_sequential(["a", "b"], "original task", chain=True)

    last_user_msg = b_llm.calls[0][-1].content
    assert "context from a" in last_user_msg
    assert "original task" in last_user_msg


async def test_run_parallel():
    orch = Orchestrator()
    orch.register(_make_agent("x", answer="x-out"))
    orch.register(_make_agent("y", answer="y-out"))

    orch_result = await orch.run_parallel(["x", "y"], "shared task")

    assert set(orch_result.results.keys()) == {"x", "y"}
    assert "x-out" in orch_result.merged_answer
    assert "y-out" in orch_result.merged_answer


async def test_select_agent_by_role():
    orch = Orchestrator()
    orch.register(_make_agent("coder", role="code"))
    orch.register(_make_agent("writer", role="writing"))

    selected = orch.select_agent("write a poem", role="writing")
    assert selected.name == "writer"


async def test_select_agent_by_role_missing():
    orch = Orchestrator()
    orch.register(_make_agent("coder", role="code"))

    with pytest.raises(KeyError, match="No agent with role"):
        orch.select_agent("task", role="nonexistent")
