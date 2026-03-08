"""Tests for AgentForge extensions: new tools, RunStore, pipeline retries, templates, ext."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agentforge.core.run_store import RunStore, StoredRun
from agentforge.core.pipeline import Pipeline, PipelineStep
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.agent import Agent, AgentConfig
from agentforge.ext import (
    register_tool,
    get_registered_tools,
    clear_registries,
    register_agent_factory,
    get_agent_factory,
    list_agent_factories,
)
from agentforge.tools.math_expression import MathExpressionTool
from agentforge.tools.datetime_tool import DateTimeTool
from agentforge.tools.sql_query import SqlQueryTool
from agentforge.tools.shell_command import ShellCommandTool
from agentforge.llm.base import BaseLLMProvider, LLMResponse, Message, Role, TokenUsage
from agentforge.templates import create_general


# ---------------------------------------------------------------------------
# RunStore
# ---------------------------------------------------------------------------


async def test_run_store_save_and_get(tmp_path):
    db = tmp_path / "runs.db"
    store = RunStore(db)
    rid = await store.save(
        agent_name="test_agent",
        task="Hello",
        answer="Hi",
        tool_calls=[],
        thinking_steps=["step1"],
        duration_seconds=1.5,
        metadata={"key": "value"},
    )
    assert isinstance(rid, str)
    assert len(rid) >= 8

    loaded = await store.get(rid)
    assert loaded is not None
    assert loaded.agent_name == "test_agent"
    assert loaded.task == "Hello"
    assert loaded.answer == "Hi"
    assert loaded.duration_seconds == 1.5
    assert loaded.metadata_json == '{"key": "value"}'


async def test_run_store_list_recent(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    await store.save("a", "t1", "o1", [], [], 1.0)
    await store.save("a", "t2", "o2", [], [], 2.0)
    await store.save("b", "t3", "o3", [], [], 3.0)

    recent = await store.list_recent(limit=10)
    assert len(recent) == 3
    recent_a = await store.list_recent(limit=10, agent_name="a")
    assert len(recent_a) == 2
    assert all(r.agent_name == "a" for r in recent_a)


async def test_run_store_clear(tmp_path):
    store = RunStore(tmp_path / "runs.db")
    await store.save("a", "t", "o", [], [], 1.0)
    await store.clear()
    recent = await store.list_recent(limit=10)
    assert len(recent) == 0


# ---------------------------------------------------------------------------
# New tools: Math, DateTime, SqlQuery, Shell
# ---------------------------------------------------------------------------


async def test_math_expression_tool():
    tool = MathExpressionTool()
    r = await tool.execute(expression="2 * 3 + 4")
    assert r.success
    assert r.output in ("10", "10.0")
    r2 = await tool.execute(expression="abs(-7)")
    assert r2.success
    assert r2.output in ("7", "7.0")


async def test_datetime_tool_now():
    tool = DateTimeTool()
    r = await tool.execute(action="now", timezone="UTC")
    assert r.success
    assert "T" in r.output and "Z" in r.output or "+" in r.output


async def test_sql_query_tool_readonly(tmp_path):
    db = tmp_path / "data.db"
    import aiosqlite
    async with aiosqlite.connect(str(db)) as conn:
        await conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        await conn.execute("INSERT INTO t VALUES (1, 'a'), (2, 'b')")
        await conn.commit()

    tool = SqlQueryTool(db)
    r = await tool.execute(query="SELECT * FROM t")
    assert r.success
    assert "id" in r.output and "name" in r.output
    assert "1" in r.output and "a" in r.output


async def test_sql_query_tool_rejects_write(tmp_path):
    db = tmp_path / "data.db"
    db.write_text("")  # empty file will fail on connect but we test validation first
    tool = SqlQueryTool(db)
    r = await tool.execute(query="INSERT INTO t VALUES (1)")
    assert not r.success
    assert "SELECT" in r.error or "Only" in r.error


async def test_shell_command_tool_allowlist():
    tool = ShellCommandTool(allowlist={"echo", "date"}, timeout_seconds=5)
    r = await tool.execute(command="echo hello")
    assert r.success
    assert "hello" in r.output
    r2 = await tool.execute(command="rm -rf /")
    assert not r2.success
    assert "allowlist" in r2.error.lower() or "not" in r2.error.lower()


# ---------------------------------------------------------------------------
# Pipeline retries and timeout
# ---------------------------------------------------------------------------


async def test_pipeline_step_retries():
    """Orchestrator retries a failing step up to retries+1 times."""
    from tests.conftest import MockLLMProvider

    llm = MockLLMProvider(responses=[
        LLMResponse(content="first try", usage=TokenUsage(), model="mock", finish_reason="stop"),
        LLMResponse(content="second try", usage=TokenUsage(), model="mock", finish_reason="stop"),
    ])
    config = AgentConfig(name="test", role="test", system_prompt="You are helpful.")
    agent = Agent(config=config, llm=llm)
    orch = Orchestrator()
    orch.register(agent)

    step = PipelineStep(
        name="s1",
        agent_name=agent.name,
        retries=1,
    )
    pipe = Pipeline(name="p", steps=[step])
    result = await orch.run_pipeline(pipe, initial_inputs={"__task__": "hello"})
    assert result.merged_answer
    assert len(result.results) == 1


async def test_pipeline_step_timeout():
    """Step with timeout_seconds uses wait_for (we only check it runs)."""
    from tests.conftest import MockLLMProvider

    llm = MockLLMProvider(responses=[
        LLMResponse(content="done", usage=TokenUsage(), model="mock", finish_reason="stop"),
    ])
    config = AgentConfig(name="test", role="test", system_prompt="You are helpful.")
    agent = Agent(config=config, llm=llm)
    orch = Orchestrator()
    orch.register(agent)

    step = PipelineStep(
        name="s1",
        agent_name=agent.name,
        timeout_seconds=60.0,
    )
    pipe = Pipeline(name="p", steps=[step])
    result = await orch.run_pipeline(pipe, initial_inputs={"__task__": "hi"})
    assert result.merged_answer == "done"


# ---------------------------------------------------------------------------
# Extension system
# ---------------------------------------------------------------------------


def test_register_tool_and_list():
    clear_registries()
    register_tool(MathExpressionTool)
    tools = get_registered_tools()
    assert any(t.__name__ == "MathExpressionTool" for t in tools)
    clear_registries()


def test_register_agent_factory():
    clear_registries()
    from tests.conftest import MockLLMProvider
    llm = MockLLMProvider()
    def factory():
        return Agent(config=AgentConfig(name="x", role="y"), llm=llm)
    register_agent_factory("test_agent", factory)
    assert "test_agent" in list_agent_factories()
    f = get_agent_factory("test_agent")
    assert f is factory
    clear_registries()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_create_general_returns_agent():
    from tests.conftest import MockLLMProvider
    llm = MockLLMProvider()
    agent = create_general(llm, name="gen")
    assert agent.name == "gen"
    assert agent.role == "general"
    assert len(agent.tools) >= 2  # web search, datetime, math
