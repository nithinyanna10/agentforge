"""Shared fixtures for the AgentForge test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agentforge.core.agent import Agent, AgentConfig, AgentResult
from agentforge.core.memory import MemoryStore, MemoryEntry
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline, PipelineStep
from agentforge.llm.base import BaseLLMProvider, LLMResponse, Message, Role, ToolCall, TokenUsage
from agentforge.tools.base import Tool, ToolResult, ToolRegistry


# ---------------------------------------------------------------------------
# Mock LLM provider
# ---------------------------------------------------------------------------

class MockLLMProvider(BaseLLMProvider):
    """In-memory LLM provider that returns pre-configured responses.

    Append ``LLMResponse`` objects to ``self.responses`` before calling the
    agent.  Each call to ``complete()`` pops the first item from the list.
    """

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        super().__init__(model="mock-model")
        self.responses: list[LLMResponse] = list(responses or [])
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(
            content="default mock answer",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            model=self.model,
            finish_reason="stop",
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        self.calls.append(messages)
        for token in ["Hello", " ", "world", "!"]:
            yield token


# ---------------------------------------------------------------------------
# Mock tool
# ---------------------------------------------------------------------------

class MockTool(Tool):
    """A tool that always succeeds with a canned result."""

    def __init__(
        self,
        tool_name: str = "mock_tool",
        tool_description: str = "A mock tool for testing",
        result: ToolResult | None = None,
    ) -> None:
        self._name = tool_name
        self._description = tool_description
        self._result = result or ToolResult(success=True, output="mock output")
        self.call_log: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Input query"},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        self.call_log.append(kwargs)
        return self._result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm_provider() -> MockLLMProvider:
    return MockLLMProvider()


@pytest.fixture()
def mock_tool() -> MockTool:
    return MockTool()


@pytest.fixture()
def sample_agent_config() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        role="general",
        system_prompt="You are a helpful test agent.",
        model="mock-model",
        temperature=0.0,
        max_tokens=256,
        max_react_steps=5,
        retry_attempts=1,
    )


@pytest.fixture()
def sample_agent(
    sample_agent_config: AgentConfig,
    mock_llm_provider: MockLLMProvider,
    mock_tool: MockTool,
) -> Agent:
    return Agent(
        config=sample_agent_config,
        llm=mock_llm_provider,
        tools=[mock_tool],
    )


@pytest.fixture()
def mock_memory() -> AsyncMock:
    mem = AsyncMock(spec=MemoryStore)
    mem.search.return_value = []
    mem.get_recent.return_value = []
    return mem
