"""Tests for agentforge.core.agent.Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentforge.core.agent import Agent, AgentConfig, AgentResult, ToolCallRecord
from agentforge.llm.base import LLMResponse, ToolCall, TokenUsage
from agentforge.tools.base import ToolResult

from .conftest import MockLLMProvider, MockTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_response(text: str = "final answer") -> LLMResponse:
    """An LLM response with no tool calls (i.e. the agent should stop)."""
    return LLMResponse(
        content=text,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="mock-model",
        finish_reason="stop",
    )


def _tool_call_response(
    text: str = "I should use a tool",
    fn_name: str = "mock_tool",
    arguments: dict | None = None,
) -> LLMResponse:
    """An LLM response that requests a tool invocation."""
    return LLMResponse(
        content=text,
        tool_calls=[
            ToolCall(id="tc_001", function_name=fn_name, arguments=arguments or {"query": "test"})
        ],
        usage=TokenUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        model="mock-model",
        finish_reason="tool_calls",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_agent_run_simple(sample_agent: Agent, mock_llm_provider: MockLLMProvider):
    """Agent answers immediately when the LLM returns no tool_calls."""
    mock_llm_provider.responses = [_simple_response("Paris is the capital of France.")]

    result = await sample_agent.run("What is the capital of France?")

    assert isinstance(result, AgentResult)
    assert result.answer == "Paris is the capital of France."
    assert result.tool_calls == []
    assert result.agent_name == "test-agent"
    assert len(mock_llm_provider.calls) == 1


async def test_agent_run_with_tool(sample_agent: Agent, mock_llm_provider: MockLLMProvider):
    """Agent invokes a tool (first call), then produces a final answer (second call)."""
    mock_llm_provider.responses = [
        _tool_call_response("Let me look that up", "mock_tool", {"query": "weather NYC"}),
        _simple_response("The weather in NYC is sunny."),
    ]

    result = await sample_agent.run("What's the weather in NYC?")

    assert result.answer == "The weather in NYC is sunny."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "mock_tool"
    assert result.tool_calls[0].result is not None
    assert result.tool_calls[0].result.success is True


async def test_agent_stream(sample_agent: Agent):
    """Streaming yields individual tokens from the mock LLM."""
    tokens: list[str] = []
    async for token in sample_agent.stream("Say hello"):
        tokens.append(token)

    assert tokens == ["Hello", " ", "world", "!"]


async def test_agent_hooks(
    sample_agent_config: AgentConfig,
    mock_tool: MockTool,
):
    """Verify on_thinking, on_tool_call, and on_result hooks fire."""
    llm = MockLLMProvider(responses=[
        _tool_call_response("Thinking step"),
        _simple_response("Done"),
    ])
    agent = Agent(config=sample_agent_config, llm=llm, tools=[mock_tool])

    thinking_log: list[str] = []
    tool_call_log: list[ToolCallRecord] = []
    result_log: list[AgentResult] = []

    agent.on_thinking = lambda name, thought: thinking_log.append(thought)
    agent.on_tool_call = lambda name, record: tool_call_log.append(record)
    agent.on_result = lambda name, result: result_log.append(result)

    await agent.run("Do something")

    assert len(thinking_log) >= 1
    assert "Thinking step" in thinking_log
    assert len(tool_call_log) == 1
    assert tool_call_log[0].tool_name == "mock_tool"
    assert len(result_log) == 1
    assert result_log[0].answer == "Done"


async def test_agent_max_steps(sample_agent_config: AgentConfig, mock_tool: MockTool):
    """Agent stops after exhausting max_react_steps even if the LLM keeps requesting tools."""
    config = sample_agent_config.model_copy(update={"max_react_steps": 3})

    infinite_tool_calls = [_tool_call_response(f"step {i}") for i in range(10)]
    llm = MockLLMProvider(responses=infinite_tool_calls)
    agent = Agent(config=config, llm=llm, tools=[mock_tool])

    result = await agent.run("loop forever")

    assert len(llm.calls) == config.max_react_steps
    assert len(result.tool_calls) == config.max_react_steps


async def test_agent_unknown_tool(sample_agent: Agent, mock_llm_provider: MockLLMProvider):
    """Agent gracefully handles a tool call for a tool that isn't registered."""
    mock_llm_provider.responses = [
        _tool_call_response("use it", "nonexistent_tool", {"x": 1}),
        _simple_response("Recovered from unknown tool."),
    ]

    result = await sample_agent.run("try a missing tool")

    assert result.answer == "Recovered from unknown tool."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].result is not None
    assert result.tool_calls[0].result.success is False
    assert "Unknown tool" in (result.tool_calls[0].result.error or "")


async def test_agent_memory_integration(
    sample_agent_config: AgentConfig,
    mock_llm_provider: MockLLMProvider,
    mock_memory: AsyncMock,
):
    """Agent writes task and answer to memory when a MemoryStore is provided."""
    mock_llm_provider.responses = [_simple_response("42")]
    agent = Agent(
        config=sample_agent_config,
        llm=mock_llm_provider,
        memory=mock_memory,
    )

    await agent.run("What is the meaning of life?")

    assert mock_memory.add.call_count == 2
    first_call_content = mock_memory.add.call_args_list[0][0][0]
    second_call_content = mock_memory.add.call_args_list[1][0][0]
    assert "What is the meaning of life?" in first_call_content
    assert "42" in second_call_content
