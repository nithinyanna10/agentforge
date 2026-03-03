"""Core Agent implementation using a ReAct (Reason + Act) loop."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from agentforge.core.memory import MemoryStore
from agentforge.llm.base import BaseLLMProvider, LLMResponse, Message, Role, ToolCall
from agentforge.tools.base import Tool, ToolResult
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    """Declarative configuration for an Agent."""

    name: str
    role: str = "general"
    system_prompt: str = "You are a helpful AI assistant."
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_react_steps: int = 10
    retry_attempts: int = 3


class ToolCallRecord(BaseModel):
    """An immutable record of a single tool invocation."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: ToolResult | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentResult(BaseModel):
    """The complete output of an agent run."""

    agent_name: str
    task: str
    answer: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    thinking_steps: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event hook type aliases
# ---------------------------------------------------------------------------

OnThinkingHook = Callable[[str, str], Any]          # (agent_name, thought)
OnToolCallHook = Callable[[str, ToolCallRecord], Any]  # (agent_name, record)
OnResultHook = Callable[[str, AgentResult], Any]     # (agent_name, result)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent:
    """A single autonomous agent that follows a ReAct loop.

    The agent iteratively *thinks* (asks the LLM for reasoning), *acts*
    (optionally invokes a tool), and *observes* (reads the tool output) until
    it produces a final answer or exhausts its step budget.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLLMProvider,
        tools: list[Tool] | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.memory = memory

        # Event hooks — callers can replace these after construction.
        self.on_thinking: OnThinkingHook | None = None
        self.on_tool_call: OnToolCallHook | None = None
        self.on_result: OnResultHook | None = None

    # -- public properties ---------------------------------------------------

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def role(self) -> str:
        return self.config.role

    # -- public API ----------------------------------------------------------

    async def run(self, task: str) -> AgentResult:
        """Execute the full ReAct loop for *task* and return an ``AgentResult``."""
        start = datetime.now(timezone.utc)
        messages = self._build_initial_messages(task)
        tool_records: list[ToolCallRecord] = []
        thinking_steps: list[str] = []

        for step in range(self.config.max_react_steps):
            logger.debug("%s | step %d", self.name, step + 1)

            response = await self._think(messages)

            if response.content:
                thinking_steps.append(response.content)
                await self._fire_thinking(response.content)

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                record = await self._act(tc)
                tool_records.append(record)
                await self._fire_tool_call(record)

                messages.append(Message(
                    role=Role.ASSISTANT,
                    content=response.content,
                    tool_calls=[tc],
                ))
                messages.append(Message(
                    role=Role.TOOL,
                    content=json.dumps(record.result.model_dump() if record.result else {"error": "no result"}),
                    tool_call_id=tc.id,
                ))

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        answer = thinking_steps[-1] if thinking_steps else ""

        result = AgentResult(
            agent_name=self.name,
            task=task,
            answer=answer,
            tool_calls=tool_records,
            thinking_steps=thinking_steps,
            duration_seconds=elapsed,
        )

        if self.memory:
            await self.memory.add(f"task: {task}", {"role": "user"})
            await self.memory.add(f"answer: {answer}", {"role": "assistant", "agent": self.name})

        await self._fire_result(result)
        return result

    async def run_with_tools(self, task: str, tools: list[Tool]) -> AgentResult:
        """Run with a one-off set of extra tools merged on top of the default set."""
        original = dict(self.tools)
        try:
            self.tools.update({t.name: t for t in tools})
            return await self.run(task)
        finally:
            self.tools = original

    async def stream(self, task: str) -> AsyncGenerator[str, None]:
        """Yield tokens as they arrive from the LLM (no tool use in streaming mode)."""
        messages = self._build_initial_messages(task)
        tool_specs = self._tool_specs() or None
        async for token in self.llm.stream(
            messages,
            tools=tool_specs,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            yield token

    # -- internal helpers ----------------------------------------------------

    def _build_initial_messages(self, task: str) -> list[Message]:
        system = self.config.system_prompt
        if self.tools:
            tool_list = ", ".join(self.tools.keys())
            system += f"\n\nYou have access to the following tools: {tool_list}."
        return [
            Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=task),
        ]

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self.tools.values()]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _think(self, messages: list[Message]) -> LLMResponse:
        """Ask the LLM to reason about the current conversation state."""
        return await self.llm.complete(
            messages,
            tools=self._tool_specs() or None,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    async def _act(self, tool_call: ToolCall) -> ToolCallRecord:
        """Invoke a tool described by the LLM's structured tool-call."""
        fn_name = tool_call.function_name
        arguments = tool_call.arguments

        record = ToolCallRecord(tool_name=fn_name, arguments=arguments)

        tool = self.tools.get(fn_name)
        if tool is None:
            record.result = ToolResult(success=False, output="", error=f"Unknown tool: {fn_name}")
            logger.warning("%s | unknown tool %r", self.name, fn_name)
            return record

        try:
            record.result = await tool.execute(**arguments)
        except Exception as exc:
            record.result = ToolResult(success=False, output="", error=str(exc))
            logger.exception("%s | tool %r failed", self.name, fn_name)

        return record

    # -- hook dispatchers ----------------------------------------------------

    async def _fire_thinking(self, thought: str) -> None:
        if self.on_thinking:
            coro_or_val = self.on_thinking(self.name, thought)
            if asyncio.iscoroutine(coro_or_val):
                await coro_or_val

    async def _fire_tool_call(self, record: ToolCallRecord) -> None:
        if self.on_tool_call:
            coro_or_val = self.on_tool_call(self.name, record)
            if asyncio.iscoroutine(coro_or_val):
                await coro_or_val

    async def _fire_result(self, result: AgentResult) -> None:
        if self.on_result:
            coro_or_val = self.on_result(self.name, result)
            if asyncio.iscoroutine(coro_or_val):
                await coro_or_val

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, role={self.role!r}, tools={list(self.tools.keys())})"
